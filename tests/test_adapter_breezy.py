"""Tests for phlux/adapters/breezy.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.breezy import fetch, location, portal_slug


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def where(city="New York", state=("NY", "New York"), country=("US", "United States"), **extra):
    return {"city": city, "state": {"id": state[0], "name": state[1]} if state else None,
            "country": {"id": country[0], "name": country[1]} if country else None, **extra}


def test_registered():
    assert ADAPTERS["breezy"] is fetch


@pytest.mark.parametrize("url", ["https://acme.breezy.hr/", "https://acme.breezy.hr", "https://ACME.breezy.hr/p/x"])
def test_slug(url):
    assert portal_slug(url) == "acme"


@pytest.mark.parametrize("url", ["https://acme.com/careers", "https://acme.breezy.hr/?department=Product"])
def test_slug_refuses_other_hosts_and_filters(url):
    with pytest.raises(ValueError):
        portal_slug(url)


def test_reads_portal_json():
    payload = [
        {"id": "7faefc00059e", "friendly_id": "7faefc00059e-data-science-intern", "name": "Data Science  Intern",
         "url": "https://acme.breezy.hr/p/7faefc00059e-data-science-intern", "location": where()},
        {"id": "b279ca27eb53", "friendly_id": "b279ca27eb53-engineer", "name": "Engineer", "location": where()},
    ]
    with patch("phlux.adapters.breezy.get", return_value=response(payload)) as get:
        postings = fetch("https://acme.breezy.hr/")
    assert [(p.id, p.title, p.location, p.url) for p in postings] == [
        ("breezy:7faefc00059e", "Data Science Intern", "New York, NY",
         "https://acme.breezy.hr/p/7faefc00059e-data-science-intern"),
        ("breezy:b279ca27eb53", "Engineer", "New York, NY", "https://acme.breezy.hr/p/b279ca27eb53-engineer"),
    ]
    get.assert_called_once_with("https://acme.breezy.hr/json")


def test_empty_portal():
    with patch("phlux.adapters.breezy.get", return_value=response([])):
        assert fetch("https://acme.breezy.hr/") == []


@pytest.mark.parametrize("job, expected", [
    ({"location": where()}, "New York, NY"),
    ({"location": where(city=None, state=None)}, "United States"),
    ({"location": where(city="Munich", state=("BY", "Bavaria"), country=("DE", "Germany"))}, "Munich, Germany"),
    ({"location": where(city=None, state=None, country=None, is_remote=True)}, "Remote"),
    ({"location": where(), "locations": [where(), where(city="Austin", state=("TX", "Texas"))]}, "New York, NY +1"),
    ({"location": None}, ""),
])
def test_location(job, expected):
    assert location(job) == expected
