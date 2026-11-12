"""Tests for phlux/adapters/bankofamerica.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.bankofamerica import CAMPUS_API, CAREERS_API, PAGE_SIZE, api_for, fetch, to_posting

URL = ("https://careers.bankofamerica.com/en-us/students/job-search"
       "?ref=search&rows=24&search=jobsByLocation&searchstring=United+States")


def job(i, title="Global Markets Summer Analyst Program - 2027", others=""):
    return {"jobRequisitionId": str(i), "postingTitle": title, "city": "New York", "state": "New York",
            "country": "United States", "additionalLocations": others,
            "jcrURL": f"/en-us/students/job-detail/{i}/global-markets-summer-analyst-program-2027"}


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def test_registered():
    assert ADAPTERS["bankofamerica"] is fetch


def test_students_and_careers_searches_use_their_servlets():
    assert api_for(URL) == CAMPUS_API
    assert api_for("https://careers.bankofamerica.com/en-us/job-search?search=getAllJobs") == CAREERS_API


def test_posting():
    posting = to_posting(job(13930, others="Chicago, Illinois, United States; New York, New York, United States; "
                                           "Houston, Texas, United States; "))
    assert posting.id == "bankofamerica:13930"
    assert posting.url == ("https://careers.bankofamerica.com/en-us/students/job-detail/13930/"
                           "global-markets-summer-analyst-program-2027")
    assert posting.location == "New York, NY +2"


def test_sends_the_search_and_pages():
    pages = [{"jobsList": [job(i) for i in range(PAGE_SIZE)], "totalMatches": PAGE_SIZE + 1},
             {"jobsList": [job(PAGE_SIZE)], "totalMatches": PAGE_SIZE + 1}]
    with patch("phlux.adapters.bankofamerica.get", side_effect=[response(p) for p in pages]) as get, \
            patch("phlux.adapters.base.time.sleep"):
        postings = fetch(URL)
    assert len(postings) == PAGE_SIZE + 1
    assert get.call_args_list[0].args[0] == CAMPUS_API
    params = dict(get.call_args_list[1].kwargs["params"])
    assert params == {"search": "jobsByLocation", "searchstring": "United States",
                      "start": str(PAGE_SIZE), "rows": str(PAGE_SIZE)}


def test_stops_at_the_total():
    with patch("phlux.adapters.bankofamerica.get",
               return_value=response({"jobsList": [job(1), job(2)], "totalMatches": 2})) as get:
        assert [p.id for p in fetch(URL)] == ["bankofamerica:1", "bankofamerica:2"]
    assert get.call_count == 1


def test_empty_search():
    with patch("phlux.adapters.bankofamerica.get", return_value=response({"jobsList": [], "totalMatches": 0})):
        assert fetch(URL) == []


def test_unexpected_answer_raises():
    with patch("phlux.adapters.bankofamerica.get", return_value=response({"error": "x"})):
        with pytest.raises(ValueError):
            fetch(URL)
