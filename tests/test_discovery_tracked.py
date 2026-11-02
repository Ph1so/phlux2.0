"""Tests for phlux/discovery/tracked.py — skipping companies companies.csv already has."""
import json

from phlux.discovery.sources import Candidate
from phlux.discovery.tracked import TrackedIndex
from phlux.models import Company

COMPANIES = [
    Company("Relativity", "https://job-boards.greenhouse.io/relativity?keyword=intern", "@greenhouse"),
    Company("1x", "https://jobs.ashbyhq.com/1x", "@ashby->FILTER:intern"),
    Company("iRobot", "https://careers.irobot.com/search-jobs", "@talentbrew"),
    Company("Welch's", "https://job-boards.greenhouse.io/welchsinc?keyword=intern", "@greenhouse"),
    Company("Path Robotics", "https://jobs.lever.co/path-robotics", "@lever"),
    Company("Ambi Robotics", "https://jobs.lever.co/ambirobotics", "@lever"),
    Company("Hudson River Trading", "https://job-boards.greenhouse.io/embed/job_board?for=wehrtyou->"
            "https://job-boards.greenhouse.io/embed/job_board?for=wehrtyou&page=2", "@greenhouse"),
]


def index(active=("Relativity", "1x", "iRobot", "Path Robotics", "Ambi Robotics")):
    return TrackedIndex(COMPANIES, active)


def candidate(name, website="", former=()):
    return Candidate(name=name, website=website, source="yc", former_names=list(former))


def test_same_name():
    match = index().match(candidate("relativity", "https://www.relativityspace.com"))
    assert (match.tracked.name, match.why) == ("Relativity", "same name, 'relativity'")


def test_a_name_alike_without_suffixes_is_only_similar():
    # Not enough to skip: Navier AI (navier.ai) is not the tracked Navier boat maker.
    relativity = candidate("Relativity Space", "https://www.relativityspace.com")
    assert index().match(relativity) is None
    similar = index().similar(relativity)
    assert (similar.tracked.name, similar.why) == ("Relativity", "similar name, 'relativity'")


def test_legal_suffix_and_punctuation_are_ignored():
    assert index().match(candidate("Ambi Robotics, Inc.", "https://ambirobotics.com")).tracked.name == "Ambi Robotics"
    assert index().match(candidate("Welch’s")).tracked.name == "Welch's"


def test_same_domain_as_a_tracked_careers_site():
    match = index().match(candidate("Totally Renamed Co", "https://www.irobot.com"))
    assert (match.tracked.name, match.why) == ("iRobot", "same domain, irobot.com")


def test_domain_label_equal_to_a_tracked_board_slug():
    match = index().match(candidate("1X Technologies", "https://www.1x.tech"))
    assert match.tracked.name == "1x"
    assert match.why == "its name or domain is the board slug '1x'"


def test_former_names_count():
    match = index().match(candidate("Hudson Labs", "https://hudson.example", former=["Hudson River Trading"]))
    assert match.tracked.name == "Hudson River Trading"


def test_short_cores_do_not_collide():
    # PathAI (pathology) is not Path Robotics, though both cores are "path".
    assert index().match(candidate("PathAI", "https://www.pathai.com")) is None
    assert index().similar(candidate("PathAI", "https://www.pathai.com")) is None
    assert index().match(candidate("Acme Robotics", "https://acme.com")) is None


def test_job_board_hosts_are_not_company_domains():
    # A candidate whose "website" is a Greenhouse board must not match every Greenhouse row.
    assert index().match(candidate("Newco", "https://job-boards.greenhouse.io/newco")) is None


def test_match_board_catches_what_names_missed():
    match = index().match_board("greenhouse", "WelchsInc")
    assert (match.tracked.name, match.why) == ("Welch's", "same greenhouse board, 'WelchsInc'")
    assert index().match_board("greenhouse", "wehrtyou").tracked.name == "Hudson River Trading"
    assert index().match_board("lever", "relativity") is None


def test_active_list_membership():
    assert index().match(candidate("Relativity")).tracked.listed
    assert not index().match(candidate("Welch's")).tracked.listed
    assert TrackedIndex(COMPANIES).match(candidate("Welch's")).tracked.listed  # no list: everything is scraped


def test_load_reads_the_csv_and_the_configured_list(tmp_path, monkeypatch):
    csv_path = tmp_path / "companies.csv"
    csv_path.write_bytes(b"Name,Link,ClassName\r\nAcme,https://jobs.lever.co/acme,@lever\r\n"
                         b"Bolt,https://jobs.ashbyhq.com/bolt,@ashby\n")
    lists = tmp_path / "lists"
    lists.mkdir()
    (lists / "robots.json").write_text(json.dumps({"companies": ["Acme"]}))
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"COMPANY_LIST": str(lists / "robots.json")}))
    tracked = TrackedIndex.load(csv_path, config)
    assert tracked.match(candidate("Acme")).tracked.listed
    assert not tracked.match(candidate("Bolt")).tracked.listed
