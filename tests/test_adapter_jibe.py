"""Tests for phlux/adapters/jibe.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

from phlux.adapters import ADAPTERS
import pytest

from phlux.adapters.jibe import api_request, fetch, jobs_page

PAGE = "https://careers.acme.com/careers-home/jobs"
API = "https://careers.acme.com/api/jobs"


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def jobs(ids):
    return [{"data": {"req_id": str(i), "slug": str(i), "title": f"Intern  {i}"}} for i in ids]


def test_registered():
    assert ADAPTERS["jibe"] is fetch


def test_search_params_pass_through():
    url = PAGE + "?sortBy=relevance&page=3&limit=100&categories=Internships%20%26%20Early%20Career"
    assert api_request(url) == (API, [("sortBy", "relevance"), ("categories", "Internships & Early Career")])


def test_pages_from_one_until_total():
    pages = [{"totalCount": 101, "jobs": jobs(range(100))}, {"totalCount": 101, "jobs": jobs([100])}]
    with patch("phlux.adapters.jibe.get", side_effect=[response(p) for p in pages]) as get:
        postings = fetch(PAGE + "?categories=Interns")
    assert len(postings) == 101
    assert (postings[0].id, postings[0].title) == ("jibe:0", "Intern 0")
    assert postings[0].url == "https://careers.acme.com/careers-home/jobs/0"
    first, second = get.call_args_list
    assert first.args == (API,)
    assert first.kwargs["params"] == [("categories", "Interns"), ("page", "1"), ("limit", "100")]
    assert second.kwargs["params"][-2] == ("page", "2")
    assert get.call_count == 2


def test_falls_back_to_slug():
    payload = {"totalCount": 1, "jobs": [{"data": {"slug": "abc", "title": "Co-op"}}]}
    with patch("phlux.adapters.jibe.get", return_value=response(payload)):
        assert [(p.id, p.url) for p in fetch(PAGE)] == [("jibe:abc", "https://careers.acme.com/careers-home/jobs/abc")]


@pytest.mark.parametrize("url, expected", [
    (PAGE + "/?page=2", PAGE),
    ("https://jobs.acme.com/jobs?keywords=intern", "https://jobs.acme.com/jobs"),
    ("https://jobs.acme.com/search?keywords=intern", "https://jobs.acme.com/jobs"),
])
def test_job_pages_sit_under_the_search_page(url, expected):
    assert jobs_page(url) == expected


def test_no_jobs():
    with patch("phlux.adapters.jibe.get", return_value=response({"totalCount": 0, "jobs": []})) as get:
        assert fetch(PAGE) == []
    assert get.call_count == 1


def test_main_location_then_a_count_of_additional_ones():
    def place(city, state, code="US"):
        return {"city": city, "state": state, "country": "United States", "country_code": code}

    payload = {"totalCount": 4, "jobs": [
        {"data": {"req_id": "1", "title": "A", **place("Palo Alto", "California"),
                  "full_location": "Palo Alto, California", "multipleLocations": False}},
        {"data": {"req_id": "2", "title": "B", **place("Seattle", "Washington"), "multipleLocations": True,
                  "additional_locations": [place("Atlanta", "Georgia"), place("Allen", "Texas"),
                                           place("Seattle", "Washington")]}},
        {"data": {"req_id": "3", "title": "C", "city": "Munich", "state": "Bavaria", "country": "Germany",
                  "country_code": "DE"}},
        {"data": {"req_id": "4", "title": "D", "short_location": "Normal, Illinois; Irvine, California"}},
    ]}
    with patch("phlux.adapters.jibe.get", return_value=response(payload)):
        postings = fetch(PAGE)
    assert [p.location for p in postings] == ["Palo Alto, CA", "Seattle, WA +2", "Munich, Germany", "Normal, IL"]
