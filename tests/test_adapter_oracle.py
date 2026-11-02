"""Tests for phlux/adapters/oracle.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.oracle import fetch, finder_terms, site_page

SITE = "https://acme.fa.em5.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs"
API = "https://acme.fa.em5.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions"


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def page(total, ids):
    return {"items": [{"TotalJobsCount": total, "requisitionList": [{"Id": str(i), "Title": f"Job  {i}"} for i in ids]}]}


def test_registered():
    assert ADAPTERS["oraclehcm"] is fetch


def test_finder_from_search_url():
    url = (SITE + "?keyword=intern&location=United+States&locationId=300000000425727"
           "&locationLevel=country&mode=location&sortBy=POSTING_DATES_DESC"
           "&selectedCategoriesFacet=11%3B22")
    assert finder_terms(url) == [
        "siteNumber=CX_1",
        "keyword=intern",
        "locationId=300000000425727",
        "sortBy=POSTING_DATES_DESC",
        "selectedCategoriesFacet=11;22",
    ]


def test_location_text_without_id():
    assert finder_terms(SITE + "?location=Detroit") == ["siteNumber=CX_1", "location=Detroit"]


def test_not_a_site_url():
    with pytest.raises(ValueError):
        finder_terms("https://acme.fa.em5.oraclecloud.com/hcmUI/CandidateExperience/en/jobs")


def test_pages_by_offset_until_total():
    pages = [page(201, range(200)), page(201, [200])]
    with patch("phlux.adapters.oracle.get", side_effect=[response(p) for p in pages]) as get:
        postings = fetch(SITE + "?keyword=intern")
    assert len(postings) == 201
    assert (postings[0].id, postings[0].title) == ("oraclehcm:0", "Job 0")
    assert postings[0].url == "https://acme.fa.em5.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job/0"
    assert get.call_count == 2
    first, second = get.call_args_list
    assert first.args == (API,)
    assert first.kwargs["params"] == {
        "onlyData": "true",
        "expand": "requisitionList.secondaryLocations",
        "finder": "findReqs;siteNumber=CX_1,keyword=intern,limit=200,offset=0",
    }
    assert second.kwargs["params"]["finder"].endswith("offset=200")


def test_site_page_drops_the_search():
    assert site_page(SITE + "/?keyword=intern&mode=location") == (
        "https://acme.fa.em5.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1")
    with pytest.raises(ValueError):
        site_page("https://acme.fa.em5.oraclecloud.com/hcmUI/CandidateExperience/en/sites/")


def test_no_jobs():
    with patch("phlux.adapters.oracle.get", return_value=response(page(0, []))) as get:
        assert fetch(SITE) == []
    assert get.call_count == 1


def test_primary_location_then_a_count_of_secondary_ones():
    jobs = [
        {"Id": "1", "Title": "A", "PrimaryLocation": "Dearborn, MI, United States", "secondaryLocations": []},
        {"Id": "2", "Title": "B", "PrimaryLocation": "Dearborn, MI, United States", "secondaryLocations": [
            {"Name": "Sterling Heights, MI, United States", "CountryCode": "US"},
            {"Name": "Dearborn, MI, United States", "CountryCode": "US"},
            {"Name": "Long Beach, CA, United States", "CountryCode": "US"}]},
        {"Id": "3", "Title": "C", "PrimaryLocation": "MI, United States"},
        {"Id": "4", "Title": "D", "PrimaryLocation": "United States"},
        {"Id": "5", "Title": "E", "PrimaryLocation": "Cologne, North Rhine-Westphalia, Germany"},
        {"Id": "6", "Title": "F"},
    ]
    with patch("phlux.adapters.oracle.get", return_value=response({"items": [{"TotalJobsCount": 6, "requisitionList": jobs}]})):
        postings = fetch(SITE)
    assert [p.location for p in postings] == [
        "Dearborn, MI", "Dearborn, MI +2", "Michigan", "United States", "Cologne, North Rhine-Westphalia, Germany", ""]
