"""Tests for phlux/adapters/dover.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.dover import client_id, fetch

CLIENT = "3bf8e18a-8218-4305-ac0d-364891d94173"
JOBS = f"https://app.dover.com/api/v1/careers-page/{CLIENT}/jobs"


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def routes(table):
    def get(url, **kwargs):
        if url in table:
            return response(table[url])
        raise AssertionError(f"unexpected GET {url}")
    return get


def test_registered():
    assert ADAPTERS["dover"] is fetch


def test_client_id_from_slug():
    get = routes({"https://app.dover.com/api/v1/careers-page-slug/acme": {"id": CLIENT, "slug": "acme"}})
    with patch("phlux.adapters.dover.get", side_effect=get):
        assert client_id("https://app.dover.com/jobs/acme") == CLIENT


def test_client_id_in_url_needs_no_lookup():
    with patch("phlux.adapters.dover.get", side_effect=AssertionError):
        assert client_id(f"https://app.dover.com/acme/careers/{CLIENT}") == CLIENT


def test_bad_url():
    with pytest.raises(ValueError):
        client_id("https://app.dover.com/")


def test_published_jobs_across_pages():
    get = routes({
        "https://app.dover.com/api/v1/careers-page-slug/acme": {"id": CLIENT},
        JOBS: {"count": 3, "next": JOBS + "?page=2", "results": [
            {"id": "j1", "title": "Robotics Intern", "is_published": True, "is_sample": False},
            {"id": "j2", "title": "Sample Job", "is_published": True, "is_sample": True},
        ]},
        JOBS + "?page=2": {"count": 3, "next": None, "results": [
            {"id": "j3", "title": "Draft", "is_published": False},
            {"id": "j4", "title": "Engineer"},
        ]},
    })
    with patch("phlux.adapters.dover.get", side_effect=get):
        postings = fetch("https://app.dover.com/jobs/acme")
    assert [(p.id, p.title) for p in postings] == [("dover:j1", "Robotics Intern"), ("dover:j4", "Engineer")]


def test_empty_board():
    get = routes({
        "https://app.dover.com/api/v1/careers-page-slug/acme": {"id": CLIENT},
        JOBS: {"count": 0, "next": None, "previous": None, "results": []},
    })
    with patch("phlux.adapters.dover.get", side_effect=get):
        assert fetch("https://app.dover.com/jobs/acme") == []
