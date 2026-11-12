"""Tests for phlux/adapters/directemployers.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

from phlux.adapters import ADAPTERS
from phlux.adapters.directemployers import API, api_request, fetch, slug

URL = "https://jobs.acme.com/locations/usa/jobs/?q=intern"


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def job(n, title="Intern", city="St. Louis", state="MO", country="United States"):
    guid = f"{n:032X}"
    return {"guid": guid, "title_exact": title, "title_slug": slug(title), "city_exact": city,
            "state_short_exact": state, "country_exact": country, "location_exact": f"{city}, {state}"}


def payload(jobs, page, pages, total):
    return {"jobs": jobs, "pagination": {"page": page, "total_pages": pages, "total": total, "page_size": 10}}


def test_registered():
    assert ADAPTERS["directemployers"] is fetch


def test_api_request_reads_query_and_location_path():
    assert api_request(URL + "&page=3&num_items=50") == ("jobs.acme.com", [("q", "intern"), ("location", "usa")])
    assert api_request("https://jobs.acme.com/jobs/?q=intern&location=Texas") == (
        "jobs.acme.com", [("q", "intern"), ("location", "Texas")])


def test_slug():
    assert slug("St. Louis, MO") == "st-louis-mo"


def test_pages_until_total_pages():
    pages = [payload([job(1, "SSP: Software Intern (T&I)"), job(2, "Co-Op", "Munich", "", "Germany")], 1, 2, 3),
             payload([job(3, "Research  Intern")], 2, 2, 3)]
    with patch("phlux.adapters.directemployers.get", side_effect=[response(p) for p in pages]) as get, \
            patch("phlux.adapters.directemployers.time.sleep"):
        postings = fetch(URL)
    assert [(p.title, p.location) for p in postings] == [
        ("SSP: Software Intern (T&I)", "St. Louis, MO"), ("Co-Op", "Munich, Germany"), ("Research Intern", "St. Louis, MO")]
    assert postings[0].id == "directemployers:" + f"{1:032X}"
    assert postings[0].url == f"https://jobs.acme.com/st-louis-mo/ssp-software-intern-t-i/{1:032X}/job/"
    first, second = get.call_args_list
    assert first.args == (API,)
    assert first.kwargs["params"] == [("q", "intern"), ("location", "usa"), ("page", "1")]
    assert first.kwargs["headers"]["X-Origin"] == "jobs.acme.com"
    assert second.kwargs["params"][-1] == ("page", "2")


def test_repeated_page_stops():
    same = payload([job(1)], 1, 5, 50)
    with patch("phlux.adapters.directemployers.get", side_effect=[response(same), response(same)]) as get, \
            patch("phlux.adapters.directemployers.time.sleep"):
        assert len(fetch(URL)) == 1
    assert get.call_count == 2


def test_skips_jobs_without_guid():
    bad = {"guid": "", "title_exact": "Intern"}
    with patch("phlux.adapters.directemployers.get", return_value=response(payload([bad, job(9)], 1, 1, 2))):
        assert [p.id for p in fetch(URL)] == ["directemployers:" + f"{9:032X}"]
