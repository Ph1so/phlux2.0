"""Write discovery's results: ``discovery/candidates.json`` and ``discovery/README.md``.

``candidates.json`` holds one record per candidate (what the source says, the
board found or why none was, and when it was first seen), plus the candidates
skipped as already tracked. ``README.md`` is the same, for reading on GitHub:
companies with internships open first, then those with a board, then boards
guessed from the name alone (to check by hand), then the unresolved, with
ready-to-paste ``companies.csv`` rows.

``first_seen`` is carried over from the previous ``candidates.json``, so a
company is marked new only in the run that first found it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from .detect import FILTER_ABOVE, Detection
from .names import name_key
from .sources import Candidate, candidate_key
from .tracked import Match

ACTIVE_LIST = "lists/robotics.json"
ONE_LINER_CHARS = 90


def record(candidate: Candidate, detection: Detection, today: str) -> dict:
    """Return the JSON record of one checked candidate (``first_seen`` is set by :func:`stamp`)."""
    return {
        "name": candidate.name,
        "website": candidate.website,
        "source": candidate.source,
        "focus": candidate.focus,
        "one_liner": candidate.one_liner,
        "tags": candidate.tags,
        "lists": candidate.matched,
        "batch": candidate.batch,
        "locations": candidate.locations,
        "yc_hiring": candidate.hiring,
        "yc_url": candidate.yc_url or None,
        "board": detection.board or None,
        "link": detection.link or None,
        "row": detection.row(candidate.name) if detection.found else None,
        "verified": detection.verified if detection.found else None,
        "postings": detection.postings,
        "internships": detection.internships,
        "internship_titles": detection.internship_titles,
        "evidence": detection.evidence or None,
        "reason": None if detection.found else detection.reason,
        "notes": detection.notes,
        "similar_to": None,
        "first_seen": today,
        "last_checked": today,
    }


def skipped_record(candidate: Candidate, match: Match) -> dict:
    """Return the JSON record of a candidate skipped because ``companies.csv`` already has it."""
    return {
        "name": candidate.name,
        "website": candidate.website,
        "tracked_as": match.tracked.name,
        "why": match.why,
        "in_active_list": match.tracked.listed,
    }


def load(path: Path) -> dict:
    """Return the previous run's data, or an empty run if there is none."""
    if not path.exists():
        return {"candidates": []}
    return json.loads(path.read_text(encoding="utf-8"))


def stamp(records: List[dict], previous: dict) -> None:
    """Carry each record's ``first_seen`` over from *previous*, matched by domain, then by name."""
    by_key: Dict[str, str] = {}
    by_name: Dict[str, str] = {}
    for old in previous.get("candidates", []):
        if old.get("first_seen"):
            by_key.setdefault(candidate_key(old["name"], old.get("website") or ""), old["first_seen"])
            by_name.setdefault(name_key(old["name"]), old["first_seen"])
    for rec in records:
        seen = by_key.get(candidate_key(rec["name"], rec.get("website") or "")) or by_name.get(name_key(rec["name"]))
        if seen and seen < rec["first_seen"]:
            rec["first_seen"] = seen


def build(records: List[dict], skipped: List[dict], sources: List[str], today: str) -> dict:
    """Return the whole ``candidates.json`` document, sorted so reruns diff cleanly."""
    records = sorted(records, key=lambda r: (r["name"].casefold(), r["website"]))
    skipped = sorted(skipped, key=lambda r: r["name"].casefold())
    verified = [r for r in records if r["board"] and r["verified"]]
    return {
        "generated": today,
        "sources": sources,
        "stats": {
            "considered": len(records) + len(skipped),
            "tracked": len(skipped),
            "with_board": len(verified),
            "with_internships": sum(1 for r in verified if r["internships"]),
            "name_only": sum(1 for r in records if r["board"] and not r["verified"]),
            "unresolved": sum(1 for r in records if not r["board"]),
            "new": sum(1 for r in records if r["first_seen"] == today),
        },
        "candidates": records,
        "tracked": skipped,
    }


def write(out_dir: Path, data: dict) -> None:
    """Write ``candidates.json`` and ``README.md`` into *out_dir*."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "candidates.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "README.md").write_text(render(data), encoding="utf-8")


# ── README ────────────────────────────────────────────────────────────────────


def _cell(text: Optional[str], limit: int = 0) -> str:
    text = " ".join(str(text or "").split()).replace("|", "\\|")
    return text[: limit - 1].rstrip() + "…" if limit and len(text) > limit else text


def _company(rec: dict) -> str:
    name = _cell(rec["name"])
    cell = f"[{name}]({rec['website']})" if rec.get("website") else name
    # A tracked row with a similar name may be this company under another name.
    return cell + (f" (tracked *{_cell(rec['similar_to'])}* is a similar name)" if rec.get("similar_to") else "")


def _new(rec: dict, today: str) -> str:
    return "**new**" if rec.get("first_seen") == today else ""


def _focus_rank(rec: dict) -> int:
    return 0 if rec.get("focus") == "robotics" else 1


def _rows_block(records: Iterable[dict]) -> List[str]:
    rows = [r["row"] for r in records if r.get("row")]
    return ["```csv", *rows, "```", ""] if rows else []


def render(data: dict) -> str:
    """Return the README for a run's data."""
    today = data["generated"]
    stats = data["stats"]
    records = data["candidates"]
    verified = [r for r in records if r["board"] and r["verified"]]
    interns = sorted((r for r in verified if r["internships"]),
                     key=lambda r: (-r["internships"], _focus_rank(r), r["name"].casefold()))
    boards = sorted((r for r in verified if not r["internships"]),
                    key=lambda r: (_focus_rank(r), -(r["postings"] or 0), r["name"].casefold()))
    guesses = sorted((r for r in records if r["board"] and not r["verified"]),
                     key=lambda r: (-(r["internships"] or 0), _focus_rank(r), r["name"].casefold()))
    unresolved = sorted((r for r in records if not r["board"]),
                        key=lambda r: (_focus_rank(r), r["name"].casefold()))
    lines = [
        "# Discovered companies",
        "",
        "Robotics and robotics-adjacent companies that phlux does not track yet, and the job board each",
        "one uses. Written by `python -m phlux.discovery` (weekly, `.github/workflows/discovery.yml`);",
        "the full data is in [`candidates.json`](candidates.json).",
        "",
        f"**Last run {today}:** {stats['considered']} candidates from {', '.join(data['sources'])} · "
        f"{stats['tracked']} already in `companies.csv` (skipped) · {stats['with_board']} with a job board "
        f"phlux can read · {stats['with_internships']} with internships open now · "
        f"{stats['name_only']} boards matched by name only · {stats['unresolved']} unresolved.",
        "",
        f"**new** marks companies first seen in this run ({stats['new']}).",
        "",
        "## Adding a company",
        "",
        "1. Paste its row into `companies.csv`.",
        f"2. Add its name to the active list, `{ACTIVE_LIST}`. The bot only scrapes companies in that list,",
        "   so a row in `companies.csv` alone is never read.",
        "3. Check `seed_new_companies` in `storage.json`: while it is false, the first scrape treats every",
        "   current posting as new (only internships are emailed).",
        "",
        "To check a company by hand: `python -m phlux.discovery detect <careers-or-company-url>`.",
        "To have one checked every run, add a `Name,website` line to [`seeds.txt`](seeds.txt).",
        f"Boards with more than {FILTER_ABOVE} postings get `->FILTER:intern` so storage keeps only internships.",
        "",
    ]
    lines += _board_section(f"With internships open ({len(interns)})", interns, today, examples=True)
    lines += _board_section(f"With a job board, no internships right now ({len(boards)})", boards, today)
    lines += _board_section(
        f"Matched by name only — check before adding ({len(guesses)})", guesses, today, examples=True,
        intro=["A board under the company's name exists, but nothing on it names the company's site,",
               "so it may belong to a same-name company. Open the board before pasting its row.", ""])
    lines += _unresolved_section(unresolved, today)
    lines += _tracked_section(data.get("tracked", []))
    return "\n".join(lines).rstrip() + "\n"


def _board_section(title: str, records: List[dict], today: str, examples: bool = False,
                   intro: Sequence[str] = ()) -> List[str]:
    lines = [f"## {title}", ""]
    if not records:
        return lines + ["None.", ""]
    lines += intro
    header = "| | Company | What they do | Focus | Board | Postings |"
    rule = "|---|---|---|---|---|---|"
    if examples:
        header += " Internships | Examples |"
        rule += "---|---|"
    lines += [header, rule]
    for r in records:
        row = (f"| {_new(r, today)} | {_company(r)} | {_cell(r['one_liner'], ONE_LINER_CHARS)} | {r['focus']} "
               f"| [{r['board']}]({r['link']}) | {r['postings']} |")
        if examples:
            row += f" {r['internships']} | {_cell('; '.join(r['internship_titles']), 140)} |"
        lines.append(row)
    lines.append("")
    return lines + _rows_block(records)


def _unresolved_section(records: List[dict], today: str) -> List[str]:
    lines = [f"## Unresolved ({len(records)})", ""]
    if not records:
        return lines + ["None.", ""]
    on_yc = sum(1 for r in records if _yc_jobs(r))
    lines += ["No board phlux can read was found. Some have none (small teams hiring by email);",
              "others use a job system phlux has no reader for, or block scripted visits.",
              f"{on_yc} say on YC that they are hiring; their YC jobs pages are linked.", "",
              "| | Company | What they do | Focus | Why |", "|---|---|---|---|---|"]
    lines += [f"| {_new(r, today)} | {_company(r)} | {_cell(r['one_liner'], ONE_LINER_CHARS)} | {r['focus']} "
              f"| {_cell(r['reason'], 160)}{_yc_jobs(r)} |" for r in records]
    return lines + [""]


def _yc_jobs(rec: dict) -> str:
    """Point at the company's YC jobs page when YC says it is hiring (phlux can't read those)."""
    if rec.get("yc_hiring") and rec.get("yc_url"):
        return f" · hiring on [YC]({rec['yc_url'].rstrip('/')}/jobs)"
    return ""


def _tracked_section(skipped: List[dict]) -> List[str]:
    lines = [f"## Already tracked ({len(skipped)})", "",
             "Skipped because they match a `companies.csv` row."]
    unlisted = [s for s in skipped if not s["in_active_list"]]
    if unlisted:
        lines += [f"These are in `companies.csv` but not in `{ACTIVE_LIST}`, so the bot never reads them:", ""]
        lines += [f"- {_cell(s['name'])} (row {_cell(s['tracked_as'])}: {_cell(s['why'])})" for s in unlisted]
    lines.append("")
    if skipped:
        lines += ["<details><summary>All skipped candidates</summary>", ""]
        lines += [f"- {_cell(s['name'])} → {_cell(s['tracked_as'])} ({_cell(s['why'])})" for s in skipped]
        lines += ["", "</details>", ""]
    return lines
