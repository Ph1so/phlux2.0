"""Tests for phlux/adapters/teamtailor.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.teamtailor import feed_url, fetch, job_id, location


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def address(city, region, country):
    return {"@type": "Place", "address": {"addressLocality": city, "addressRegion": region, "addressCountry": country}}


def item(number, title, *places, **posting):
    return {
        "id": f"uuid-{number}",
        "title": title,
        "url": f"https://acme.teamtailor.com/jobs/{number}-{title.lower().replace(' ', '-')}",
        "content_html": "<p>Build <b>robots</b>.</p>",
        "_jobposting": {"identifier": {"value": str(number)}, "jobLocation": list(places), **posting},
    }


def test_registered():
    assert ADAPTERS["teamtailor"] is fetch


@pytest.mark.parametrize("url, expected", [
    ("https://acme.teamtailor.com/jobs", "https://acme.teamtailor.com/jobs.json"),
    ("https://acme.teamtailor.com/", "https://acme.teamtailor.com/jobs.json"),
    ("https://careers.acme.com/jobs", "https://careers.acme.com/jobs.json"),
])
def test_feed_url(url, expected):
    assert feed_url(url) == expected


def test_feed_url_refuses_filters():
    with pytest.raises(ValueError):
        feed_url("https://acme.teamtailor.com/jobs?department=12")


def test_reads_json_feed():
    payload = {"items": [
        item(8447974, "Robot Technician", address("Hamburg", "Germany", "DE")),
        item(7552490, "Robotics  Intern", address("Tallinn", "Estonia", "EE")),
    ]}
    with patch("phlux.adapters.teamtailor.get", return_value=response(payload)) as get:
        postings = fetch("https://acme.teamtailor.com/jobs")
    assert [(p.id, p.title, p.location, p.url) for p in postings] == [
        ("teamtailor:8447974", "Robot Technician", "Hamburg, Germany",
         "https://acme.teamtailor.com/jobs/8447974-robot-technician"),
        ("teamtailor:7552490", "Robotics Intern", "Tallinn, Estonia",
         "https://acme.teamtailor.com/jobs/7552490-robotics--intern"),
    ]
    assert postings[0].description == "Build robots ."
    get.assert_called_once_with("https://acme.teamtailor.com/jobs.json")


def test_empty_feed():
    with patch("phlux.adapters.teamtailor.get", return_value=response({"items": []})):
        assert fetch("https://acme.teamtailor.com/jobs") == []


def test_job_id_falls_back_to_page_path():
    assert job_id({"id": "uuid", "url": "https://acme.teamtailor.com/jobs/123-x", "_jobposting": {}}) == "123"
    assert job_id({"id": "uuid", "url": "", "_jobposting": {}}) == "uuid"


@pytest.mark.parametrize("posting, expected", [
    ({"jobLocation": [address("Austin", "Texas", "US")]}, "Austin, TX"),
    ({"jobLocation": [address("Austin", "United States", "US")]}, "Austin"),
    ({"jobLocation": [address("Hamburg", "Germany", "DE"), address("Tallinn", "Estonia", "EE")]},
     "Hamburg, Germany +1"),
    ({"jobLocation": address("Paris", "Île-de-France", "FR")}, "Paris, France"),
    ({"jobLocation": [], "jobLocationType": "TELECOMMUTE"}, "Remote"),
    ({}, ""),
])
def test_location(posting, expected):
    assert location(posting) == expected
