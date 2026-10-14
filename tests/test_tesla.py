"""Tests for phlux/scrapers/tesla.py."""
import json
from unittest.mock import MagicMock, patch

import pytest

from phlux.scrapers.tesla import filter_listings, location_ids, tesla_jobs

STATE = {
    "lookup": {
        "types": {"1": "fulltime", "3": "intern"},
        "departments": {"3": "Tesla AI", "6": "Vehicle Software"},
    },
    "geo": [
        {"id": "5", "sites": [
            {"id": "US", "states": [{"id": "CA", "cities": {"Palo Alto": ["10", "11"]}}]},
            {"id": "CA", "states": [{"id": "ON", "cities": {"Toronto": ["20"]}}]},
        ]},
    ],
    "listings": [
        {"t": "Internship, Optimus ", "dp": "3", "l": "10", "y": 3},
        {"t": "Internship, Autopilot", "dp": "6", "l": "11", "y": 3},
        {"t": "Engineer, Optimus", "dp": "3", "l": "10", "y": 1},
        {"t": "Internship, Toronto", "dp": "3", "l": "20", "y": 3},
    ],
}


class TestFilterListings:
    def test_location_ids_for_site(self):
        assert location_ids(STATE["geo"], "US") == {"10", "11"}

    def test_filters_type_and_site(self):
        assert filter_listings(STATE, "intern", "US", []) == [
            "Internship, Optimus",
            "Internship, Autopilot",
        ]

    def test_filters_departments_case_insensitively(self):
        assert filter_listings(STATE, "intern", "US", ["tesla ai"]) == ["Internship, Optimus"]

    def test_unknown_department_matches_nothing(self):
        assert filter_listings(STATE, "intern", "US", ["Nope"]) == []


class TestTeslaJobs:
    def _driver(self, *responses):
        driver = MagicMock()
        driver.current_url = "https://www.tesla.com/careers/search/?type=intern&site=US"
        driver.execute_async_script.side_effect = responses
        return driver

    @patch("phlux.scrapers.tesla.time.sleep")
    def test_retries_until_challenge_clears(self, _sleep):
        driver = self._driver("HTTP 429", json.dumps(STATE))
        assert tesla_jobs(driver, "Vehicle Software") == ["Internship, Autopilot"]

    @patch("phlux.scrapers.tesla.time.sleep")
    def test_raises_when_api_stays_blocked(self, _sleep):
        driver = self._driver(*["HTTP 403"] * 5)
        with pytest.raises(RuntimeError, match="HTTP 403"):
            tesla_jobs(driver)
