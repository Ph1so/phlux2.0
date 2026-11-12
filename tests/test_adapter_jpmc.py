"""Tests for phlux/adapters/jpmc.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.jpmc import fetch, program_ids, to_posting

ORIGIN = "https://www.jpmorganchase.com"
URL = f"{ORIGIN}/careers/explore-opportunities/programs/quant-fin-programs"
JOB = "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX/job/{}"


def page(*ids):
    cards = "".join(f'<div class="cmp-careers-apply-now hide " programId="{i}" id="first-apply-now-link"></div>'
                    for i in ids)
    return f"<html><body><h1>Quant programs</h1>{cards}</body></html>"


def response(text="", payload=None):
    mock = MagicMock()
    mock.text = text
    mock.json.return_value = payload
    return mock


def entry(number, name, locations):
    return {"name": name, "region": "Asia Pacific", "country": "SG", "locations": locations,
            "start_date": "2026-09-13T16:00:00+00:00", "end_date": "2026-11-29T15:59:00+00:00",
            "application_url": JOB.format(number), "level": "graduate"}


def serve(pages):
    def get(url, **kwargs):
        return pages[url]
    return get


def test_registered():
    assert ADAPTERS["jpmc"] is fetch


def test_reads_the_programs_gate():
    gate = f"{ORIGIN}/services/json/v1/careers/gate/programs.1320540457653.json"
    pages = {
        URL: response(page("1320540457653")),
        gate: response(payload={"1320540457653": [
            entry(210784061, "2027 Markets Quantitative Trading  & Research – Off-Cycle Internship - Singapore",
                  ["Singapore"]),
            entry(210773869, "2027 Data & AI Program - Summer Internship - Analyst - United States",
                  ["Chicago, IL, United States", "Columbus, OH, United States", "New York, NY, United States"]),
        ]}),
    }
    with patch("phlux.adapters.jpmc.get", side_effect=serve(pages)):
        postings = fetch(URL)
    assert [p.id for p in postings] == ["jpmc:210784061", "jpmc:210773869"]
    assert postings[0].title == "2027 Markets Quantitative Trading & Research – Off-Cycle Internship - Singapore"
    assert postings[0].location == "Singapore"
    assert postings[0].url == JOB.format(210784061)
    assert postings[1].location == "Chicago, IL +2"


def test_closed_program_has_no_postings():
    gate = f"{ORIGIN}/services/json/v1/careers/gate/programs.1320540459061.json"
    pages = {URL: response(page("1320540459061")), gate: response(payload={"1320540459061": []})}
    with patch("phlux.adapters.jpmc.get", side_effect=serve(pages)):
        assert fetch(URL) == []


def test_every_program_on_the_page_once():
    gates = {i: f"{ORIGIN}/services/json/v1/careers/gate/programs.{i}.json" for i in ("abc1", "def2")}
    pages = {
        URL: response(page("abc1", "def2", "abc1")),
        gates["abc1"]: response(payload={"abc1": [entry(1, "Intern A", ["Paris"])]}),
        gates["def2"]: response(payload={"def2": [entry(2, "Intern B", ["Zurich"]), entry(1, "Intern A", ["Paris"])]}),
    }
    with patch("phlux.adapters.jpmc.get", side_effect=serve(pages)) as get:
        postings = fetch(URL)
    assert [p.id for p in postings] == ["jpmc:1", "jpmc:2"]
    assert get.call_count == 3


def test_page_without_program_raises():
    with patch("phlux.adapters.jpmc.get", return_value=response("<html><body>Programs</body></html>")):
        with pytest.raises(ValueError):
            fetch(URL)


def test_answer_without_the_program_raises():
    gate = f"{ORIGIN}/services/json/v1/careers/gate/programs.abc1.json"
    pages = {URL: response(page("abc1")), gate: response(payload={"other": []})}
    with patch("phlux.adapters.jpmc.get", side_effect=serve(pages)):
        with pytest.raises(ValueError):
            fetch(URL)


def test_program_ids_skip_values_the_page_would_not_fetch():
    assert program_ids(page("1bf51922da13d70", "bad/../id", "")) == ["1bf51922da13d70"]


@pytest.mark.parametrize("application_url, key, url", [
    (JOB.format(210795339), "jpmc:210795339", JOB.format(210795339)),
    ("https://example.com/apply?id=7", "jpmc:https://example.com/apply?id=7", "https://example.com/apply?id=7"),
    ("", "jpmc:title:Working Student", ""),
])
def test_keys(application_url, key, url):
    posting = to_posting({"name": "Working  Student", "locations": ["Frankfurt a. Main"],
                          "application_url": application_url}, ORIGIN)
    assert (posting.id, posting.url, posting.location) == (key, url, "Frankfurt a. Main")


def test_entry_without_name_is_skipped():
    assert to_posting({"name": "", "application_url": JOB.format(1)}, ORIGIN) is None
