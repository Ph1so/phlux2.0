"""Tests for phlux/adapters/phenom.py (HTTP mocked)."""
import json
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.phenom import PAGE_SIZE, close_enough, fetch, location, parse_page, slug, to_posting

URL = "https://careers.acme.com/us/en/search-results?keywords=intern"
APP = {
    "widgetApiEndpoint": "https://careers.acme.com/widgets", "country": "us", "deviceType": "desktop",
    "locale": "en_us", "refNum": "ACMEUS", "baseUrl": "https://careers.acme.com/us/en/",
    "pageName": "search-results", "siteType": "external", "pageId": "page15",
}


def job(i, title="Software Intern", where="San Jose, California, United States of America", others=None):
    return {"jobId": f"R{i}", "reqId": f"R{i}", "jobSeqNo": f"ACMEUSR{i}EXTERNALENUS", "title": title,
            "location": where, "multi_location": others if others is not None else [where],
            "city": "San Jose", "state": "California", "country": "United States of America"}


def page(jobs, total, keywords="intern", selections=None, page_type="default"):
    ddo = {"siteConfig": {"status": "success"}, "eagerLoadRefineSearch": {
        "status": 200, "hits": len(jobs), "totalHits": total,
        "data": {"jobs": jobs, "aggregations": [], "keywords": keywords, "ui_selections": selections,
                 "locationData": {"placeVal": ""}, "subsearch": None}}}
    session = {"csrfToken": "x", "pageType": page_type, "from": "0", "pageName": "search-results"}
    return (f'<script>var phApp = phApp || {json.dumps(APP)}; phApp.ddo = {json.dumps(ddo)}; '
            f'phApp.experimentData = {{}};</script><script>phApp.sessionParams = {json.dumps(session)};</script>')


def response(html=None, payload=None):
    mock = MagicMock()
    mock.text = html
    mock.json.return_value = payload
    return mock


def answer(jobs, total):
    return {"refineSearch": {"status": 200, "hits": len(jobs), "totalHits": total, "data": {"jobs": jobs}}}


def test_registered():
    assert ADAPTERS["phenom"] is fetch


def test_parse_page_reads_the_search():
    search = parse_page(page([job(1)], 32, selections={"experienceLevel": ["University Intern"]}))
    assert search.api == "https://careers.acme.com/widgets"
    assert search.total == 32 and [j["jobId"] for j in search.jobs] == ["R1"]
    assert search.base_url == "https://careers.acme.com/us/en/"
    assert search.body["keywords"] == "intern"
    assert search.body["selected_fields"] == {"experienceLevel": ["University Intern"]}
    assert search.body["lang"] == "en_us" and search.body["pageId"] == "page15"
    assert search.body["size"] == PAGE_SIZE and not search.landing


@pytest.mark.parametrize("html", ["<html></html>", f"<script>var phApp = phApp || {json.dumps(APP)};</script>"])
def test_not_a_phenom_search_page(html):
    with pytest.raises(ValueError):
        parse_page(html)


def test_posting_id_link_and_location():
    posting = to_posting(job(170977, "2027 Intern - Adobe Sales Academy BDR", others=[
        "San Jose, California, United States of America", "Lehi, Utah, United States of America"]),
        "https://careers.acme.com/us/en/")
    assert posting.id == "phenom:R170977"
    assert posting.title == "2027 Intern - Adobe Sales Academy BDR"
    assert posting.url == "https://careers.acme.com/us/en/job/R170977/2027-Intern-Adobe-Sales-Academy-BDR"
    assert posting.location == "San Jose, CA +1"


def test_slug():
    assert slug("2027 MBA Intern – Product Manager") == "2027-MBA-Intern-Product-Manager"


@pytest.mark.parametrize("where, expected", [
    ("London, London, City of, United Kingdom", "London, United Kingdom"),
    ("Singapore, Central Singapore, Singapore", "Singapore"),
    ("Bogota, Capital District, Colombia", "Bogota, Colombia"),
    ("London, United Kingdom", "London, United Kingdom"),
])
def test_locations_abroad(where, expected):
    assert location({"location": where, "multi_location": [where]}) == expected


def test_location_from_fields_when_text_is_missing():
    assert location({"location": "", "city": "Bedford", "state": "Massachusetts",
                     "country": "United States of America"}) == "Bedford, MA"


def test_whole_result_on_the_page_needs_no_api():
    with patch("phlux.adapters.phenom.get", return_value=response(page([job(1), job(2)], 2))) as get, \
            patch("phlux.adapters.phenom.post") as post:
        postings = fetch(URL)
    assert [p.id for p in postings] == ["phenom:R1", "phenom:R2"]
    get.assert_called_once_with(URL)
    post.assert_not_called()


def test_longer_result_is_read_from_the_api_in_one_request():
    first_page = page([job(i) for i in range(10)], 12, selections={"country": ["United States of America"]})
    jobs = [job(i) for i in range(12)]
    with patch("phlux.adapters.phenom.get", return_value=response(first_page)), \
            patch("phlux.adapters.phenom.post", return_value=response(payload=answer(jobs, 12))) as post:
        postings = fetch(URL)
    assert len(postings) == 12
    body = post.call_args.kwargs["json"]
    assert post.call_args.args[0] == "https://careers.acme.com/widgets"
    assert body["from"] == 0 and body["keywords"] == "intern" and body["ddoKey"] == "refineSearch"
    assert body["selected_fields"] == {"country": ["United States of America"]}


def test_a_search_bigger_than_one_request_is_paged(caplog):
    total = PAGE_SIZE + 3
    first_page = page([job(i) for i in range(10)], total)
    answers = [answer([job(i) for i in range(PAGE_SIZE)], total),
               answer([job(i) for i in range(PAGE_SIZE, total)], total)]
    with patch("phlux.adapters.phenom.get", return_value=response(first_page)), \
            patch("phlux.adapters.phenom.post", side_effect=[response(payload=a) for a in answers]) as post, \
            patch("phlux.adapters.phenom.time.sleep"):
        postings = fetch(URL)
    assert len(postings) == total
    assert [c.kwargs["json"]["from"] for c in post.call_args_list] == [0, PAGE_SIZE]
    assert "narrow the link" in caplog.text


def test_an_api_answering_another_search_raises():
    landing = page([job(i) for i in range(10)], 11, page_type="landingPage")
    with patch("phlux.adapters.phenom.get", return_value=response(landing)), \
            patch("phlux.adapters.phenom.post", return_value=response(payload=answer([job(1)], 45))):
        with pytest.raises(ValueError, match="landing page"):
            fetch(URL)


def test_unexpected_api_answer_raises():
    first_page = page([job(i) for i in range(10)], 12)
    with patch("phlux.adapters.phenom.get", return_value=response(first_page)), \
            patch("phlux.adapters.phenom.post", return_value=response(payload={"error": "nope"})):
        with pytest.raises(ValueError):
            fetch(URL)


def test_totals_drift_a_little():
    assert close_enough(32, 33) and close_enough(400, 430)
    assert not close_enough(4, 45)
