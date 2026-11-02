"""Tests for phlux/adapters/deshaw.py (HTTP mocked)."""
import json
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.deshaw import fetch

URL = "https://www.deshaw.com/careers/internships"


def page(props):
    data = {"props": {"pageProps": props}, "page": "/careers/internships"}
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'


def response(html):
    mock = MagicMock()
    mock.text = html
    return mock


def test_registered():
    assert ADAPTERS["deshaw"] is fetch


def test_reads_every_internship():
    html = page({"internships": [
        {"id": "5890", "displayName": "Quantitative Analyst Intern (New York) –  Summer 2027",
         "data": {"id": 5890, "jobUrl": "Quantitative-Analyst-Intern-New-York-Summer-2027-5890"}},
        {"id": "5925", "displayName": "Systems Engineering Intern (London) - Summer 2027"},
    ], "regularJobs": [{"id": "1", "displayName": "Not an internship"}], "jobsFetchingError": False})
    with patch("phlux.adapters.deshaw.get", return_value=response(html)):
        postings = fetch(URL)
    assert [(p.id, p.title) for p in postings] == [
        ("deshaw:5890", "Quantitative Analyst Intern (New York) – Summer 2027"),
        ("deshaw:5925", "Systems Engineering Intern (London) - Summer 2027"),
    ]
    # The page links jobUrl lowercased; a job without one has no link.
    assert [p.url for p in postings] == [
        "https://www.deshaw.com/careers/quantitative-analyst-intern-new-york-summer-2027-5890", ""]


def test_no_internships():
    with patch("phlux.adapters.deshaw.get", return_value=response(page({"internships": []}))):
        assert fetch(URL) == []


@pytest.mark.parametrize("html", [page({"internships": [], "jobsFetchingError": True}), page({}), "<html></html>"])
def test_failed_page_raises(html):
    with patch("phlux.adapters.deshaw.get", return_value=response(html)):
        with pytest.raises(RuntimeError):
            fetch(URL)
