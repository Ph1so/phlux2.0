"""Tests for phlux/adapters/google.py (HTTP mocked)."""
import json
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qsl, urlsplit

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.google import fetch, page_url, parse

URL = ("https://www.google.com/about/careers/applications/jobs/results/?category=SOFTWARE_ENGINEERING"
       "&category=HARDWARE_ENGINEERING&location=United%20States&employment_type=INTERN")


def results_page(jobs, total, size=20):
    data = json.dumps([[[jid, title, "https://apply", None] for jid, title in jobs], None, total, size])
    return (f"<script>AF_initDataCallback({{key: 'ds:0', hash: '1', data:[1], sideChannel: {{}}}});</script>"
            f"<script>AF_initDataCallback({{key: 'ds:1', hash: '2', data:{data}, sideChannel: {{}}}});</script>")


def response(html):
    mock = MagicMock()
    mock.text = html
    return mock


def test_registered():
    assert ADAPTERS["google"] is fetch


def test_page_url_keeps_repeated_filters():
    params = parse_qsl(urlsplit(page_url(URL + "&page=7", 3)).query)
    assert params == [("category", "SOFTWARE_ENGINEERING"), ("category", "HARDWARE_ENGINEERING"),
                      ("location", "United States"), ("employment_type", "INTERN"), ("page", "3")]


def test_parse():
    postings, total, size = parse(results_page([("111", "Software  Engineer Intern"), ("222", "PM")], 2))
    assert [(p.id, p.title) for p in postings] == [("google:111", "Software Engineer Intern"), ("google:222", "PM")]
    assert (total, size) == (2, 20)


def test_parse_empty_page():
    html = "<script>AF_initDataCallback({key: 'ds:1', hash: '2', data:[null,null,0,20], sideChannel: {}});</script>"
    assert parse(html) == ([], 0, 20)


def test_parse_without_data():
    with pytest.raises(ValueError):
        parse("<html>no jobs here</html>")


def test_reads_every_page_from_total():
    pages = {
        1: results_page([(str(i), f"Job {i}") for i in range(20)], 45),
        2: results_page([(str(i), f"Job {i}") for i in range(20, 40)], 45),
        3: results_page([(str(i), f"Job {i}") for i in range(40, 45)], 45),
    }

    def get(url, **kwargs):
        return response(pages[int(dict(parse_qsl(urlsplit(url).query))["page"])])

    with patch("phlux.adapters.google.get", side_effect=get) as mock:
        postings = fetch("https://www.google.com/about/careers/applications/jobs/results?company=DeepMind&page=2")
    assert [p.id for p in postings] == [f"google:{i}" for i in range(45)]
    assert mock.call_count == 3


def test_huge_search_is_refused():
    with patch("phlux.adapters.google.get", return_value=response(results_page([("1", "x")], 5000))):
        with pytest.raises(RuntimeError):
            fetch(URL)
