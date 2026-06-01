"""Tests for phlux/scraping.py."""
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from phlux.models import Company, ScrapeResult
from phlux.scraping import Actions, autoApply, load_company_data, process_jobs


# ── Actions ───────────────────────────────────────────────────────────────────

class TestActions:
    def test_get_type_css(self):
        assert Actions([]).get_type("CSS:.job-title") == "CSS"

    def test_get_type_click(self):
        assert Actions([]).get_type("CLICK:#load-more") == "CLICK"

    def test_get_type_filter(self):
        assert Actions([]).get_type("FILTER:intern") == "FILTER"

    def test_get_selector_basic(self):
        assert Actions([]).get_selector("CSS:.job-title") == ".job-title"

    def test_get_selector_filter_keyword(self):
        assert Actions([]).get_selector("FILTER:intern") == "intern"

    def test_get_selector_strips_pointer_flag(self):
        assert Actions([]).get_selector("CLICK:#btn:pointer") == "#btn"

    def test_has_flag_true(self):
        assert Actions([]).has_flag("CLICK:#btn:pointer", "pointer") is True

    def test_has_flag_false(self):
        assert Actions([]).has_flag("CLICK:#btn", "pointer") is False

    def test_is_iterable(self):
        actions = Actions(["CSS:.x", "CLICK:#y", "FILTER:intern"])
        assert list(actions) == ["CSS:.x", "CLICK:#y", "FILTER:intern"]

    def test_empty_actions_iterable(self):
        assert list(Actions([])) == []


# ── load_company_data ─────────────────────────────────────────────────────────

class TestLoadCompanyData:
    def test_parses_csv_correctly(self, tmp_path):
        csv_file = tmp_path / "companies.csv"
        csv_file.write_text(
            "Name,Link,ClassName\nAcme,https://acme.com,CSS:.job\n",
            encoding="utf-8",
        )
        companies = load_company_data(csv_file)
        assert len(companies) == 1
        assert companies[0].name == "Acme"
        assert companies[0].link == "https://acme.com"
        assert companies[0].selector == "CSS:.job"

    def test_strips_whitespace_and_quotes(self, tmp_path):
        csv_file = tmp_path / "companies.csv"
        csv_file.write_text(
            "Name,Link,ClassName\n Acme , 'https://acme.com' , CSS:.job \n",
            encoding="utf-8",
        )
        companies = load_company_data(csv_file)
        assert companies[0].name == "Acme"
        assert companies[0].link == "https://acme.com"
        assert companies[0].selector == "CSS:.job"

    def test_returns_empty_list_for_header_only_csv(self, tmp_path):
        csv_file = tmp_path / "companies.csv"
        csv_file.write_text("Name,Link,ClassName\n", encoding="utf-8")
        assert load_company_data(csv_file) == []

    def test_multiple_rows(self, tmp_path):
        csv_file = tmp_path / "companies.csv"
        csv_file.write_text(
            "Name,Link,ClassName\nAcme,https://acme.com,CSS:.a\nBeta,https://beta.com,CSS:.b\n",
            encoding="utf-8",
        )
        companies = load_company_data(csv_file)
        assert len(companies) == 2
        assert companies[1].name == "Beta"

    def test_raises_for_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_company_data(tmp_path / "nonexistent.csv")


# ── process_jobs ──────────────────────────────────────────────────────────────

class TestProcessJobs:
    def _run(self, data, jobs, name="Acme", link="https://acme.com"):
        new_jobs = {}
        process_jobs(data, ScrapeResult(name, jobs, link), new_jobs)
        return new_jobs

    def test_adds_new_job_to_data(self):
        data = {"companies": {}}
        self._run(data, ["Software Engineer"])
        assert len(data["companies"]["Acme"]) == 1
        assert data["companies"]["Acme"][0]["title"] == "Software Engineer"

    def test_job_entry_has_date(self):
        data = {"companies": {}}
        self._run(data, ["Engineer"])
        date = data["companies"]["Acme"][0]["date"]
        # Date should be M/D format (no leading zeros)
        parts = date.split("/")
        assert len(parts) == 2
        assert all(p.isdigit() for p in parts)

    def test_deduplicates_existing_dict_job(self):
        data = {"companies": {"Acme": [{"title": "Engineer", "date": "1/1"}]}}
        new_jobs = self._run(data, ["Engineer"])
        assert len(data["companies"]["Acme"]) == 1  # no duplicate
        assert "Acme" not in new_jobs.get("companies", {})

    def test_only_new_titles_added(self):
        data = {"companies": {"Acme": [{"title": "Old Job", "date": "1/1"}]}}
        self._run(data, ["Old Job", "New Job"])
        assert len(data["companies"]["Acme"]) == 2
        titles = [j["title"] for j in data["companies"]["Acme"]]
        assert "New Job" in titles

    def test_records_new_jobs_in_accumulator(self):
        data = {"companies": {}}
        new_jobs = self._run(data, ["Engineer"])
        assert "Acme" in new_jobs["companies"]
        assert new_jobs["companies"]["Acme"]["link"] == "https://acme.com"
        assert new_jobs["companies"]["Acme"]["jobs"][0]["title"] == "Engineer"

    def test_normalizes_newline_in_title(self):
        data = {"companies": {}}
        self._run(data, ["Engineer\nLevel 3"])
        assert data["companies"]["Acme"][0]["title"] == "Engineer - Level 3"

    def test_handles_legacy_string_job_format(self):
        data = {"companies": {"Acme": ["Old Job"]}}
        new_jobs = self._run(data, ["Old Job", "New Job"])
        titles = [
            (j["title"] if isinstance(j, dict) else j)
            for j in data["companies"]["Acme"]
        ]
        assert "Old Job" in titles
        assert "New Job" in titles
        assert titles.count("Old Job") == 1  # not duplicated

    def test_date_uses_month_slash_day_format(self):
        fixed_dt = MagicMock()
        fixed_dt.month = 5
        fixed_dt.day = 31

        data = {"companies": {}}
        with patch("phlux.scraping.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_dt
            self._run(data, ["Engineer"])

        assert data["companies"]["Acme"][0]["date"] == "5/31"

    def test_empty_job_list_adds_nothing(self):
        data = {"companies": {}}
        new_jobs = self._run(data, [])
        assert data["companies"].get("Acme", []) == []
        assert "Acme" not in new_jobs.get("companies", {})


# ── autoApply ─────────────────────────────────────────────────────────────────

class TestAutoApply:
    def test_raises_without_gh_token(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="GH_TOKEN not set"):
                autoApply(["Software Engineer"], "https://careers.example.com")

    def test_dispatches_workflow_for_job(self):
        element_mock = MagicMock()
        element_mock.get_attribute.return_value = "12345"

        driver_mock = MagicMock()
        wait_mock = MagicMock()
        wait_mock.until.return_value = element_mock

        post_mock = MagicMock()
        post_mock.return_value.status_code = 204

        with patch("phlux.scraping.get_driver", return_value=driver_mock), \
             patch("phlux.scraping.WebDriverWait", return_value=wait_mock), \
             patch("phlux.scraping.requests.post", post_mock), \
             patch.dict(os.environ, {"GH_TOKEN": "fake_token"}):
            autoApply(["Software Engineer"], "https://careers.example.com")

        post_mock.assert_called_once()
        call_kwargs = post_mock.call_args
        assert "Authorization" in call_kwargs.kwargs.get("headers", call_kwargs[1].get("headers", {}))

    def test_skips_job_with_no_seqno(self):
        element_mock = MagicMock()
        element_mock.get_attribute.return_value = None  # no seqno

        driver_mock = MagicMock()
        wait_mock = MagicMock()
        wait_mock.until.return_value = element_mock

        post_mock = MagicMock()

        with patch("phlux.scraping.get_driver", return_value=driver_mock), \
             patch("phlux.scraping.WebDriverWait", return_value=wait_mock), \
             patch("phlux.scraping.requests.post", post_mock), \
             patch.dict(os.environ, {"GH_TOKEN": "fake_token"}):
            autoApply(["Software Engineer"], "https://careers.example.com")

        post_mock.assert_not_called()
