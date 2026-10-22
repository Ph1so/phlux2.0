"""Tests for phlux/adapters/taleo.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

from phlux.adapters import ADAPTERS
from phlux.adapters.taleo import fetch, parse_results

BASE = "https://phf.tbe.taleo.net/phf01/ats/careers/v2/"
URL = BASE + "searchResults?org=ACME&cws=47"


def response(html):
    mock = MagicMock()
    mock.text = html
    return mock


def row(rid, title):
    return (f'<div class="oracletaleocwsv2-accordion-head-info"><h4 class="oracletaleocwsv2-head-title">'
            f'<a href="{BASE}viewRequisition?org=ACME&amp;cws=47&amp;rid={rid}" class="viewJobLink">{title}</a>'
            f'</h4><div>San Jose, CA</div></div>')


def page(rows, matched=None, next_href=None):
    total = (f'<div class="panel oracletaleocwsv2-totals-callout"><h3>Positions Matched</h3>'
             f'<span class="oracletaleocwsv2-panel-number">{matched}</span></div>') if matched is not None else ""
    nxt = f'<a class="jscroll-next" href="{next_href}">more</a>' if next_href else ""
    return f"<html><body>{total}<div class='scroll'>{''.join(rows)}{nxt}</div></body></html>"


def test_registered():
    assert ADAPTERS["taleo"] is fetch


def test_parse_titles_ids_and_count():
    postings, next_url, matched = parse_results(page([row(11510, " Computer Vision  Research Intern")], 2), URL)
    assert [(p.id, p.title) for p in postings] == [("taleo:11510", "Computer Vision Research Intern")]
    assert next_url is None and matched == 2


def test_follows_scroll_links():
    pages = [
        page([row(1, "A"), row(2, "B")], 3, "searchResults?org=ACME&cws=47&act=next&rowFrom=2"),
        page([row(3, "C")]),
    ]
    with patch("phlux.adapters.taleo.get", side_effect=[response(p) for p in pages]) as get:
        postings = fetch(URL)
    assert [p.id for p in postings] == ["taleo:1", "taleo:2", "taleo:3"]
    assert get.call_args_list[1].args == (BASE + "searchResults?org=ACME&cws=47&act=next&rowFrom=2",)


def test_stops_when_scroll_link_repeats_page():
    looping = page([row(1, "A")], 5, URL)
    with patch("phlux.adapters.taleo.get", return_value=response(looping)) as get:
        assert [p.id for p in fetch(URL)] == ["taleo:1"]
    assert get.call_count == 1


def test_no_jobs():
    with patch("phlux.adapters.taleo.get", return_value=response(page([], 0))):
        assert fetch(URL) == []
