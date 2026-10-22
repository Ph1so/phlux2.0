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
    return {"id": job_id, "name": name, "locations": [{"city": city}]}


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
    assert [(p.id, p.title) for p in postings] == [
        ("rippling:a", "Robotics  Intern"),
        ("rippling:b", "Recruiter"),
    ]
    get.assert_called_once_with(API, params={"searchQuery": ["intern"], "page": 0, "pageSize": 100})


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
