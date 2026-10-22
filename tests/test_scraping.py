"""Tests for phlux/scraping.py."""
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from phlux.models import Company, ScrapeResult
from phlux.scraping import (
    MAX_PAGES,
    PRESETS,
    Actions,
    _paginate,
    autoApply,
    board_of,
    expand_presets,
    get_board_jobs,
    load_company_data,
    process_jobs,
    scrape_company,
)
from phlux.boards import Posting


# ── Actions ───────────────────────────────────────────────────────────────────

class FakeButton:
    def __init__(self, attrs=None):
        self.attrs = attrs or {}

    def get_attribute(self, name):
        return self.attrs.get(name)


class FakePager:
    """A driver whose "next" button walks through *pages* of titles."""

    def __init__(self, pages, last_button=None):
        self.pages = pages
        self.index = 0
        self.last_button = last_button
        self.clicks = 0

    def find_elements(self, by, selector):
        if self.index < len(self.pages) - 1:
            return [FakeButton()]
        return [self.last_button] if self.last_button else []

    def execute_script(self, script, element):
        self.clicks += 1
        self.index = min(self.index + 1, len(self.pages) - 1)

    def collect(self):
        return self.pages[self.index]


@pytest.fixture(autouse=False)
def no_sleep():
    clock = iter(range(0, 10**6))
    with patch("phlux.scraping.time.sleep"), \
         patch("phlux.scraping.time.monotonic", side_effect=lambda: next(clock)):
        yield


@pytest.mark.usefixtures("no_sleep")
class TestPaginate:
    def test_collects_every_page_after_the_first(self):
        driver = FakePager([["a"], ["b"], ["c"]])
        assert _paginate(driver, "#next", driver.collect) == ["b", "c"]

    def test_single_page_has_nothing_to_add(self):
        driver = FakePager([["a"]])
        assert _paginate(driver, "#next", driver.collect) == []
        assert driver.clicks == 0

    def test_stops_at_disabled_button(self):
        driver = FakePager([["a"], ["b"]], last_button=FakeButton({"aria-disabled": "true"}))
        assert _paginate(driver, "#next", driver.collect) == ["b"]
        assert driver.clicks == 1

    def test_stops_when_click_leaves_page_unchanged(self):
        driver = FakePager([["a"], ["b"]], last_button=FakeButton())
        assert _paginate(driver, "#next", driver.collect) == ["b"]

    def test_waits_for_half_rendered_page_to_settle(self):
        driver = FakePager([["a"], ["b", "c"]])
        reads = iter([["a"], ["a", "b"], ["b", "c"], ["b", "c"]])
        assert _paginate(driver, "#next", lambda: next(reads)) == ["b", "c"]

    def test_respects_page_cap(self):
        driver = FakePager([[str(i)] for i in range(MAX_PAGES + 5)])
        assert len(_paginate(driver, "#next", driver.collect)) == MAX_PAGES - 1

    def test_workday_preset_paginates(self):
        assert "PAGINATE:" in PRESETS["workday"]


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


# ── expand_presets ────────────────────────────────────────────────────────────

class TestExpandPresets:
    def test_expands_preset(self):
        assert expand_presets("@greenhouse") == PRESETS["greenhouse"]

    def test_chains_with_other_actions(self):
        assert expand_presets("@ashby->FILTER:intern") == PRESETS["ashby"] + "->FILTER:intern"

    def test_is_case_insensitive(self):
        assert expand_presets("@Lever") == PRESETS["lever"]

    def test_leaves_plain_actions_untouched(self):
        assert expand_presets("CLICK:#more->CSS:h3") == "CLICK:#more->CSS:h3"

    def test_unknown_preset_raises(self):
        with pytest.raises(ValueError, match="@nope"):
            expand_presets("@nope")

    def test_every_preset_in_companies_csv_exists(self):
        repo_root = Path(__file__).resolve().parent.parent
        for company in load_company_data(repo_root / "companies.csv"):
            expand_presets(company.selector)


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
        # Date should be ISO YYYY-MM-DD so the year survives
        assert datetime.strptime(date, "%Y-%m-%d")

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

    def test_date_uses_iso_format(self):
        fixed_dt = datetime(2026, 5, 31, 12, 0)

        data = {"companies": {}}
        with patch("phlux.scraping.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_dt
            self._run(data, ["Engineer"])

        assert data["companies"]["Acme"][0]["date"] == "2026-05-31"

    def test_seed_marks_na_and_sends_no_alert(self):
        data = {"companies": {}}
        new_jobs = {}
        process_jobs(data, ScrapeResult("Acme", ["Engineer"], "https://acme.com"), new_jobs, seed=True)
        assert data["companies"]["Acme"] == [{"title": "Engineer", "date": "N/A"}]
        assert "Acme" not in new_jobs.get("companies", {})

    def test_empty_job_list_adds_nothing(self):
        data = {"companies": {}}
        new_jobs = self._run(data, [])
        assert data["companies"].get("Acme", []) == []
        assert "Acme" not in new_jobs.get("companies", {})


class TestProcessJobsWithIds:
    def _run(self, data, jobs, ids, name="Acme"):
        new_jobs = {}
        process_jobs(data, ScrapeResult(name, jobs, "https://acme.com", ids), new_jobs)
        return new_jobs

    def test_new_posting_stores_its_id(self):
        data = {"companies": {"Acme": [{"title": "Old", "date": "2026-10-01", "id": "lever:0"}]}}
        new_jobs = self._run(data, ["Old", "Robotics Engineer"], ["lever:0", "lever:1"])
        assert data["companies"]["Acme"][1]["id"] == "lever:1"
        assert [j["title"] for j in new_jobs["companies"]["Acme"]["jobs"]] == ["Robotics Engineer"]

    def test_renamed_posting_is_not_new(self):
        data = {"companies": {"Acme": [{"title": "Robotics Eng", "date": "2026-10-01", "id": "lever:1"}]}}
        new_jobs = self._run(data, ["Robotics Engineer"], ["lever:1"])
        assert len(data["companies"]["Acme"]) == 1
        assert "Acme" not in new_jobs.get("companies", {})

    def test_stored_title_gets_its_id_recorded(self):
        data = {"companies": {"Acme": [
            {"title": "Planner", "date": "2026-10-01", "id": "lever:9"},
            {"title": "Perception", "date": "2026-10-02"},
        ]}}
        self._run(data, ["Perception"], ["lever:2"])
        assert data["companies"]["Acme"][1] == {"title": "Perception", "date": "2026-10-02", "id": "lever:2"}

    def test_first_board_scrape_is_silent(self):
        # Titles stored by page scrapes, none with an id yet: the API's extra
        # titles are old postings past the first page, so no alert and N/A.
        data = {"companies": {"Acme": [{"title": "Planner", "date": "2026-10-01"}]}}
        new_jobs = self._run(data, ["Planner", "⭐️ Robotics Intern"], ["ashby:1", "ashby:2"])
        assert data["companies"]["Acme"] == [
            {"title": "Planner", "date": "2026-10-01", "id": "ashby:1"},
            {"title": "⭐️ Robotics Intern", "date": "N/A", "id": "ashby:2"},
        ]
        assert "Acme" not in new_jobs.get("companies", {})

    def test_later_board_scrapes_alert(self):
        data = {"companies": {"Acme": [{"title": "Planner", "date": "2026-10-01", "id": "ashby:1"}]}}
        new_jobs = self._run(data, ["Planner", "⭐️ Robotics Intern"], ["ashby:1", "ashby:2"])
        assert [j["title"] for j in new_jobs["companies"]["Acme"]["jobs"]] == ["⭐️ Robotics Intern"]

    def test_new_company_on_a_board_still_alerts(self):
        data = {"companies": {}}
        new_jobs = self._run(data, ["⭐️ Robotics Intern"], ["ashby:2"])
        assert data["companies"]["Acme"][0]["date"] != "N/A"
        assert "Acme" in new_jobs["companies"]


class TestBoardRouting:
    @pytest.mark.parametrize("instructions, board", [
        ("@greenhouse", "greenhouse"),
        ("@Lever->FILTER:intern", "lever"),
        ('"@ashby"', "ashby"),
        ("@workday", None),
        ("CSS:h3", None),
        ("UNDETECTED->API:tesla:Tesla SI", None),
    ])
    def test_board_of(self, instructions, board):
        assert board_of(instructions) == board

    def test_get_board_jobs_filters_stars_and_tidies(self):
        postings = [
            Posting("lever:1", "Robotics  Software Intern"),
            Posting("lever:2", "Senior  Recruiter"),
            Posting("lever:3", "Perception Intern, Whats New"),
        ]
        with patch("phlux.scraping.board_postings", return_value=postings) as fetch:
            titles, ids = get_board_jobs("Acme", "https://jobs.lever.co/acme", "@lever->FILTER:intern")
        fetch.assert_called_once_with("lever", "https://jobs.lever.co/acme")
        assert titles == ["⭐️ Robotics Software Intern", "⭐️ Perception Intern, Whats New"]
        assert ids == ["lever:1", "lever:3"]

    def test_scrape_company_uses_api_for_boards(self):
        with patch("phlux.scraping.board_postings", return_value=[Posting("ashby:1", "Planner")]), \
             patch("phlux.scraping.get_jobs_headless") as headless:
            result = scrape_company(Company("Acme", "https://jobs.ashbyhq.com/acme", "@ashby"))
        headless.assert_not_called()
        assert (result.jobs, result.ids) == (["Planner"], ["ashby:1"])

    def test_scrape_company_uses_browser_otherwise(self):
        with patch("phlux.scraping.get_jobs_headless", return_value=["Planner"]) as headless:
            result = scrape_company(Company("Acme", "https://acme.com/jobs", "CSS:h3"))
        headless.assert_called_once_with("Acme", "https://acme.com/jobs", "CSS:h3")
        assert (result.jobs, result.ids) == (["Planner"], [])


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


# ── ScrapeManager seeding ─────────────────────────────────────────────────────

class TestScrapeCompaniesSeeding:
    def _scrape(self, tmp_path, storage):
        import json
        from concurrent.futures import ThreadPoolExecutor

        from phlux.scraping import ScrapeManager

        path = tmp_path / "storage.json"
        path.write_text(json.dumps(storage), encoding="utf-8")
        companies = [Company("Acme", "https://acme.com", "sel"), Company("Beta", "https://beta.com", "sel")]
        with patch("phlux.scraping.ProcessPoolExecutor", ThreadPoolExecutor), \
             patch("phlux.scraping.get_jobs_headless", return_value=["Old Role", "New Role"]), \
             patch("phlux.config.load_config", return_value={}):
            return ScrapeManager().scrape_companies(companies, storage_path=str(path), max_workers=2)

    def test_flag_seeds_only_companies_with_nothing_stored(self, tmp_path):
        storage = {
            "seed_new_companies": True,
            "companies": {"Acme": [{"title": "Old Role", "date": "2026-09-27"}]},
        }
        result = self._scrape(tmp_path, storage)
        assert [j["date"] for j in result["data"]["companies"]["Beta"]] == ["N/A", "N/A"]
        assert list(result["new_jobs"]["companies"]) == ["Acme"]
        assert result["data"]["seed_new_companies"] is True

    def test_without_flag_every_new_title_alerts(self, tmp_path):
        result = self._scrape(tmp_path, {"companies": {}})
        assert set(result["new_jobs"]["companies"]) == {"Acme", "Beta"}
