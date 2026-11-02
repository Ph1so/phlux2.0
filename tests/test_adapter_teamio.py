"""Tests for phlux/adapters/teamio.py (HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from phlux.adapters import ADAPTERS
from phlux.adapters.teamio import API, fetch, job_url, widget_config

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
    # The widget opens an ad on the careers page itself; the page's anchor is dropped.
    assert postings[0].url == "https://acme.ai/careers/?r=detail&id=1"
    get.assert_called_once_with("https://acme.ai/careers/#openpositions")
    first = post.call_args_list[0]
    assert first.args == (API,)
    assert first.kwargs["headers"] == {"X-Api-Key": "pubkey"}
    assert first.kwargs["json"]["variables"] == {"widgetId": "w-1", "page": 1, "rps": 100}
    assert post.call_args_list[1].kwargs["json"]["variables"]["page"] == 2


@pytest.mark.parametrize("config, expected", [
    ({}, "https://acme.ai/careers/?r=detail&id=7"),
    ({"onePage": True, "legacyRouting": False}, "https://acme.ai/careers/?r=detail&id=7"),
    ({"legacyRouting": True}, ""),
    ({"onePage": False, "detailPath": "/careers/job"}, ""),
])
def test_job_url_follows_the_widgets_routing(config, expected):
    assert job_url("https://acme.ai/careers/?utm_source=x#openpositions", config, "7") == expected


def test_graphql_errors_raise():
    with patch("phlux.adapters.teamio.get", return_value=response(text=PAGE)), \
         patch("phlux.adapters.teamio.post", return_value=response({"errors": [{"message": "bad key"}]})):
        with pytest.raises(RuntimeError):
            fetch("https://acme.ai/careers/")


def test_query_asks_for_locations():
    with patch("phlux.adapters.teamio.get", return_value=response(text=PAGE)), \
         patch("phlux.adapters.teamio.post", return_value=response(ads([]))) as post:
        fetch("https://acme.ai/careers/")
    assert "locations { city region country }" in post.call_args.kwargs["json"]["query"]


@pytest.mark.parametrize("title, locations, expected", [
    ("Robotics QA Engineer", [{"city": "Bratislava-Ružinov", "region": "Bratislavský", "country": "Slovensko"}],
     "Bratislava-Ružinov, Slovensko"),
    ("Technical Warehouse Operator [Austin, TX]", [{"city": None, "region": None, "country": "Spojené státy americké"}],
     "Austin, TX"),
    ("Field Technician [York, PA 17402]", [{"city": None, "region": None, "country": "Spojené státy americké"}],
     "York, PA"),
    ("Technical Account Manager", [{"city": None, "region": None, "country": "Spojené státy americké"}],
     "United States"),
    ("Technician [m/ž]", [{"city": "Bratislava", "region": "Bratislavský", "country": "Slovensko"},
                          {"city": "Košice", "region": "Košický", "country": "Slovensko"}], "Bratislava, Slovensko +1"),
    ("Intern", [], ""),
])
def test_location(title, locations, expected):
    with patch("phlux.adapters.teamio.get", return_value=response(text=PAGE)), \
         patch("phlux.adapters.teamio.post", return_value=response(ads([{"id": "1", "title": title,
                                                                           "locations": locations}]))):
        assert fetch("https://acme.ai/careers/")[0].location == expected
