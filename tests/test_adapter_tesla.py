"""Tests for phlux/adapters/tesla.py (browsers mocked)."""
from unittest.mock import patch

import pytest

from phlux.adapters import tesla

STATE = {
    "lookup": {
        "types": {"1": "intern", "2": "regular"},
        "departments": {"3": "Tesla SI", "6": "Vehicle Software", "7": "Engineering & Information Technology"},
    },
    "geo": [{"sites": [{"id": "US", "states": [{"cities": {"Palo Alto": ["10"]}}]},
                       {"id": "DE", "states": [{"cities": {"Berlin": ["20"]}}]}]}],
    "listings": [
        {"id": "1", "t": "Internship,  Optimus", "y": 1, "l": "10", "dp": "3"},
        {"id": "2", "t": "Internship, Firmware", "y": 1, "l": "10", "dp": "6"},
        {"id": "3", "t": "Engineer, Optimus", "y": 2, "l": "10", "dp": "3"},
        {"id": "4", "t": "Internship, Berlin", "y": 1, "l": "20", "dp": "3"},
        {"id": "5", "t": "Internship, Data Platforms", "y": 1, "l": "10", "dp": "7"},
    ],
}
URL = "https://www.tesla.com/careers/search/?type=intern&site=US"


class TestFetch:
    def test_filters_by_type_site_and_departments(self):
        with patch.object(tesla, "fetch_state", return_value=STATE):
            postings = tesla.fetch(URL, "Tesla SI|Engineering & Information Technology")
        assert [(p.id, p.title) for p in postings] == [
            ("tesla:1", "Internship, Optimus"),
            ("tesla:5", "Internship, Data Platforms"),
        ]
        assert [p.url for p in postings] == [
            "https://www.tesla.com/careers/search/job/internship-optimus-1",
            "https://www.tesla.com/careers/search/job/internship-data-platforms-5",
        ]

    def test_no_departments_keeps_all(self):
        with patch.object(tesla, "fetch_state", return_value=STATE):
            postings = tesla.fetch(URL)
        assert [p.id for p in postings] == ["tesla:1", "tesla:2", "tesla:5"]


class TestJobUrl:
    @pytest.mark.parametrize("search_url, title, expected", [
        (URL, "Internship, Software Engineer, Vehicle Firmware (Winter/Spring 2027)",
         "https://www.tesla.com/careers/search/job/internship-software-engineer-vehicle-firmware-winter-spring-2027-9"),
        (URL, "Sr. Ingénieur  Qualité", "https://www.tesla.com/careers/search/job/sr-ingenieur-qualite-9"),
        ("https://www.tesla.com/de_DE/careers/search/?site=DE", "Praktikum",
         "https://www.tesla.com/de_DE/careers/search/job/praktikum-9"),
        (URL, "???", "https://www.tesla.com/careers/search/job/9"),
    ])
    def test_slug_and_id_under_the_search_page(self, search_url, title, expected):
        assert tesla.job_url(search_url, {"id": "9", "t": title}) == expected


class TestFetchState:
    def test_falls_back_to_next_browser(self):
        calls = []

        def refused(url):
            calls.append("undetected")
            raise tesla.Refused("page denied")

        def works(url):
            calls.append("nodriver")
            return STATE

        with patch.object(tesla, "STRATEGIES", [("undetected-chromedriver", refused), ("nodriver", works)]):
            assert tesla.fetch_state(URL) is STATE
        assert calls == ["undetected", "nodriver"]

    def test_stops_at_first_success(self):
        second = lambda url: pytest.fail("second browser should not start")  # noqa: E731
        with patch.object(tesla, "STRATEGIES", [("a", lambda url: STATE), ("b", second)]):
            assert tesla.fetch_state(URL) is STATE

    def test_reports_every_failure(self):
        def denied(url):
            raise tesla.Refused("page denied")

        def throttled(url):
            raise tesla.Refused("HTTP 429")

        with patch.object(tesla, "STRATEGIES", [("undetected-chromedriver", denied), ("nodriver", throttled)]):
            with pytest.raises(RuntimeError, match="undetected-chromedriver: Refused: page denied; nodriver: Refused: HTTP 429"):
                tesla.fetch_state(URL)


class TestHeaded:
    @pytest.mark.parametrize("platform, display, expected", [
        ("linux", ":99", True),
        ("linux", "", False),
        ("darwin", ":0", False),
    ])
    def test_headed_only_on_linux_with_a_display(self, monkeypatch, platform, display, expected):
        monkeypatch.setattr(tesla.sys, "platform", platform)
        monkeypatch.setenv("DISPLAY", display)
        assert tesla.headed() is expected
