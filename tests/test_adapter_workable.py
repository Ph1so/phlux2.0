"""Tests for phlux/adapters/workable.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.workable import fetch, search_body

API = "https://apply.workable.com/api/v3/accounts/acme/jobs"
EMPTY = {"query": "", "location": [], "department": [], "worktype": [], "workplace": [], "remote": []}


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def test_registered():
    assert ADAPTERS["workable"] is fetch


def test_body_from_board_filters():
    url = "https://apply.workable.com/acme/?query=intern&department=12&worktype=full&workplace=remote"
    assert search_body(url) == {**EMPTY, "query": "intern", "department": [12],
                                "worktype": ["full"], "workplace": ["remote"]}


def test_location_filter_refused():
    with pytest.raises(ValueError):
        search_body("https://apply.workable.com/acme/?location=US")


def test_pages_with_next_page_token():
    pages = [
        {"total": 2, "results": [{"shortcode": "AAA", "title": "Engineer"}], "nextPage": "tok"},
        {"total": 2, "results": [{"shortcode": "BBB", "title": "Research Intern"}]},
    ]
    with patch("phlux.adapters.workable.post", side_effect=[response(p) for p in pages]) as post:
        postings = fetch("https://apply.workable.com/acme/")
    assert [(p.id, p.title, p.url) for p in postings] == [
        ("workable:AAA", "Engineer", "https://apply.workable.com/acme/j/AAA/"),
        ("workable:BBB", "Research Intern", "https://apply.workable.com/acme/j/BBB/"),
    ]
    first, second = post.call_args_list
    assert first.args == (API,) and first.kwargs["json"] == EMPTY
    assert second.kwargs["json"] == {**EMPTY, "token": "tok"}


def test_empty_board():
    with patch("phlux.adapters.workable.post", return_value=response({"total": 0, "results": []})) as post:
        assert fetch("https://apply.workable.com/acme") == []
    assert post.call_count == 1


def where(city, region, country="United States", code="US", **extra):
    return {"city": city, "region": region, "country": country, "countryCode": code, **extra}


@pytest.mark.parametrize("job, expected", [
    ({"location": where("Fremont", "California"), "locations": [where("Fremont", "California", hidden=False)]},
     "Fremont, CA"),
    ({"location": where("Fremont", "California"),
      "locations": [where("Fremont", "California"), where("Guangzhou", "Guangdong", "China", "CN"),
                    where("Austin", "Texas", hidden=True)]}, "Fremont, CA +1"),
    ({"location": where("Munich", "Bavaria", "Germany", "DE")}, "Munich, Germany"),
    ({"location": where("", "", "United States", "US"), "remote": True, "workplace": "remote"}, "Remote"),
    ({"location": None}, ""),
])
def test_location(job, expected):
    payload = {"total": 1, "results": [{"shortcode": "AAA", "title": "Intern", **job}]}
    with patch("phlux.adapters.workable.post", return_value=response(payload)):
        assert fetch("https://apply.workable.com/acme/")[0].location == expected
