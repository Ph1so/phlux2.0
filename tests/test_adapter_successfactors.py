"""Tests for phlux/adapters/successfactors.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.successfactors import fetch, format_location, page_url, parse_results

URL = "https://jobs.acme.com/acme/search/?q=&locationsearch=United+States&sortColumn=referencedate"


@pytest.fixture(autouse=True)
def no_sleep():
    with patch("phlux.adapters.successfactors.time.sleep"):
        yield


def response(html):
    mock = MagicMock()
    mock.text = html
    return mock


def table(jobs, total, first=1):
    """A table-template results page; *jobs* are (id, title, location) tuples."""
    rows = "".join(
        f'<tr class="data-row"><td class="colTitle">'
        f'<span class="jobTitle hidden-phone"><a class="jobTitle-link" href="/Acme/job/Town-{i}/{i}/">{t}</a></span>'
        f'<div class="jobdetail-phone"><a class="jobTitle-link" href="/Acme/job/Town-{i}/{i}/">{t}</a>'
        f'<span class="jobLocation visible-phone"><span class="jobLocation">{loc}</span></span></div></td>'
        f'<td class="colLocation"><span class="jobLocation">{loc}</span></td></tr>'
        for i, t, loc in jobs
    )
    last = first + len(jobs) - 1
    return (f'<span class="paginationLabel">Results <b>{first} – {last}</b> of <b>{total}</b></span>'
            f'<table id="searchresults"><tbody>{rows}</tbody></table>')


def tiles(jobs, total):
    """A tile-template results page, each tile repeating its fields per screen size."""
    def fields(i, t, loc):
        return (f'<a class="jobTitle-link" href="/job/Town-{i}/{i}/">{t}</a>'
                f'<div class="section-field location"><span class="section-label">Location</span>'
                f'<div id="job-{i}-desktop-section-location-value">{loc}</div></div>')
    items = "".join(f'<li class="job-tile job-id-{i}" data-url="/job/Town-{i}/{i}/">{fields(i, t, loc) * 3}</li>'
                    for i, t, loc in jobs)
    return (f'<div id="tile-search-results-label">Showing 1 to {len(jobs)} of {total} Jobs</div>'
            f'<ul id="job-tile-list">{items}</ul>')


NO_RESULTS = ('<div id="noresults">There are currently no open positions matching. The 10 most recent jobs '
              'are listed below.</div>' + tiles([(9, "Unrelated", "Augsburg, BY, DE")], 10))


def test_registered():
    assert ADAPTERS["successfactors"] is fetch


def test_page_url():
    assert page_url(URL, 0) == URL
    assert page_url(URL + "&startrow=50", 25) == URL + "&startrow=25"


@pytest.mark.parametrize("raw, expected", [
    ("North Reading, MA, US", "North Reading, MA"),
    ("San Jose, CA, US +1 more…", "San Jose, CA +1"),
    ("Atlanta, US", "Atlanta"),
    ("Augsburg, BY, DE", "Augsburg, Germany"),
    ("Redditch, GB", "Redditch, United Kingdom"),
    ("Remote", "Remote"),
    ("", ""),
])
def test_format_location(raw, expected):
    assert format_location(raw) == expected


def test_parse_table():
    html = table([(101, "Hardware Engineer, (Defense &amp; Aerospace)", 'San Jose, CA, US <small>+1 more…</small>')], 1)
    postings, total = parse_results(html, URL)
    assert total == 1
    [p] = postings
    assert (p.id, p.title, p.location) == ("successfactors:101", "Hardware Engineer, (Defense & Aerospace)",
                                           "San Jose, CA +1")
    assert p.url == "https://jobs.acme.com/Acme/job/Town-101/101/"


def test_parse_tiles_once_each():
    postings, total = parse_results(tiles([(7, "Field Service Engineer", "Shelby Township, MI, US"),
                                           (8, "Resident Engineer", "Redditch, GB")], 48), URL)
    assert total == 48
    assert [(p.id, p.location) for p in postings] == [("successfactors:7", "Shelby Township, MI"),
                                                     ("successfactors:8", "Redditch, United Kingdom")]
    assert postings[0].url == "https://jobs.acme.com/job/Town-7/7/"


def test_no_results_page_lists_nothing():
    assert parse_results(NO_RESULTS, URL) == ([], 0)


def test_not_a_successfactors_page():
    with pytest.raises(ValueError):
        parse_results("<html><body>Hello</body></html>", URL)


def test_reads_pages_up_to_the_total():
    pages = [table([(1, "A", "X, CA, US"), (2, "B", "X, CA, US")], 3), table([(3, "C", "X, CA, US")], 3, first=3)]
    with patch("phlux.adapters.successfactors.get", side_effect=[response(p) for p in pages]) as get:
        postings = fetch(URL)
    assert [p.id for p in postings] == ["successfactors:1", "successfactors:2", "successfactors:3"]
    assert [c.args[0] for c in get.call_args_list] == [URL, URL + "&startrow=2"]


def test_page_with_another_total_is_skipped_and_the_walk_repeated():
    walk1 = [table([(1, "A", ""), (2, "B", "")], 4), NO_RESULTS]
    walk2 = [table([(1, "A", ""), (2, "B", "")], 4), table([(3, "C", ""), (4, "D", "")], 4, first=3)]
    with patch("phlux.adapters.successfactors.get", side_effect=[response(p) for p in walk1 + walk2]) as get:
        postings = fetch(URL)
    assert [p.id for p in postings] == [f"successfactors:{i}" for i in (1, 2, 3, 4)]
    assert get.call_count == 4


def test_short_walks_keep_every_job_seen():
    # The sort order shifts: each walk repeats one job and misses another.
    walk1 = [table([(1, "A", ""), (2, "B", "")], 4), table([(2, "B", ""), (3, "C", "")], 4, first=3)]
    walk2 = [table([(1, "A", ""), (2, "B", "")], 4), table([(4, "D", ""), (2, "B", "")], 4, first=3)]
    with patch("phlux.adapters.successfactors.get", side_effect=[response(p) for p in walk1 + walk2]):
        postings = fetch(URL)
    assert sorted(p.id for p in postings) == [f"successfactors:{i}" for i in (1, 2, 3, 4)]


def test_gives_up_after_three_short_walks():
    walk = [table([(1, "A", ""), (2, "B", "")], 5), table([(2, "B", ""), (3, "C", "")], 5, first=3),
            table([(3, "C", "")], 5, first=5)]
    with patch("phlux.adapters.successfactors.get", side_effect=[response(p) for p in walk * 3]) as get:
        postings = fetch(URL)
    assert len(postings) == 3 and get.call_count == 9


def test_empty_search():
    with patch("phlux.adapters.successfactors.get", return_value=response(NO_RESULTS)) as get:
        assert fetch(URL) == []
    assert get.call_count == 1
