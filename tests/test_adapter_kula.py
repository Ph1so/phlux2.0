"""Tests for phlux/adapters/kula.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

from phlux.adapters import ADAPTERS
from phlux.adapters.kula import API, fetch


def response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    return mock


def test_registered():
    assert ADAPTERS["kula"] is fetch


def test_listed_posts_across_pages():
    pages = [
        {"data": [
            {"id": 1, "title": "ML Research Intern", "listed": True, "kind": "internal_and_external"},
            {"id": 2, "title": "Hidden", "listed": False, "kind": "internal_and_external"},
        ], "meta": {"count": 4, "page": 1, "items": 99, "pages": 2}},
        {"data": [
            {"id": 3, "title": "Staff Only", "listed": True, "kind": "internal"},
            {"id": 4, "title": "Head of Hardware", "listed": True, "kind": "external"},
        ], "meta": {"count": 4, "page": 2, "items": 99, "pages": 2}},
    ]
    with patch("phlux.adapters.kula.get", side_effect=[response(p) for p in pages]) as get:
        postings = fetch("https://careers.kula.ai/acme-ai")
    assert [(p.id, p.title) for p in postings] == [("kula:1", "ML Research Intern"), ("kula:4", "Head of Hardware")]
    assert get.call_args_list[0].args == (API,)
    assert [c.kwargs["params"] for c in get.call_args_list] == [
        {"accountName": "acme-ai", "type": "ats_job_post.index", "items": 99, "page": 1},
        {"accountName": "acme-ai", "type": "ats_job_post.index", "items": 99, "page": 2},
    ]


def test_empty_board():
    payload = {"data": [], "meta": {"count": 0, "page": 1, "items": 99, "pages": 0}, "errors": []}
    with patch("phlux.adapters.kula.get", return_value=response(payload)) as get:
        assert fetch("https://careers.kula.ai/acme-ai") == []
    assert get.call_count == 1
