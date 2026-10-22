"""Tests for phlux/adapters/apple.py (HTTP mocked)."""
import json
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qsl, urlsplit

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.apple import fetch, parse

URL = "https://jobs.apple.com/en-us/search?location=united-states-USA&team=internships-STDNT-INTRN"


def search_page(jobs, total):
    data = {"loaderData": {"search": {
        "searchResults": [{"id": jid, "positionId": jid.split("-")[0], "postingTitle": title} for jid, title in jobs],
        "totalRecords": total,
    }}}
    return f"<script>window.__staticRouterHydrationData = JSON.parse({json.dumps(json.dumps(data))});</script>"


def response(html):
    mock = MagicMock()
    mock.text = html
    return mock


def page_of(url):
    return int(dict(parse_qsl(urlsplit(url).query))["page"])


@pytest.fixture(autouse=True)
def no_sleep():
    with patch("phlux.adapters.apple.time.sleep"):
        yield


def test_registered():
    assert ADAPTERS["apple"] is fetch


def test_parse():
    postings, total = parse(search_page([("200-0157", "Software  Internships"), ("200-0836", "Software Internships")], 2))
    assert [(p.id, p.title) for p in postings] == [
        ("apple:200-0157", "Software Internships"), ("apple:200-0836", "Software Internships")]
    assert total == 2


def test_parse_without_data():
    with pytest.raises(ValueError):
        parse("<html></html>")


def test_reads_every_page():
    pages = {1: search_page([(f"{i}-1", f"Job {i}") for i in range(20)], 25),
             2: search_page([(f"{i}-1", f"Job {i}") for i in range(20, 25)], 25)}
    with patch("phlux.adapters.apple.get", side_effect=lambda url, **kw: response(pages[page_of(url)])) as get:
        postings = fetch(URL + "&page=3")
    assert len(postings) == 25
    assert [page_of(c.args[0]) for c in get.call_args_list] == [1, 2]
    assert "team=internships-STDNT-INTRN" in get.call_args_list[0].args[0]


def test_empty_answer_is_asked_again():
    answers = [response(search_page([], 0)), response(search_page([("1-1", "Intern")], 1))]
    with patch("phlux.adapters.apple.get", side_effect=answers):
        assert [p.id for p in fetch(URL)] == ["apple:1-1"]


def test_empty_search():
    with patch("phlux.adapters.apple.get", return_value=response(search_page([], 0))) as get:
        assert fetch(URL) == []
    assert get.call_count == 4


def test_later_page_empty_raises():
    pages = {1: search_page([(f"{i}-1", f"Job {i}") for i in range(20)], 25), 2: search_page([], 0)}
    with patch("phlux.adapters.apple.get", side_effect=lambda url, **kw: response(pages[page_of(url)])):
        with pytest.raises(RuntimeError):
            fetch(URL)
