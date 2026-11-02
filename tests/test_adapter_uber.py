"""Tests for phlux/adapters/uber.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.uber import API, fetch, job_url

URL = "https://jobs.uber.com/en/jobs/?countries=United+States&team=University"


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def page(n, ids, pages=2):
    return {"totalPages": pages, "totalJobs": 12, "page": n, "pageSize": 10,
            "jobs": [{"Id": str(i), "Title": f"2027 Software  Engineering Intern {i}",
                      "Urls": [{"Culture": "en-us", "Url": f"/en/jobs/{i}/", "IsDefault": True}]} for i in ids]}


def test_registered():
    assert ADAPTERS["uber"] is fetch


def test_reads_every_page_with_the_links_filters():
    pages = {1: page(1, range(10)), 2: page(2, range(10, 12))}
    with patch("phlux.adapters.uber.get",
               side_effect=lambda url, params, **kw: response(pages[dict(params)["page"]])) as get:
        postings = fetch(URL + "&page=4")
    assert [p.id for p in postings] == [f"uber:{i}" for i in range(12)]
    assert postings[0].title == "2027 Software Engineering Intern 0"
    assert postings[0].url == "https://jobs.uber.com/en/jobs/0/"
    assert get.call_args_list[0].args == (API,)
    assert get.call_args_list[0].kwargs["params"] == [
        ("countries", "United States"), ("team", "University"), ("page", 1)]


@pytest.mark.parametrize("urls, expected", [
    ([{"Culture": "de-de", "Url": "/de/jobs/7/", "IsDefault": False},
      {"Culture": "en-us", "Url": "/en/jobs/7/", "IsDefault": True}], "https://jobs.uber.com/en/jobs/7/"),
    ([{"Culture": "de-de", "Url": "/de/jobs/7/", "IsDefault": False}], "https://jobs.uber.com/de/jobs/7/"),
    (None, "https://jobs.uber.com/en/jobs/7/"),
])
def test_job_url_prefers_the_default_page(urls, expected):
    assert job_url({"Id": "7", "Urls": urls}) == expected


def test_no_jobs():
    with patch("phlux.adapters.uber.get", return_value=response({"totalPages": 1, "totalJobs": 0, "jobs": []})):
        assert fetch(URL) == []


def test_huge_search_is_refused():
    with patch("phlux.adapters.uber.get", return_value=response(page(1, range(10), pages=72))):
        with pytest.raises(RuntimeError):
            fetch("https://jobs.uber.com/en/jobs/")
