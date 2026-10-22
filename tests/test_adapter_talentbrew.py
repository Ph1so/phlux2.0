"""Tests for phlux/adapters/talentbrew.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.talentbrew import fetch, page_url, parse_results

URL = "https://careers.acme.com/search-jobs?k=intern"


def response(html):
    mock = MagicMock()
    mock.text = html
    return mock


def page(jobs, total, pages, keywords="intern", current=1):
    items = "".join(
        f'<li><a data-job-id="{i}" href="/job/x/{i}"><h2>{t}</h2><span class="job-location">Bedford, MA</span></a>'
        f'<button class="js-save-job-btn" data-job-id="{i}">Save</button></li>'
        for i, t in jobs
    )
    return (f'<section id="search-results" data-keywords="{keywords}" data-location="" '
            f'data-total-results="{total}" data-total-pages="{pages}" data-current-page="{current}" '
            f'data-records-per-page="2"><ul id="search-results-list">{items}</ul></section>')


def test_registered():
    assert ADAPTERS["talentbrew"] is fetch


def test_page_url():
    assert page_url(URL, 1) == URL
    assert page_url(URL + "&p=7", 3) == URL + "&p=3"


def test_parse_titles_ids_and_pages():
    postings, scope, pages = parse_results(page([(101, "Associate  GTM Manager")], 1, 1))
    assert [(p.id, p.title) for p in postings] == [("talentbrew:101", "Associate GTM Manager")]
    assert pages == 1 and scope["data-keywords"] == "intern"


def test_span_title_markup():
    html = ('<section id="search-results" data-total-results="1" data-records-per-page="15">'
            '<a data-job-id="9" href="/job/9"><span class="search-results__job-title">Commercial Intern</span></a>'
            '<span class="location">UK</span></section>')
    postings, _, pages = parse_results(html)
    assert [p.title for p in postings] == ["Commercial Intern"] and pages == 1


def test_not_a_talentbrew_page():
    with pytest.raises(ValueError):
        parse_results("<html></html>")


def test_reads_all_pages():
    pages = [page([(1, "A"), (2, "B")], 3, 2), page([(3, "C")], 3, 2, current=2)]
    with patch("phlux.adapters.talentbrew.get", side_effect=[response(p) for p in pages]) as get:
        postings = fetch(URL)
    assert [p.id for p in postings] == ["talentbrew:1", "talentbrew:2", "talentbrew:3"]
    assert [c.args[0] for c in get.call_args_list] == [URL, URL + "&p=2"]


def test_stops_when_a_page_loses_the_search():
    pages = [page([(1, "A"), (2, "B")], 3, 2), page([(8, "Other")], 900, 450, keywords="")]
    with patch("phlux.adapters.talentbrew.get", side_effect=[response(p) for p in pages]):
        assert [p.id for p in fetch(URL)] == ["talentbrew:1", "talentbrew:2"]


def test_total_drift_is_tolerated():
    pages = [page([(1, "A"), (2, "B")], 60, 2), page([(3, "C")], 59, 2)]
    with patch("phlux.adapters.talentbrew.get", side_effect=[response(p) for p in pages]):
        assert len(fetch(URL)) == 3
