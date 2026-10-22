"""Tests for phlux/adapters/janestreet.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.janestreet import DIRECTORY, MAIN, fetch, paramify, paramify_strict

OPEN_ROLES = "https://www.janestreet.com/join-jane-street/open-roles/"
JOBS = [
    {"id": 1, "position": "Quantitative Trader", "availability": "Summer Internship", "city": "NYC",
     "category": "Trading, Research, and Machine Learning", "team": "", "duration": "June-August"},
    {"id": 2, "position": "Sales & Trading", "availability": "Summer Internship", "city": "NYC",
     "category": "Institutional Sales and Trading", "team": None, "duration": "June-August"},
    {"id": 3, "position": "Quantitative Trader", "availability": "Summer Internship", "city": "LDN",
     "category": "Trading, Research, and Machine Learning", "team": "", "duration": "June-August"},
    {"id": 4, "position": "Software Engineer", "availability": "Full-Time: New Grad", "city": "NYC",
     "category": "Technology", "team": "", "duration": ""},
    {"id": 5, "position": "Accounting Coordinator", "availability": "Full-Time: Experienced", "city": "NYC",
     "category": "Finance and Operations", "team": "Accounting", "duration": ""},
    {"id": 6, "position": "Unlisted Intern", "availability": "Summer Internship", "city": "NYC",
     "category": "Technology", "team": "", "duration": "June-August"},
    {"id": 7, "position": "Co-op Engineer", "availability": "Winter Co-op", "city": "NYC",
     "category": "Technology", "team": "", "duration": "January-April"},
]
LISTED = ["1", "2", "3", "4", "5", "7"]


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def run(query):
    routes = {MAIN: JOBS, DIRECTORY: LISTED}
    with patch("phlux.adapters.janestreet.get", side_effect=lambda url, **kw: response(routes[url])):
        return fetch(OPEN_ROLES + query)


def test_registered():
    assert ADAPTERS["janestreet"] is fetch


def test_paramify():
    assert paramify("New York") == "new-york"
    assert paramify("Full-Time: New Grad") == "full-time-new-grad"
    assert paramify("Trading, Research, and Machine Learning") == "trading-research-and-machine-learning"
    assert paramify_strict("Quantitative Trader") == "quantitative-trader"


def test_internships_in_new_york():
    postings = run("?type=internship&location=new-york")
    # Unlisted ids are not on the page; titles are shown with & spelled out.
    assert [(p.id, p.title) for p in postings] == [
        ("janestreet:1", "Quantitative Trader"), ("janestreet:2", "Sales and Trading")]


def test_students_and_new_grads():
    assert [p.id for p in run("?type=students-and-new-grads&location=new-york")] == [
        "janestreet:1", "janestreet:2", "janestreet:4", "janestreet:7"]


def test_co_op_type():
    assert [p.id for p in run("?type=co-op")] == ["janestreet:7"]


def test_experienced_with_department():
    assert [p.id for p in run("?type=experienced-candidates&department=finance-and-operations")] == ["janestreet:5"]


def test_all_locations():
    assert [p.id for p in run("?type=internship&location=all-locations")] == ["janestreet:1", "janestreet:2", "janestreet:3"]


@pytest.mark.parametrize("query", ["?type=internship&location=newyork", "?type=internships", "?department=nope"])
def test_unknown_filter_value_is_refused(query):
    with pytest.raises(ValueError):
        run(query)
