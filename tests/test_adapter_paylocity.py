"""Tests for phlux/adapters/paylocity.py (HTTP mocked)."""
import json
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.paylocity import fetch, page_data

URL = "https://recruiting.paylocity.com/recruiting/jobs/All/3a4d8744-ab51-41d9-a0cf-43de316c7dca/Acme"


def page(jobs):
    data = {"Departments": [], "Jobs": jobs, "ModuleTitle": "Acme"}
    return f"<html><script>window.pageData = {json.dumps(data)};\nwindow.other = 1;</script></html>"


def response(html):
    mock = MagicMock()
    mock.text = html
    return mock


def test_registered():
    assert ADAPTERS["paylocity"] is fetch


def test_reads_jobs_from_page_data():
    html = page([
        {"JobId": 4586493, "JobTitle": "Shuttle Attendant; Part-Time", "IsInternal": False},
        {"JobId": 1, "JobTitle": "Robotics Intern {Summer}", "IsInternal": False},
    ])
    with patch("phlux.adapters.paylocity.get", return_value=response(html)) as get:
        postings = fetch(URL)
    assert [(p.id, p.title, p.url) for p in postings] == [
        ("paylocity:4586493", "Shuttle Attendant; Part-Time",
         "https://recruiting.paylocity.com/Recruiting/Jobs/Details/4586493"),
        ("paylocity:1", "Robotics Intern {Summer}", "https://recruiting.paylocity.com/Recruiting/Jobs/Details/1"),
    ]
    get.assert_called_once_with(URL)


def test_empty_board():
    with patch("phlux.adapters.paylocity.get", return_value=response(page([]))):
        assert fetch(URL) == []


def test_missing_page_data_raises():
    with pytest.raises(ValueError):
        page_data("<html>Access denied</html>")


def where(city=None, state=None, country="USA"):
    return {"Name": "HQ", "City": city, "State": state, "Zip": None, "Country": country}


@pytest.mark.parametrize("job, expected", [
    ({"JobLocation": where("Philadelphia", "PA"), "ShouldDisplayLocation": True, "IsRemote": False},
     "Philadelphia, PA"),
    ({"JobLocation": where("Austin", "Texas"), "ShouldDisplayLocation": True, "IsRemote": False}, "Austin, TX"),
    ({"JobLocation": where(), "LocationName": "Remote Worker - N/A", "ShouldDisplayLocation": True,
      "IsRemote": True}, "Remote"),
    ({"JobLocation": where(), "ShouldDisplayLocation": False, "IsRemote": True}, "Remote"),
    ({"JobLocation": where("Philadelphia", "PA"), "ShouldDisplayLocation": False, "IsRemote": False}, ""),
    ({"JobLocation": where("Toronto", "ON", "CAN"), "ShouldDisplayLocation": True}, "Toronto, Canada"),
    ({}, ""),
])
def test_location(job, expected):
    html = page([{"JobId": 1, "JobTitle": "Intern", **job}])
    with patch("phlux.adapters.paylocity.get", return_value=response(html)):
        assert fetch(URL)[0].location == expected
