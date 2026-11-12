"""Tests for phlux/adapters/pinpoint.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.pinpoint import api_url, fetch, location


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def job(number, title, city="Redondo Beach", province="California", **extra):
    return {
        "id": str(number),
        "title": title,
        "url": f"https://acme.pinpointhq.com/en/postings/uuid-{number}",
        "path": f"/en/postings/uuid-{number}",
        "location": {"city": city, "province": province, "name": f"{city} "},
        "workplace_type": "onsite",
        "description": "<p>Design <b>thrusters</b>.</p>",
        **extra,
    }


def test_registered():
    assert ADAPTERS["pinpoint"] is fetch


@pytest.mark.parametrize("url", [
    "https://acme.pinpointhq.com/", "https://acme.pinpointhq.com", "https://acme.pinpointhq.com/en/postings/x",
])
def test_api_url(url):
    assert api_url(url) == "https://acme.pinpointhq.com/postings.json"


@pytest.mark.parametrize("url", ["https://acme.com/careers", "https://acme.pinpointhq.com/?department=1"])
def test_api_url_refuses_other_hosts_and_filters(url):
    with pytest.raises(ValueError):
        api_url(url)


def test_reads_postings_json():
    payload = {"data": [
        job(290785, "Senior Development Test Engineer"),
        job(568562, "Avionics  Engineering Intern", url=None),
    ]}
    with patch("phlux.adapters.pinpoint.get", return_value=response(payload)) as get:
        postings = fetch("https://acme.pinpointhq.com/")
    assert [(p.id, p.title, p.location, p.url) for p in postings] == [
        ("pinpoint:290785", "Senior Development Test Engineer", "Redondo Beach, CA",
         "https://acme.pinpointhq.com/en/postings/uuid-290785"),
        ("pinpoint:568562", "Avionics Engineering Intern", "Redondo Beach, CA",
         "https://acme.pinpointhq.com/en/postings/uuid-568562"),
    ]
    assert postings[0].description == "Design thrusters ."
    get.assert_called_once_with("https://acme.pinpointhq.com/postings.json")


def test_empty_site():
    with patch("phlux.adapters.pinpoint.get", return_value=response({"data": []})):
        assert fetch("https://acme.pinpointhq.com/") == []


@pytest.mark.parametrize("posting, expected", [
    (job(1, "x"), "Redondo Beach, CA"),
    (job(1, "x", city="Boulder", province="Colorado"), "Boulder, CO"),
    (job(1, "x", city="London", province="England"), "London, England"),
    (job(1, "x", city="Toronto", province="Ontario", location={"city": "Toronto", "province": "Ontario",
                                                                 "country": "Canada"}), "Toronto, Canada"),
    (job(1, "x", city="", province="", workplace_type="remote"), "Remote"),
    ({"location": None}, ""),
])
def test_location(posting, expected):
    assert location(posting) == expected
