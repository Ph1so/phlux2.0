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
    assert [(p.id, p.title) for p in postings] == [
        ("gem:am9icG9zdDpx", "Forward Deployed Engineer"),
        ("gem:am9icG9zdDpM", "Robotics Intern"),
    ]
    get.assert_called_once_with("https://api.gem.com/job_board/v0/acme/job_posts/")
