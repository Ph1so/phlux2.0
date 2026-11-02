"""Tests for phlux/adapters/gem.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

from phlux.adapters import ADAPTERS
from phlux.adapters.gem import fetch


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def test_registered():
    assert ADAPTERS["gem"] is fetch


def test_reads_job_posts():
    payload = [
        {"id": "am9icG9zdDpx", "title": "Forward Deployed Engineer", "absolute_url": "https://jobs.gem.com/acme/am9icG9zdDpx"},
        {"id": "am9icG9zdDpM", "title": "Robotics Intern"},
    ]
    with patch("phlux.adapters.gem.get", return_value=response(payload)) as get:
        postings = fetch("https://jobs.gem.com/acme")
    assert [(p.id, p.title, p.url) for p in postings] == [
        ("gem:am9icG9zdDpx", "Forward Deployed Engineer", "https://jobs.gem.com/acme/am9icG9zdDpx"),
        ("gem:am9icG9zdDpM", "Robotics Intern", ""),
    ]
    get.assert_called_once_with("https://api.gem.com/job_board/v0/acme/job_posts/")


def test_location_from_offices_else_the_posts_location():
    def office(name, location):
        return {"id": name, "name": name, "location": {"name": location}}

    payload = [
        {"id": "a", "title": "A", "location": {"name": "San Francisco, United States"},
         "offices": [office("San Francisco, California", "San Francisco, United States")]},
        {"id": "b", "title": "B", "location": {"name": "United States - Remote"},
         "offices": [office("Remote, United States", "United States - Remote"), office("Los Angeles", "")]},
        {"id": "c", "title": "C", "location": {"name": "Munich, Germany"}, "offices": []},
        {"id": "d", "title": "D"},
    ]
    with patch("phlux.adapters.gem.get", return_value=response(payload)):
        postings = fetch("https://jobs.gem.com/acme")
    assert [p.location for p in postings] == ["San Francisco, CA", "Remote, United States +1", "Munich, Germany", ""]
