"""Tests for phlux/adapters/icims.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.icims import fetch, page_url, parse_results

PORTAL = "https://careers-acme.icims.com/jobs/search"


def response(html):
    mock = MagicMock()
    mock.text = html
    return mock


def row(job_id, title):
    return f"""
    <div class="row">
      <div class="col-xs-6 header left"><span class="sr-only field-label">Job Locations</span><span>US-CA</span></div>
      <div class="col-xs-12 title">
        <a class="iCIMS_Anchor" href="{PORTAL[:-7]}/{job_id}/slug/job?in_iframe=1" title="{job_id} - {title}">
          <span class="sr-only field-label">Title</span>
          <h3>
          {title}</h3>
        </a>
      </div>
    </div>"""


def results(rows, page, pages):
    return f"<html><body><div>Search Results Page {page} of {pages}</div>{''.join(rows)}</body></html>"


def test_registered():
    assert ADAPTERS["icims"] is fetch


def test_page_url_keeps_search_and_sets_iframe_view():
    url = PORTAL + "?ss=1&searchKeyword=intern&needsRedirect=false&in%5Fiframe=1&pr=4"
    assert page_url(url, 2) == PORTAL + "?ss=1&searchKeyword=intern&needsRedirect=false&in_iframe=1&pr=2"


def test_parse_heading_titles_and_ids():
    postings, pages = parse_results(results([row(5486, "Electrical Engineer - Intern (Summer 2027)")], 1, 3))
    assert [(p.id, p.title) for p in postings] == [("icims:5486", "Electrical Engineer - Intern (Summer 2027)")]
    assert pages == 3


def test_parse_plain_anchor_without_heading():
    html = f'<a class="iCIMS_Anchor" href="{PORTAL[:-7]}/12/x/job"><span class="sr-only">Title</span> Flight Test Intern </a>'
    postings, pages = parse_results(html)
    assert [(p.id, p.title) for p in postings] == [("icims:12", "Flight Test Intern")]
    assert pages is None


def test_parse_makes_relative_links_absolute():
    html = '<a class="iCIMS_Anchor" href="/jobs/12/flight-test-intern/job?mobile=false&amp;in_iframe=1"><h3>Intern</h3></a>'
    postings, _ = parse_results(html, PORTAL + "?in_iframe=1&pr=0")
    assert postings[0].url == "https://careers-acme.icims.com/jobs/12/flight-test-intern/job"


def test_reads_every_page_and_stops_at_count():
    pages = [results([row(1, "A"), row(2, "B")], 1, 2), results([row(3, "C")], 2, 2)]
    with patch("phlux.adapters.icims.get", side_effect=[response(p) for p in pages]) as get:
        postings = fetch(PORTAL + "?ss=1&searchKeyword=intern")
    assert [p.id for p in postings] == ["icims:1", "icims:2", "icims:3"]
    # The iframe view's in_iframe=1 is not part of the job's page.
    assert postings[0].url == "https://careers-acme.icims.com/jobs/1/slug/job"
    assert [c.args[0] for c in get.call_args_list] == [
        PORTAL + "?ss=1&searchKeyword=intern&in_iframe=1&pr=0",
        PORTAL + "?ss=1&searchKeyword=intern&in_iframe=1&pr=1",
    ]


def test_no_results():
    with patch("phlux.adapters.icims.get", return_value=response("<html><body>No jobs</body></html>")) as get:
        assert fetch(PORTAL) == []
    assert get.call_count == 1


def card(job_id, where):
    """A result as the job-card layout renders it, with its "Job Locations" field."""
    return f"""
    <li class="iCIMS_JobCardItem"><div class="row">
      <div class="col-xs-6 header left"><span class="sr-only field-label">Job Locations</span>
        <span>
        {where}</span></div>
      <div class="col-xs-12 title"><a class="iCIMS_Anchor" href="{PORTAL[:-7]}/{job_id}/slug/job">
        <span class="sr-only field-label">Title</span><h3>Intern {job_id}</h3></a></div>
      <div class="col-xs-12 additionalFields"><dl><dt class="iCIMS_JobHeaderField">Category</dt>
        <dd><span>Flight Test</span></dd></dl></div>
    </div></li>"""


@pytest.mark.parametrize("where, expected", [
    ("US-CA-San Carlos", "San Carlos, CA"),
    ("US-NC-Winston-Salem", "Winston-Salem, NC"),
    ("JP-13-Tokyo", "Tokyo, Japan"),
    ("DE-BY-Munich", "Munich, Germany"),
    ("US-CA", "California"),
    ("US-Remote", "Remote"),
    ("US-CA-Marina | US-CA-San Carlos", "Marina, CA +1"),
    ("Multiple Locations", "Multiple Locations"),
])
def test_location_codes_written_out(where, expected):
    postings, _ = parse_results(results([card(7, where)], 1, 1))
    assert postings[0].location == expected


def test_row_layout_location():
    postings, _ = parse_results(results([row(5486, "Intern")], 1, 1))
    assert postings[0].location == "California"


def test_no_location_field():
    html = f'<a class="iCIMS_Anchor" href="{PORTAL[:-7]}/12/x/job"><h3>Intern</h3></a>'
    assert parse_results(html)[0][0].location == ""
