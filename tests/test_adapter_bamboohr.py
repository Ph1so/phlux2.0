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
    assert [(p.id, p.title, p.url) for p in postings] == [
        ("bamboohr:112", "Controls Engineer", "https://acme.bamboohr.com/careers/112"),
        ("bamboohr:7", "Software Intern", "https://acme.bamboohr.com/careers/7"),
    ]
    get.assert_called_once_with("https://acme.bamboohr.com/careers/list", allow_redirects=False)


def test_gone_board_raises():
    with patch("phlux.adapters.bamboohr.get", return_value=response(redirect="https://www.bamboohr.com")):
        with pytest.raises(RuntimeError, match="gone"):
            fetch("https://acme.bamboohr.com/careers")


@pytest.mark.parametrize("job, expected", [
    ({"location": {"city": "San Antonio", "state": "Texas"}}, "San Antonio, TX"),
    ({"location": {"city": None, "state": None},
      "atsLocation": {"city": "Munich", "state": "Bavaria", "country": "Germany"}}, "Munich, Germany"),
    ({"location": {"city": None, "state": None}, "atsLocation": {}, "isRemote": True}, "Remote"),
    ({"location": None, "atsLocation": None, "isRemote": None}, ""),
])
def test_location(job, expected):
    payload = {"result": [{"id": "1", "jobOpeningName": "Intern", **job}]}
    with patch("phlux.adapters.bamboohr.get", return_value=response(payload)):
        assert fetch("https://acme.bamboohr.com/careers")[0].location == expected
