"""Tests for phlux/adapters/ibm.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.ibm import API, PAGE_SIZE, fetch, filters, ibm_place, search_body

URL = "https://www.ibm.com/careers/search?field_keyword_18[0]=Internship&field_keyword_05[0]=United%20States"


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def hits(ids, total):
    return {"hits": {"total": {"value": total, "relation": "eq"}, "hits": [
        {"_id": f"doc{i}", "_source": {"title": f"Intern  {i}", "url": f"https://careers.ibm.com/careers/JobDetail?jobId={i}",
                                       "field_keyword_19": "POUGHKEEPSIE, US"}}
        for i in ids]}}


def test_registered():
    assert ADAPTERS["ibm"] is fetch


def test_filters_read_facets():
    url = URL + "&field_keyword_08[0]=Research&field_keyword_08[1]=Software%20Engineering&foo=bar"
    assert filters(url) == {
        "field_keyword_18": ["Internship"],
        "field_keyword_05": ["United States"],
        "field_keyword_08": ["Research", "Software Engineering"],
    }


def test_search_body_terms_and_stable_sort():
    body = search_body({"field_keyword_18": ["Internship"], "field_keyword_08": ["A", "B"]}, 100)
    assert body["post_filter"]["bool"]["must"] == [
        {"term": {"field_keyword_18": "Internship"}},
        {"terms": {"field_keyword_08": ["A", "B"]}},
    ]
    assert body["from"] == 100 and body["size"] == PAGE_SIZE
    assert body["sort"] == [{"_id": "asc"}]
    assert body["appId"] == "careers" and body["scopes"] == ["careers2"]


@pytest.mark.parametrize("raw, expected", [
    ("POUGHKEEPSIE, US", "Poughkeepsie"),
    ("Yorktown Heights, US", "Yorktown Heights"),
    ("RESEARCH TRIANGLE PARK, US", "Research Triangle Park"),
    ("Bangalore, IN", "Bangalore, India"),
    ("Multiple Cities", "Multiple Cities"),
    ("", ""),
])
def test_ibm_place(raw, expected):
    assert ibm_place(raw) == expected


def test_pages_until_total():
    pages = [hits(range(PAGE_SIZE), PAGE_SIZE + 1), hits([PAGE_SIZE], PAGE_SIZE + 1)]
    with patch("phlux.adapters.ibm.post", side_effect=[response(p) for p in pages]) as post, \
            patch("phlux.adapters.ibm.time.sleep"):
        postings = fetch(URL)
    assert len(postings) == PAGE_SIZE + 1
    first = postings[0]
    assert (first.id, first.title, first.location, first.url) == (
        "ibm:0", "Intern 0", "Poughkeepsie", "https://careers.ibm.com/careers/JobDetail?jobId=0")
    assert [c.args[0] for c in post.call_args_list] == [API, API]
    assert [c.kwargs["json"]["from"] for c in post.call_args_list] == [0, PAGE_SIZE]


def test_one_page_is_one_request():
    with patch("phlux.adapters.ibm.post", return_value=response(hits([1, 2], 2))) as post:
        assert [p.id for p in fetch(URL)] == ["ibm:1", "ibm:2"]
    assert post.call_count == 1


def test_empty_page_stops():
    with patch("phlux.adapters.ibm.post", return_value=response(hits([], 5))) as post:
        assert fetch(URL) == []
    assert post.call_count == 1
