"""Tests for phlux/discovery/report.py and run.py — records, first_seen, README, the run."""
import json
from unittest.mock import patch

from phlux.discovery import run as discovery_run
from phlux.discovery.detect import Detection
from phlux.discovery.report import build, load, record, render, skipped_record, stamp, write
from phlux.discovery.sources import Candidate
from phlux.discovery.tracked import Match, Tracked, TrackedIndex
from phlux.models import Company

TODAY = "2026-11-08"


def candidate(name, website="", focus="robotics", **extra):
    return Candidate(name=name, website=website, source="yc", focus=focus, one_liner=f"{name} | robots", **extra)


def board(postings, internships=0, link="https://jobs.ashbyhq.com/x", titles=()):
    return Detection(board="ashby", slug="x", link=link, evidence="linked from site", postings=postings,
                     internships=internships, internship_titles=list(titles))


RECORDS = [
    record(candidate("Bolt", "https://bolt.dev"), board(30, 1, titles=["Robotics Intern"]), TODAY),
    record(candidate("Acme, Inc.", "https://acme.com"), board(80, 3, titles=["Intern A", "Intern B", "Co-op C"]), TODAY),
    record(candidate("Quiet", "https://quiet.io", focus="adjacent"), board(5), TODAY),
    record(candidate("Loud", "https://loud.io"), board(2), TODAY),
    record(candidate("Hidden", "https://hidden.io", hiring=True, yc_url="https://www.ycombinator.com/companies/hidden"),
           Detection(reason="no job board linked from 3 page(s)"), TODAY),
    record(candidate("Samename", "https://samename.ai"),
           Detection(board="greenhouse", slug="samename", link="https://job-boards.greenhouse.io/samename",
                     postings=4, internships=0, verified=False), TODAY),
]
SKIPPED = [
    skipped_record(candidate("Relativity Space"), Match(Tracked("Relativity", True), "same name without suffixes")),
    skipped_record(candidate("Welch's Inc"), Match(Tracked("Welch's", False), "same greenhouse board")),
]


def fresh(records=RECORDS):
    return [dict(r) for r in records]


def test_record_holds_the_row_and_counts():
    rec = RECORDS[1]
    assert rec["row"] == "Acme,https://jobs.ashbyhq.com/x,@ashby->FILTER:intern"
    assert (rec["board"], rec["postings"], rec["internships"], rec["reason"]) == ("ashby", 80, 3, None)
    assert (rec["first_seen"], rec["last_checked"]) == (TODAY, TODAY)
    unresolved = RECORDS[4]
    assert (unresolved["board"], unresolved["row"], unresolved["reason"]) == (
        None, None, "no job board linked from 3 page(s)")


def test_first_seen_survives_reruns_by_domain_or_name():
    previous = {"candidates": [
        {"name": "Bolt", "website": "http://www.bolt.dev/", "first_seen": "2026-10-01"},
        {"name": "Acme Inc", "website": "https://acme.com", "first_seen": "2026-10-15"},
        {"name": "Loud", "website": "https://loud-old-domain.io", "first_seen": "2026-09-30"},
    ]}
    records = fresh()
    stamp(records, previous)
    seen = {r["name"]: r["first_seen"] for r in records}
    assert seen == {"Bolt": "2026-10-01", "Acme, Inc.": "2026-10-15", "Quiet": TODAY, "Loud": "2026-09-30",
                    "Hidden": TODAY, "Samename": TODAY}


def test_build_sorts_and_counts():
    records = fresh()
    stamp(records, {"candidates": [{"name": "Bolt", "website": "https://bolt.dev", "first_seen": "2026-10-01"}]})
    data = build(records, SKIPPED, ["yc", "seeds"], TODAY)
    assert [r["name"] for r in data["candidates"]] == ["Acme, Inc.", "Bolt", "Hidden", "Loud", "Quiet", "Samename"]
    assert data["stats"] == {"considered": 8, "tracked": 2, "with_board": 4, "with_internships": 2,
                             "name_only": 1, "unresolved": 1, "new": 5}


def test_readme_sections_in_order_with_rows():
    records = fresh()
    stamp(records, {"candidates": [{"name": "Bolt", "website": "https://bolt.dev", "first_seen": "2026-10-01"}]})
    readme = render(build(records, SKIPPED, ["yc", "seeds"], TODAY))
    sections = [line for line in readme.splitlines() if line.startswith("## ")]
    assert sections == ["## Adding a company", "## With internships open (2)",
                        "## With a job board, no internships right now (2)",
                        "## Matched by name only — check before adding (1)", "## Unresolved (1)",
                        "## Already tracked (2)"]
    assert readme.index("[Samename]") > readme.index("[Quiet]")
    # Most internships first; new companies marked; one-liners escaped.
    acme = readme.index("[Acme, Inc.](https://acme.com)")
    assert acme < readme.index("[Bolt](https://bolt.dev)")
    assert "| **new** | [Acme, Inc.](https://acme.com) | Acme, Inc. \\| robots |" in readme
    assert "|  | [Bolt](https://bolt.dev) |" in readme
    # Ready-to-paste rows, and the list reminder.
    assert "```csv\nAcme,https://jobs.ashbyhq.com/x,@ashby->FILTER:intern\nBolt,https://jobs.ashbyhq.com/x,@ashby\n```" in readme
    assert "`lists/robotics.json`" in readme
    # Robotics before adjacent among boards without internships.
    assert readme.index("[Loud]") < readme.index("[Quiet]")
    assert "hiring on [YC](https://www.ycombinator.com/companies/hidden/jobs)" in readme
    # Tracked rows the bot never reads are called out.
    assert "- Welch's Inc (row Welch's: same greenhouse board)" in readme


def test_write_and_load_round_trip(tmp_path):
    data = build(fresh(), SKIPPED, ["yc"], TODAY)
    write(tmp_path / "discovery", data)
    assert load(tmp_path / "discovery" / "candidates.json") == data
    assert (tmp_path / "discovery" / "README.md").read_text().startswith("# Discovered companies")
    assert load(tmp_path / "nothing.json") == {"candidates": []}


# ── Run ───────────────────────────────────────────────────────────────────────


class Static:
    name = "yc"

    def __init__(self, candidates):
        self._candidates = candidates

    def candidates(self):
        return list(self._candidates)


TRACKED = [Company("Relativity", "https://job-boards.greenhouse.io/relativity", "@greenhouse")]


def fake_detect(name, website, batch=""):
    if name == "Crashy":
        raise ValueError("odd page")
    if name == "Rel Space Corp":  # a name the index can't place, but its board is tracked
        return Detection(board="greenhouse", slug="relativity", link="https://job-boards.greenhouse.io/relativity")
    return Detection(board="lever", slug=name.lower(), link=f"https://jobs.lever.co/{name.lower()}", postings=1,
                     internships=1, internship_titles=["Intern"])


def test_discover_skips_tracked_companies_before_and_after_detection():
    candidates = [candidate("Relativity, Inc."), candidate("Rel Space Corp"), candidate("Acme"),
                  candidate("Crashy"), candidate("Relativity Labs")]
    with patch.object(discovery_run, "detect", side_effect=fake_detect) as detect:
        records, skipped = discovery_run.discover(candidates, TrackedIndex(TRACKED), TODAY, workers=2)
    assert sorted(s["name"] for s in skipped) == ["Rel Space Corp", "Relativity, Inc."]
    assert "Relativity, Inc." not in [c.args[0] for c in detect.call_args_list]  # never crawled
    by_name = {r["name"]: r for r in records}
    assert by_name["Acme"]["row"] == "Acme,https://jobs.lever.co/acme,@lever"
    assert by_name["Crashy"]["reason"] == "detection failed: ValueError: odd page"
    # A similar name alone doesn't skip a company (its board differs); it is flagged.
    assert (by_name["Relativity Labs"]["similar_to"], by_name["Acme"]["similar_to"]) == ("Relativity", None)


def test_run_writes_the_report_and_keeps_first_seen(tmp_path):
    csv_path = tmp_path / "companies.csv"
    csv_path.write_text("Name,Link,ClassName\nRelativity,https://job-boards.greenhouse.io/relativity,@greenhouse\n")
    source = Static([candidate("Acme", "https://acme.com"), candidate("Relativity")])
    with patch.object(discovery_run, "detect", side_effect=fake_detect):
        discovery_run.run([source], tmp_path, csv_path, today="2026-11-01")
        source._candidates.append(candidate("Bolt", "https://bolt.dev"))
        data = discovery_run.run([source], tmp_path, csv_path, today=TODAY)
    seen = {r["name"]: (r["first_seen"], r["last_checked"]) for r in data["candidates"]}
    assert seen == {"Acme": ("2026-11-01", TODAY), "Bolt": (TODAY, TODAY)}
    assert data["stats"]["new"] == 1
    saved = json.loads((tmp_path / "candidates.json").read_text())
    assert saved["tracked"][0]["tracked_as"] == "Relativity"
    readme = (tmp_path / "README.md").read_text()
    assert "| **new** | [Bolt](https://bolt.dev)" in readme and "| **new** | [Acme]" not in readme


def test_readme_flags_a_similar_tracked_name():
    rec = record(candidate("Navier AI", "https://navier.ai"), board(3), TODAY)
    rec["similar_to"] = "Navier"
    readme = render(build([rec], [], ["yc"], TODAY))
    assert "[Navier AI](https://navier.ai) (tracked *Navier* is a similar name)" in readme
