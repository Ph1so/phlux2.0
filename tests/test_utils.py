"""Tests for phlux/utils.py."""
import json
import os
from unittest.mock import MagicMock, mock_open, patch

import pytest
import requests

from phlux.models import Company
from phlux.utils import is_full_time, is_internship, update_icons


# ── is_internship / is_full_time ──────────────────────────────────────────────

class TestIsInternship:
    def test_matches_intern_substring(self):
        assert is_internship("Software Engineer Intern") is True

    def test_matches_internship_full_word(self):
        assert is_internship("internship program") is True

    def test_matches_ship_as_substring_of_internship(self):
        # "ship" is a substring of "internship" — intentional keyword
        assert is_internship("Internship Summer 2026") is True

    def test_matches_coop_with_hyphen(self):
        assert is_internship("Co-op Position") is True

    def test_matches_coop_no_hyphen(self):
        assert is_internship("Coop Rotation") is True

    def test_matches_coop_with_space(self):
        assert is_internship("Co Op Role") is True

    def test_case_insensitive(self):
        assert is_internship("INTERN") is True

    def test_false_for_fulltime_role(self):
        assert is_internship("Software Engineer") is False

    def test_false_for_senior_manager(self):
        assert is_internship("Senior Manager") is False


class TestIsFullTime:
    def test_is_exact_negation_of_is_internship(self):
        titles = [
            "Software Engineer",
            "Software Engineer Intern",
            "Co-op Role",
            "Manager",
            "Internship Program",
        ]
        for title in titles:
            assert is_full_time(title) == (not is_internship(title)), title

    def test_true_for_regular_role(self):
        assert is_full_time("Data Scientist") is True

    def test_false_for_intern_role(self):
        assert is_full_time("Software Engineer Intern") is False


# ── update_icons ──────────────────────────────────────────────────────────────

_ICONS_ID_ENV = {"ICONS_ID": "test_key"}


def _make_company(name="Acme"):
    return Company(name, f"https://{name.lower()}.com", "CSS:.job")


class TestUpdateIcons:
    def test_skips_existing_companies(self):
        icons_data = json.dumps({"Acme": "https://cdn.example.com/acme.png"})
        with patch("builtins.open", mock_open(read_data=icons_data)), \
             patch("phlux.utils.requests.get") as mock_get, \
             patch.dict(os.environ, _ICONS_ID_ENV):
            update_icons([_make_company("Acme")])
        mock_get.assert_not_called()

    def test_fetches_missing_company(self):
        mock_response = MagicMock()
        mock_response.json.return_value = [{"domain": "newco.com"}]
        mock_response.raise_for_status = MagicMock()

        captured = {}
        def capture_dump(data, *args, **kwargs):
            captured["data"] = data

        with patch("builtins.open", mock_open(read_data="{}")), \
             patch("phlux.utils.requests.get", return_value=mock_response), \
             patch("phlux.utils.json.dump", side_effect=capture_dump), \
             patch.dict(os.environ, _ICONS_ID_ENV):
            update_icons([_make_company("NewCo")])

        assert "NewCo" in captured["data"]
        assert "newco.com" in captured["data"]["NewCo"]

    def test_handles_request_exception_gracefully(self):
        with patch("builtins.open", mock_open(read_data="{}")), \
             patch("phlux.utils.requests.get", side_effect=requests.RequestException("timeout")), \
             patch("phlux.utils.json.dump"), \
             patch.dict(os.environ, _ICONS_ID_ENV):
            update_icons([_make_company("BrokenCo")])  # must not raise

    def test_handles_missing_icons_file(self):
        mock_response = MagicMock()
        mock_response.json.return_value = [{"domain": "newco.com"}]
        mock_response.raise_for_status = MagicMock()

        read_mock = mock_open()
        read_mock.side_effect = [FileNotFoundError, MagicMock()]

        captured = {}
        def capture_dump(data, *args, **kwargs):
            captured["data"] = data

        with patch("builtins.open", read_mock), \
             patch("phlux.utils.requests.get", return_value=mock_response), \
             patch("phlux.utils.json.dump", side_effect=capture_dump), \
             patch.dict(os.environ, _ICONS_ID_ENV):
            update_icons([_make_company("NewCo")])

        assert "NewCo" in captured.get("data", {})

    def test_handles_empty_api_response(self):
        mock_response = MagicMock()
        mock_response.json.return_value = []  # IndexError on [0]
        mock_response.raise_for_status = MagicMock()

        with patch("builtins.open", mock_open(read_data="{}")), \
             patch("phlux.utils.requests.get", return_value=mock_response), \
             patch("phlux.utils.json.dump"), \
             patch.dict(os.environ, _ICONS_ID_ENV):
            update_icons([_make_company("EmptyCo")])  # must not raise
