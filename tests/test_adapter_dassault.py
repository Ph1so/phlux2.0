"""Tests for phlux/adapters/dassault.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.dassault import API, PAGE_SIZE, fetch, filters, search_query, to_posting

URL = ("https://www.3ds.com/careers/jobs?woc=%257B%2522type%2522%253A%255B%2522type%252FInternship%2522%255D"
       "%252C%2522country%2522%253A%255B%2522country%252FUnited%2520States%2522%255D%257D")


def hit(card_id, title="INTERNSHIP - Data Science", where="United States, MA, Waltham"):
    metas = {"card_id": str(card_id), "content_title": title, "content_info_2_value": where,
             "content_cta_1_url": f"https://www.3ds.com/careers/jobs/internship-data-science-{card_id}"}
    return {"metas": [{"name": k, "value": v} for k, v in metas.items()] + [{"name": "meta_cat", "value": "x"}]}


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def test_registered():
    assert ADAPTERS["dassault"] is fetch


def test_filters_from_the_twice_encoded_woc():
    assert filters(URL) == {"type": ["type/Internship"], "country": ["country/United States"]}
    assert filters("https://www.3ds.com/careers/jobs") == {}


def test_unreadable_woc_raises():
    with pytest.raises(ValueError):
        filters("https://www.3ds.com/careers/jobs?woc=%257Bnot-json")


def test_search_query():
    assert search_query(URL) == ('card_content_lang:en (card_content_type="career") card_content_categories:'
                                 '(("type/Internship") AND ("country/United States"))')
    assert search_query("https://www.3ds.com/de/careers/jobs?wockw=solidworks") == (
        'card_content_lang:de (card_content_type="career") (solidworks)')


@pytest.mark.parametrize("where, expected", [
    ("United States, MA, Waltham", "Waltham, MA"),
    ("France, Vélizy-Villacoublay", "Vélizy-Villacoublay, France"),
    ("United States, MA, Waltham; United States, CA, San Diego", "Waltham, MA +1"),
])
def test_posting(where, expected):
    posting = to_posting(hit(550524, where=where))
    assert posting.id == "dassault:550524"
    assert posting.title == "INTERNSHIP - Data Science"
    assert posting.url == "https://www.3ds.com/careers/jobs/internship-data-science-550524"
    assert posting.location == expected


def test_sends_the_query_and_pages():
    total = PAGE_SIZE + 1
    pages = [{"nhits": total, "hits": [hit(i) for i in range(PAGE_SIZE)]}, {"nhits": total, "hits": [hit(PAGE_SIZE)]}]
    with patch("phlux.adapters.dassault.get", side_effect=[response(p) for p in pages]) as get, \
            patch("phlux.adapters.base.time.sleep"):
        postings = fetch(URL)
    assert len(postings) == total
    assert get.call_args_list[0].args[0] == API
    params = get.call_args_list[1].kwargs["params"]
    assert params["q"].startswith("#all card_content_lang:en") and params["b"] == PAGE_SIZE
    assert params["hf"] == PAGE_SIZE and params["output_format"] == "json"


def test_no_hits():
    with patch("phlux.adapters.dassault.get", return_value=response({"nhits": 0, "hits": []})) as get:
        assert fetch(URL) == []
    assert get.call_count == 1


def test_unexpected_answer_raises():
    with patch("phlux.adapters.dassault.get", return_value=response({"error": "x"})):
        with pytest.raises(ValueError):
            fetch(URL)
