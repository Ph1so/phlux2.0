"""Tests for phlux/adapters/eightfold.py (HTTP mocked)."""
import json
from html import escape
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.eightfold import api_request, fetch, pcsx_filters, position_url, snake_case

OPTIONS = {
    "seniority": {"displayName": "Seniority", "options": {"labelMap": {"0": "Intern", "1": "Entry"}}},
    "jobType": {"displayName": "Job Type", "options": {"labelMap": {}}},
    "distance": {"displayName": "Distance", "options": None},
}


def pcsx_page(domain="acme.com", options=None):
    data = {"domain": domain, "configs": {"pcsxConfig": {"enabled": True, "searchOptionsMap": options or OPTIONS}}}
    return f'<html><body><div id="pcsx"></div><code id="pcsx-data" style="display:none;">{escape(json.dumps(data))}</code></body></html>'


def legacy_page(domain="acme.com"):
    return f'<html><body><code id="smartApplyData">{escape(json.dumps({"domain": domain, "positions": []}))}</code></body></html>'


def response(payload=None, text=""):
    mock = MagicMock()
    mock.json.return_value = payload
    mock.text = text
    return mock


def positions(start, count, total):
    return [{"id": n, "name": f"Intern  {n}", "positionUrl": f"/careers/job/{n}"}
            for n in range(start, min(start + count, total))]


def test_registered():
    assert ADAPTERS["eightfold"] is fetch


@pytest.mark.parametrize("key, expected", [
    ("seniority", "seniority"),
    ("jobType", "job_type"),
    ("workLocationOption", "work_location_option"),
    ("full/part-time", "full_part_time"),
])
def test_snake_case_like_lodash(key, expected):
    assert snake_case(key) == expected


def test_filters_by_key_display_name_and_label():
    params = {
        "seniority": ["Intern,Entry"],
        "Job Type": ["Regular"],
        "filter_department": ["Engineering"],
        "query": ["intern"],
        "triggerGoButton": ["true"],
    }
    assert pcsx_filters(params, OPTIONS) == [
        ("filter_seniority", "0"),
        ("filter_seniority", "1"),
        ("filter_job_type", "Regular"),
        ("filter_department", "Engineering"),
    ]


def test_pcsx_request_takes_domain_from_page():
    url = "https://careers.acme.com/careers?seniority=Intern&location=United%20States&sort_by=relevance&start=20"
    api, params, pcsx = api_request(url, pcsx_page("acme.com"))
    assert pcsx and api == "https://careers.acme.com/api/pcsx/search"
    assert params == [
        ("domain", "acme.com"),
        ("query", ""),
        ("location", "United States"),
        ("sort_by", "relevance"),
        ("filter_seniority", "0"),
    ]


def test_url_domain_wins():
    _, params, _ = api_request("https://jobs.acme.com/careers?domain=acme.io&query=intern", pcsx_page("acme.com"))
    assert params[:2] == [("domain", "acme.io"), ("query", "intern")]


def test_legacy_request_passes_url_params():
    url = 'https://jobs.acme.com/careers?domain=acme.com&query=%22internship%22%20-intern&pid=123&sort_by=relevance'
    api, params, pcsx = api_request(url, legacy_page())
    assert not pcsx and api == "https://jobs.acme.com/api/apply/v2/jobs"
    assert params == [("domain", "acme.com"), ("query", '"internship" -intern'), ("sort_by", "relevance")]


def test_not_an_eightfold_page():
    with pytest.raises(ValueError):
        api_request("https://acme.com/careers", "<html></html>")


@patch("phlux.adapters.base.time.sleep")
def test_pcsx_pages_until_count(sleep):
    url = "https://careers.acme.com/careers?seniority=Intern"
    calls = []

    def get(target, **kwargs):
        calls.append((target, kwargs))
        if target == url:
            return response(text=pcsx_page())
        start = int(dict(kwargs["params"])["start"])
        return response({"status": 200, "data": {"count": 12, "positions": positions(start, 10, 12)}})

    with patch("phlux.adapters.eightfold.get", side_effect=get):
        postings = fetch(url)
    assert [p.id for p in postings] == [f"eightfold:{n}" for n in range(12)]
    assert postings[0].title == "Intern 0"
    # positionUrl is relative to the careers site.
    assert postings[0].url == "https://careers.acme.com/careers/job/0"
    # The page, then two API pages; no third call once the count is reached.
    assert [c[0] for c in calls] == [url] + ["https://careers.acme.com/api/pcsx/search"] * 2
    assert [dict(c[1]["params"])["start"] for c in calls[1:]] == ["0", "10"]
    assert ("filter_seniority", "0") in calls[1][1]["params"]
    # One session carries the page's cookies to the API.
    assert len({id(c[1]["session"]) for c in calls}) == 1


@patch("phlux.adapters.base.time.sleep")
def test_legacy_reads_top_level_positions(sleep):
    url = "https://jobs.acme.com/careers?query=intern"

    def get(target, **kwargs):
        if target == url:
            return response(text=legacy_page())
        return response({"count": 1, "positions": [{
            "id": 7, "name": "Video Intern", "canonicalPositionUrl": "https://jobs.acme.com/careers/job/7"}]})

    with patch("phlux.adapters.eightfold.get", side_effect=get) as mock:
        postings = fetch(url)
    assert [(p.id, p.title, p.url) for p in postings] == [
        ("eightfold:7", "Video Intern", "https://jobs.acme.com/careers/job/7")]
    assert mock.call_args_list[1].args == ("https://jobs.acme.com/api/apply/v2/jobs",)
    assert mock.call_args_list[1].kwargs["params"] == [("domain", "acme.com"), ("query", "intern"), ("start", "0")]


@pytest.mark.parametrize("position, expected", [
    ({"id": 5, "positionUrl": "/careers/job/5"}, "https://careers.acme.com/careers/job/5"),
    ({"id": 5, "canonicalPositionUrl": "https://careers.acme.com/careers/job/5"},
     "https://careers.acme.com/careers/job/5"),
    # Without either, the page every Eightfold site uses for a position.
    ({"id": 5}, "https://careers.acme.com/careers/job/5"),
])
def test_position_url(position, expected):
    assert position_url("https://careers.acme.com", position) == expected


@patch("phlux.adapters.base.time.sleep")
def test_empty_search(sleep):
    url = "https://careers.acme.com/careers?query=zzz"

    def get(target, **kwargs):
        if target == url:
            return response(text=pcsx_page())
        return response({"data": {"count": 0, "positions": []}})

    with patch("phlux.adapters.eightfold.get", side_effect=get) as mock:
        assert fetch(url) == []
    assert mock.call_count == 2


@patch("phlux.adapters.base.time.sleep")
def test_locations_written_city_state_with_a_count(sleep):
    url = "https://careers.acme.com/careers?seniority=Intern"
    found = [
        {"id": 1, "name": "A", "locations": ["San Diego, California, United States of America"],
         "standardizedLocations": ["San Diego, CA, US"]},
        {"id": 2, "name": "B", "locations": ["San Diego, California, United States of America",
                                              "New Jersey, United States of America",
                                              "Santa Clara, California, United States of America"]},
        {"id": 3, "name": "C", "standardizedLocations": ["Boxborough, MA, US"]},
        {"id": 4, "name": "D", "locations": ["Munich, Bavaria, Germany"]},
        {"id": 5, "name": "E"},
    ]

    def get(target, **kwargs):
        if target == url:
            return response(text=pcsx_page())
        return response({"data": {"count": len(found), "positions": found}})

    with patch("phlux.adapters.eightfold.get", side_effect=get):
        postings = fetch(url)
    assert [p.location for p in postings] == [
        "San Diego, CA", "San Diego, CA +2", "Boxborough, MA", "Munich, Bavaria, Germany", ""]


@patch("phlux.adapters.base.time.sleep")
def test_legacy_location_comes_first(sleep):
    url = "https://jobs.acme.com/careers?query=intern"

    def get(target, **kwargs):
        if target == url:
            return response(text=legacy_page())
        return response({"count": 1, "positions": [{
            "id": 7, "name": "Video Intern", "location": "Boston, Massachusetts, United States",
            "locations": ["Austin, Texas, United States", "Boston, Massachusetts, United States"]}]})

    with patch("phlux.adapters.eightfold.get", side_effect=get):
        assert fetch(url)[0].location == "Boston, MA +1"
