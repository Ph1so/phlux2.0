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
    assert [(p.id, p.title) for p in postings] == [
        ("paylocity:4586493", "Shuttle Attendant; Part-Time"),
        ("paylocity:1", "Robotics Intern {Summer}"),
    ]
    get.assert_called_once_with(URL)


def test_empty_board():
    with patch("phlux.adapters.paylocity.get", return_value=response(page([]))):
        assert fetch(URL) == []


def test_missing_page_data_raises():
    with pytest.raises(ValueError):
        page_data("<html>Access denied</html>")
