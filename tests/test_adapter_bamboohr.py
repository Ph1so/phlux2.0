"""Tests for phlux/adapters/bamboohr.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.bamboohr import board_slug, fetch


def response(payload=None, redirect=None):
    mock = MagicMock()
    mock.json.return_value = payload
    mock.is_redirect = redirect is not None
    mock.headers = {"location": redirect} if redirect else {}
    return mock


def test_registered():
    assert ADAPTERS["bamboohr"] is fetch


@pytest.mark.parametrize("url", [
    "https://acme.bamboohr.com/careers",
    "https://acme.bamboohr.com/careers/",
    "https://ACME.bamboohr.com/jobs/",
])
def test_slug(url):
    assert board_slug(url) == "acme"


def test_slug_rejects_other_hosts():
    with pytest.raises(ValueError):
        board_slug("https://acme.com/careers")


def test_reads_careers_list():
    payload = {"meta": {"totalCount": 2}, "result": [
        {"id": "112", "jobOpeningName": "Controls Engineer"},
        {"id": "7", "jobOpeningName": "Software Intern"},
    ]}
    with patch("phlux.adapters.bamboohr.get", return_value=response(payload)) as get:
        postings = fetch("https://acme.bamboohr.com/careers")
    assert [(p.id, p.title) for p in postings] == [
        ("bamboohr:112", "Controls Engineer"),
        ("bamboohr:7", "Software Intern"),
    ]
    get.assert_called_once_with("https://acme.bamboohr.com/careers/list", allow_redirects=False)


def test_gone_board_raises():
    with patch("phlux.adapters.bamboohr.get", return_value=response(redirect="https://www.bamboohr.com")):
        with pytest.raises(RuntimeError, match="gone"):
            fetch("https://acme.bamboohr.com/careers")
