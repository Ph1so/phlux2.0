"""Tests for phlux/adapters/teamio.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.teamio import API, fetch, widget_config

PAGE = ('<div id="capybara"></div><script>window.__LMC_CAREER_WIDGET__ = '
        '{"apiKey":"pubkey","widgetId":"w-1","selector":"#capybara","themes":["base"]};</script>')


def response(payload=None, text=""):
    mock = MagicMock()
    mock.json.return_value = payload
    mock.text = text
    return mock


def ads(jobs, groups=(), last=1):
    return {"data": {"widget": {"jobAdList": {
        "groupedJobAds": {"jobAds": jobs, "groups": [{"jobAds": g} for g in groups]},
        "paginator": {"currentPage": 1, "lastPage": last},
    }}}}


def test_registered():
    assert ADAPTERS["teamio"] is fetch


def test_widget_config_from_page():
    assert widget_config(PAGE)["widgetId"] == "w-1"
    with pytest.raises(ValueError):
        widget_config("<html></html>")


def test_reads_ungrouped_and_grouped_ads_across_pages():
    pages = [
        ads([{"id": "1", "title": "Robotics  Warehouse Coordinator [Austin, TX]"}],
            groups=[[{"id": "2", "title": "QA Engineer"}]], last=2),
        ads([{"id": "3", "title": "Intern"}, {"id": "1", "title": "Robotics  Warehouse Coordinator [Austin, TX]"}], last=2),
    ]
    with patch("phlux.adapters.teamio.get", return_value=response(text=PAGE)) as get, \
         patch("phlux.adapters.teamio.post", side_effect=[response(p) for p in pages]) as post:
        postings = fetch("https://acme.ai/careers/#openpositions")
    assert [(p.id, p.title) for p in postings] == [
        ("teamio:1", "Robotics  Warehouse Coordinator [Austin, TX]"),
        ("teamio:2", "QA Engineer"),
        ("teamio:3", "Intern"),
    ]
    get.assert_called_once_with("https://acme.ai/careers/#openpositions")
    first = post.call_args_list[0]
    assert first.args == (API,)
    assert first.kwargs["headers"] == {"X-Api-Key": "pubkey"}
    assert first.kwargs["json"]["variables"] == {"widgetId": "w-1", "page": 1, "rps": 100}
    assert post.call_args_list[1].kwargs["json"]["variables"]["page"] == 2


def test_graphql_errors_raise():
    with patch("phlux.adapters.teamio.get", return_value=response(text=PAGE)), \
         patch("phlux.adapters.teamio.post", return_value=response({"errors": [{"message": "bad key"}]})):
        with pytest.raises(RuntimeError):
            fetch("https://acme.ai/careers/")
