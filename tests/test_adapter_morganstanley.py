"""Tests for phlux/adapters/morganstanley.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.morganstanley import API, fetch, location, to_posting

URL = "https://www.morganstanley.com/careers/career-opportunities-search?opportunity=sg#"


def job(number, title="2027 Technology Summer Analyst Program (New York)", city="New York",
        state="New York", country="United States of America"):
    return {"jobNumber": number, "jobTitle": title, "city": city, "allState": state, "country": country,
            "level3": city, "url": f"https://morganstanley.tal.net/vx/candidate/so/pm/1/pl/1/opp/{number}"}


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def test_registered():
    assert ADAPTERS["morganstanley"] is fetch


def test_posting():
    posting = to_posting(job("21558", "2027 Internal Audit  Internship Program (Budapest)", "Budapest",
                             "Budapest", "Hungary"))
    assert posting.id == "morganstanley:21558"
    assert posting.title == "2027 Internal Audit Internship Program (Budapest)"
    assert posting.location == "Budapest, Hungary"
    assert posting.url == "https://morganstanley.tal.net/vx/candidate/so/pm/1/pl/1/opp/21558"


def test_us_location_and_several_states():
    assert location(job("1")) == "New York, NY"
    assert location(job("1", state="New York, Georgia")) == "New York"


def test_sends_the_url_opportunity():
    payload = {"status": 200, "msg": "SUCCESS", "totalResults": 2, "resultSet": [job("1"), job("2")]}
    with patch("phlux.adapters.morganstanley.get", return_value=response(payload)) as get:
        postings = fetch(URL)
    assert [p.id for p in postings] == ["morganstanley:1", "morganstanley:2"]
    assert get.call_args.args[0] == API
    assert get.call_args.kwargs["params"] == {"opportunity": "sg", "lang": "en"}


def test_count_mismatch_is_logged(caplog):
    payload = {"status": 200, "totalResults": 3, "resultSet": [job("1")]}
    with patch("phlux.adapters.morganstanley.get", return_value=response(payload)):
        assert len(fetch(URL)) == 1
    assert "lists 3" in caplog.text


def test_unexpected_answer_raises():
    with patch("phlux.adapters.morganstanley.get", return_value=response({"status": 500, "msg": "ERROR"})):
        with pytest.raises(ValueError):
            fetch(URL)
