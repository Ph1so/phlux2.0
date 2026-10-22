"""Tests for phlux/adapters/greyorange.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.greyorange import API, fetch

URL = "https://www.greyorange.com/company/careers/#th-job-section"


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def page(page, jobs, total=12, size=5):
    return {"success": True, "data": {"html": "", "totalCount": total, "pageSize": size, "page": page,
                                      "jobs": [{"id": str(i), "jobTitle": f"Engineer  {i}"} for i in jobs]}}


def test_registered():
    assert ADAPTERS["greyorange"] is fetch


def test_reads_every_page():
    pages = {1: page(1, range(5)), 2: page(2, range(5, 10)), 3: page(3, range(10, 12))}
    with patch("phlux.adapters.greyorange.post",
               side_effect=lambda url, data, **kw: response(pages[data["page"]])) as post:
        postings = fetch(URL)
    assert [p.id for p in postings] == [f"greyorange:{i}" for i in range(12)]
    assert postings[0].title == "Engineer 0"
    assert post.call_args_list[0].args == (API,)
    assert post.call_args_list[0].kwargs["data"] == {"action": "go_fetch_jobs", "page": 1}
    assert post.call_count == 3


def test_no_jobs():
    empty = {"success": True, "data": {"html": "", "totalCount": 0, "pageSize": 0, "page": 1, "jobs": []}}
    with patch("phlux.adapters.greyorange.post", return_value=response(empty)):
        assert fetch(URL) == []


def test_failure_raises():
    with patch("phlux.adapters.greyorange.post", return_value=response({"success": False, "data": None})):
        with pytest.raises(RuntimeError):
            fetch(URL)
