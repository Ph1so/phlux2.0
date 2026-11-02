"""Tests for phlux/adapters/rippling.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.rippling import board_filters, board_slug, fetch

API = "https://ats.rippling.com/api/v2/board/acme/jobs"


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def job(job_id, name, city="Boston"):
    return {"id": job_id, "name": name, "url": f"https://ats.rippling.com/acme/jobs/{job_id}",
            "locations": [{"city": city}]}


def test_registered():
    assert ADAPTERS["rippling"] is fetch


@pytest.mark.parametrize("url", [
    "https://ats.rippling.com/acme/jobs?page=0&pageSize=100",
    "https://ats.rippling.com/acme/jobs",
    "https://ats.rippling.com/en-GB/acme/jobs",
    "https://ats.rippling.com/acme/jobs/1234",
])
def test_slug(url):
    assert board_slug(url) == "acme"


def test_filters_drop_paging_and_empty_values():
    url = ("https://ats.rippling.com/acme/jobs?page=2&searchQuery=&workplaceType=REMOTE"
           "&country=US&state=&pageSize=20&departments=Eng&departments=Ops")
    assert board_filters(url) == {
        "workplaceType": ["REMOTE"], "country": ["US"], "departments": ["Eng", "Ops"],
    }


def test_one_posting_per_job_id_with_filters_passed_on():
    payload = {"items": [
        job("a", "Robotics  Intern"),
        job("b", "Recruiter"),
        job("a", "Robotics  Intern", city="Austin"),  # same job, second location
    ], "totalPages": 1}
    with patch("phlux.adapters.rippling.get", return_value=response(payload)) as get:
        postings = fetch("https://ats.rippling.com/acme/jobs?page=0&pageSize=100&searchQuery=intern")
    assert [(p.id, p.title, p.url) for p in postings] == [
        ("rippling:a", "Robotics  Intern", "https://ats.rippling.com/acme/jobs/a"),
        ("rippling:b", "Recruiter", "https://ats.rippling.com/acme/jobs/b"),
    ]
    get.assert_called_once_with(API, params={"searchQuery": ["intern"], "page": 0, "pageSize": 100})


def test_a_job_without_a_url_links_to_its_board_page():
    payload = {"items": [{"id": "c", "name": "Intern"}], "totalPages": 1}
    with patch("phlux.adapters.rippling.get", return_value=response(payload)):
        postings = fetch("https://ats.rippling.com/en-GB/acme/jobs")
    assert postings[0].url == "https://ats.rippling.com/acme/jobs/c"


def test_pages_until_total_pages():
    pages = [
        {"items": [job("a", "A")], "totalPages": 2},
        {"items": [job("b", "B")], "totalPages": 2},
    ]
    with patch("phlux.adapters.rippling.get", side_effect=[response(p) for p in pages]) as get:
        postings = fetch("https://ats.rippling.com/acme/jobs")
    assert [p.id for p in postings] == ["rippling:a", "rippling:b"]
    assert [c.kwargs["params"]["page"] for c in get.call_args_list] == [0, 1]


def test_empty_board():
    with patch("phlux.adapters.rippling.get", return_value=response({"items": [], "totalPages": 0})):
        assert fetch("https://ats.rippling.com/acme/jobs") == []


def located(job_id, *names):
    return {"id": job_id, "name": "Intern", "url": f"https://ats.rippling.com/acme/jobs/{job_id}",
            "locations": [{"name": n, "country": "United States", "countryCode": "US"} for n in names]}


def test_a_jobs_locations_from_all_its_items_sorted():
    pages = [
        {"items": [located("a", "Huntsville, AL"), located("b", "Remote (United States)"),
                   located("a", "Arlington, VA")], "totalPages": 2},
        {"items": [located("a", "Clarksburg, MD"), located("c")], "totalPages": 2},
    ]
    with patch("phlux.adapters.rippling.get", side_effect=[response(p) for p in pages]):
        postings = fetch("https://ats.rippling.com/acme/jobs")
    assert [(p.id, p.location) for p in postings] == [
        ("rippling:a", "Arlington, VA +2"), ("rippling:b", "Remote (United States)"), ("rippling:c", "")]


def test_the_same_job_reads_the_same_in_any_order():
    items = [located("a", "Huntsville, AL"), located("a", "Arlington, VA")]
    for order in (items, items[::-1]):
        with patch("phlux.adapters.rippling.get", return_value=response({"items": order, "totalPages": 1})):
            assert fetch("https://ats.rippling.com/acme/jobs")[0].location == "Arlington, VA +1"


def test_a_location_without_a_name_is_built_from_its_fields():
    item = {"id": "a", "name": "Intern", "locations": [{"city": "Boston", "stateCode": "MA", "countryCode": "US"}]}
    with patch("phlux.adapters.rippling.get", return_value=response({"items": [item], "totalPages": 1})):
        assert fetch("https://ats.rippling.com/acme/jobs")[0].location == "Boston, MA"
