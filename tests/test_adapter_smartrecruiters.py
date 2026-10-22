"""Tests for phlux/adapters/smartrecruiters.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.smartrecruiters import api_request, fetch

API = "https://api.smartrecruiters.com/v1/companies/Acme/postings"


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def test_registered():
    assert ADAPTERS["smartrecruiters"] is fetch


def test_api_url_params_pass_through():
    url = (API + "?country=us&custom_field.111=aaa,bbb&custom_field.222=ccc&limit=5&offset=10")
    assert api_request(url) == (API, [
        ("country", "us"),
        ("custom_field.111", "aaa,bbb"),
        ("custom_field.222", "ccc"),
    ])


@pytest.mark.parametrize("url", [
    "https://careers.smartrecruiters.com/Acme?search=intern",
    "https://jobs.smartrecruiters.com/Acme/?search=intern",
])
def test_career_page_search_becomes_q(url):
    assert api_request(url) == (API, [("q", "intern")])


@pytest.mark.parametrize("url", [
    "https://careers.acme.com/jobs",
    "https://api.smartrecruiters.com/v1/postings",
])
def test_other_urls_refused(url):
    with pytest.raises(ValueError):
        api_request(url)


def test_pages_by_offset_until_total():
    pages = [
        {"totalFound": 101, "content": [{"id": str(n), "name": f"Intern  {n}"} for n in range(100)]},
        {"totalFound": 101, "content": [{"id": "100", "name": "Last Intern "}]},
    ]
    with patch("phlux.adapters.smartrecruiters.get", side_effect=[response(p) for p in pages]) as get:
        postings = fetch(API + "?country=us")
    assert len(postings) == 101
    assert (postings[0].id, postings[0].title) == ("smartrecruiters:0", "Intern 0")
    assert postings[-1].title == "Last Intern"
    assert get.call_count == 2
    first, second = get.call_args_list
    assert first.args == (API,)
    assert first.kwargs["params"] == [("country", "us"), ("limit", "100"), ("offset", "0")]
    assert second.kwargs["params"][-1] == ("offset", "100")


def test_empty_board():
    with patch("phlux.adapters.smartrecruiters.get", return_value=response({"totalFound": 0, "content": []})) as get:
        assert fetch(API) == []
    assert get.call_count == 1
