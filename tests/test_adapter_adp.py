"""Tests for phlux/adapters/adp.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.adp import fetch, job_url, location

CID = "b0e24f83-6e4d-492d-9d6a-bc0fea197d6a"
URL = (f"https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html"
       f"?cid={CID}&ccId=19000101_000001&lang=en_US")
API = "https://workforcenow.adp.com/mascsr/default/careercenter/public/events/staffing/v1/job-requisitions"


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def where(city="", state="", short=None):
    entry = {"address": {"cityName": city, "countrySubdivisionLevel1": {"codeValue": state}, "postalCode": ""},
             "aliasNames": [], "nameCode": {}}
    if short is not None:
        entry["nameCode"]["shortName"] = short
    return entry


def job(item, external, title, places=None):
    return {
        "itemID": item,
        "requisitionTitle": title,
        "customFieldGroup": {"stringFields": [
            {"nameCode": {"codeValue": "ExternalJobID"}, "stringValue": external},
            {"nameCode": {"codeValue": "CareerCenterRefId"}},
        ]},
        "requisitionLocations": places if places is not None else [where("Houston", "TX", " Houston, TX, US")],
    }


def page(jobs, total):
    return {"jobRequisitions": jobs, "meta": {"startSequence": 0, "totalNumber": total}}


def test_registered():
    assert ADAPTERS["adp"] is fetch


def test_job_url_is_the_share_link():
    assert job_url(URL, "575114") == (
        f"https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html"
        f"?cid={CID}&ccId=19000101_000001&jobId=575114&lang=en_US")


def test_location_forms():
    assert location(job("1", "1", "A")) == "Houston, TX"
    assert location(job("1", "1", "A", [where(state="CA", short=" CA, US"), where(), where(state="AZ")])) \
        == "California +1"
    assert location(job("1", "1", "A", [where(), where()])) == ""
    assert location(job("1", "1", "A", [where(short="Deep Space Systems Inc, CO, US")])) \
        == "Deep Space Systems Inc, CO"
    houston = where("Houston", "TX", " Houston, TX, US")
    assert location(job("1", "1", "A", [houston, where("Greenbelt", "MD"), houston])) == "Houston, TX +1"


def test_reads_every_page_until_the_total():
    pages = [
        page([job("9207467720225_106", "575114", "Intern"),
              job("9207519358072_42", "575456", "Logistics &  Operations Engineer")], 3),
        page([job("9207469300448_26", "575203", "Senior Space Flight Engineer", [where(), where()])], 3),
    ]
    with patch("phlux.adapters.adp.PAGE_SIZE", 2), patch("phlux.adapters.adp.DELAY", 0), \
         patch("phlux.adapters.adp.get", side_effect=[response(p) for p in pages]) as get:
        postings = fetch(URL)
    assert [(p.id, p.title, p.location) for p in postings] == [
        ("adp:575114", "Intern", "Houston, TX"),
        ("adp:575456", "Logistics & Operations Engineer", "Houston, TX"),
        ("adp:575203", "Senior Space Flight Engineer", ""),
    ]
    assert postings[0].url.endswith("&jobId=575114&lang=en_US")
    assert [c.args[0] for c in get.call_args_list] == [API, API]
    params = [c.kwargs["params"] for c in get.call_args_list]
    assert [p["$skip"] for p in params] == ["0", "2"]
    assert params[0]["cid"] == CID and params[0]["ccId"] == "19000101_000001" and params[0]["lang"] == "en_US"


def test_a_short_first_page_still_reads_on():
    pages = [page([job("a", "1", "A")], 3), page([job("b", "2", "B"), job("c", "3", "C")], 3)]
    with patch("phlux.adapters.adp.PAGE_SIZE", 2), patch("phlux.adapters.adp.DELAY", 0), \
         patch("phlux.adapters.adp.get", side_effect=[response(p) for p in pages]):
        assert [p.id for p in fetch(URL)] == ["adp:1", "adp:2", "adp:3"]


def test_stops_on_an_empty_page():
    pages = [page([job("a", "1", "A")], 50), page([], 50)]
    with patch("phlux.adapters.adp.PAGE_SIZE", 1), patch("phlux.adapters.adp.DELAY", 0), \
         patch("phlux.adapters.adp.get", side_effect=[response(p) for p in pages]) as get:
        assert [p.id for p in fetch(URL)] == ["adp:1"]
    assert get.call_count == 2


def test_falls_back_to_the_item_id():
    raw = job("9207467720225_106", "", "Intern")
    with patch("phlux.adapters.adp.get", return_value=response(page([raw], 1))):
        [posting] = fetch(URL)
    assert posting.id == "adp:9207467720225_106" and posting.url == ""


def test_needs_a_cid():
    with pytest.raises(ValueError):
        fetch("https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?lang=en_US")


# ── MyJobs ────────────────────────────────────────────────────────────────────

MYJOBS = "https://myjobs.adp.com/fanuc/cx/job-listing"
SEARCH = "https://my.adp.com/myadp_prefix/mycareer/public/staffing/v1/job-requisitions"


def site(custom_filters=True, token="AQICAHtoken"):
    return {"domain": "fanuc", "orgoid": "G36B3N8NPGHCGC17", "myJobsToken": token,
            "settings": {"externalId": "324131", "enabledFeatures": {"customJobFilters": custom_filters}},
            "properties": {"myadpUrl": "https://my.adp.com"}}


def req(req_id, title, places, code="050202-Engineer"):
    return {"reqId": req_id, "jobTitle": code, "publishedJobTitle": title, "postingDate": "2026-11-11T14:49:15Z",
            "requisitionLocations": [
                {"address": {"country": {"codeValue": country}, "cityName": city,
                             "countrySubdivisionLevel1": {"codeValue": state}}, "postingIndicator": True}
                for city, state, country in places]}


def test_myjobs_reads_the_site_then_searches_once():
    jobs = {"count": 2, "jobRequisitions": [
        req("5001234535106", "Process  Engineer", [("Rochester Hills", "MI", "USA")]),
        req("5001232866406", "Senior Accountant", [("Mississauga", "ON", "CAN"), ("Rochester Hills", "MI", "USA")]),
    ]}
    with patch("phlux.adapters.adp.get", side_effect=[response(site()), response(jobs)]) as get:
        postings = fetch(MYJOBS)
    assert [(p.id, p.title, p.location, p.url) for p in postings] == [
        ("adp:5001234535106", "Process Engineer", "Rochester Hills, MI",
         "https://myjobs.adp.com/fanuc/cx/job-details?reqId=5001234535106"),
        ("adp:5001232866406", "Senior Accountant", "Mississauga, Canada +1",
         "https://myjobs.adp.com/fanuc/cx/job-details?reqId=5001232866406"),
    ]
    assert get.call_args_list[0].args == ("https://myjobs.adp.com/public/staffing/v1/career-site/fanuc",)
    search = get.call_args_list[1]
    assert search.args == (SEARCH + "/apply-custom-filters",)
    assert search.kwargs["headers"]["myJobsToken"] == "AQICAHtoken"
    assert search.kwargs["headers"]["Accept-Language"] == "en-US"
    assert "publishedJobTitle" in search.kwargs["params"]["$select"]
    assert "postingDate" in search.kwargs["params"]["$select"]
    assert search.kwargs["params"]["$top"] == "1000" and search.kwargs["params"]["$skip"] == "0"


def test_myjobs_plain_search_without_custom_filters():
    with patch("phlux.adapters.adp.get", side_effect=[response(site(custom_filters=False)),
                                                      response({"count": 0, "jobRequisitions": []})]) as get:
        assert fetch(MYJOBS) == []
    assert get.call_args_list[1].args == (SEARCH,)


def test_myjobs_falls_back_to_the_job_title():
    raw = req("1", None, [("Indianapolis", "IN", "")], code="Robotic/CNC Field Service Engineer")
    jobs = {"count": 1, "jobRequisitions": [raw]}
    with patch("phlux.adapters.adp.get", side_effect=[response(site()), response(jobs)]):
        [posting] = fetch(MYJOBS)
    assert posting.title == "Robotic/CNC Field Service Engineer" and posting.location == "Indianapolis, IN"


def test_myjobs_reads_on_when_the_count_is_larger():
    first = {"count": 3, "jobRequisitions": [req("1", "A", []), req("2", "B", [])]}
    second = {"count": 3, "jobRequisitions": [req("2", "B", []), req("3", "C", [])]}
    with patch("phlux.adapters.adp.get", side_effect=[response(site()), response(first), response(second)]) as get:
        assert [p.id for p in fetch(MYJOBS)] == ["adp:1", "adp:2", "adp:3"]
    assert get.call_args_list[2].kwargs["params"]["$skip"] == "2"


def test_myjobs_needs_a_token():
    with patch("phlux.adapters.adp.get", return_value=response(site(token=None))):
        with pytest.raises(ValueError):
            fetch(MYJOBS)
