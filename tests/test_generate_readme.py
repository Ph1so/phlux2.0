"""Tests for generate_readme.py."""
import json
import re
from unittest.mock import mock_open, patch

import pytest

from datetime import date

from generate_readme import (
    generate_listings,
    generate_readme,
    load_jobs,
    parse_found_date,
)


# ── load_jobs ─────────────────────────────────────────────────────────────────

class TestLoadJobs:
    def test_returns_companies_dict(self, tmp_path):
        storage = {"companies": {"Acme": [{"title": "Engineer", "date": "5/1"}]}}
        f = tmp_path / "storage.json"
        f.write_text(json.dumps(storage), encoding="utf-8")
        result = load_jobs(str(f))
        assert result == {"Acme": [{"title": "Engineer", "date": "5/1"}]}

    def test_returns_empty_dict_when_companies_key_missing(self, tmp_path):
        f = tmp_path / "storage.json"
        f.write_text("{}", encoding="utf-8")
        assert load_jobs(str(f)) == {}

    def test_raises_for_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_jobs(str(tmp_path / "nonexistent.json"))


# ── generate_readme ───────────────────────────────────────────────────────────

def _call_generate(jobs, links, icons=None):
    icons_data = json.dumps(icons or {})
    with patch("generate_readme.update_icons"), \
         patch("generate_readme.load_company_data", return_value=[]), \
         patch("builtins.open", mock_open(read_data=icons_data)):
        return generate_readme(jobs, links)


class TestGenerateReadme:
    def test_contains_job_count(self):
        jobs = {"Acme": [{"title": "Engineer", "date": "5/1"}, {"title": "Intern", "date": "5/2"}]}
        links = {"Acme": "https://acme.com"}
        readme = _call_generate(jobs, links)
        assert "2 roles" in readme

    def test_sorts_by_date_descending(self):
        jobs = {
            "Acme": [
                {"title": "Old Job", "date": "2026-05-01"},
                {"title": "New Job", "date": "2027-01-05"},
            ]
        }
        links = {"Acme": "https://acme.com"}
        readme = _call_generate(jobs, links)
        assert readme.index("New Job") < readme.index("Old Job")

    def test_handles_legacy_string_job_format(self):
        jobs = {"Acme": ["Just a string role"]}
        links = {"Acme": "https://acme.com"}
        readme = _call_generate(jobs, links)
        assert "1 roles" in readme

    def test_escapes_pipe_in_title(self):
        jobs = {"Acme": [{"title": "Software | Hardware Engineer", "date": "5/1"}]}
        links = {"Acme": "https://acme.com"}
        readme = _call_generate(jobs, links)
        assert "\\|" in readme

    def test_uses_hash_link_for_unknown_company(self):
        jobs = {"UnknownCorp": [{"title": "Dev", "date": "5/1"}]}
        links = {}  # company not in links
        readme = _call_generate(jobs, links)
        assert 'href="#"' in readme

    def test_leaves_undated_backlog_out(self):
        jobs = {"Acme": [{"title": "Engineer", "date": "N/A"}]}
        links = {"Acme": "https://acme.com"}
        readme = _call_generate(jobs, links)  # must not raise
        assert "Engineer" not in readme
        assert "1 roles" in readme

    def test_includes_company_link(self):
        jobs = {"Acme": [{"title": "Engineer", "date": "5/1"}]}
        links = {"Acme": "https://acme.com/careers"}
        readme = _call_generate(jobs, links)
        assert "https://acme.com/careers" in readme

    def test_includes_icon_img_when_provided(self):
        jobs = {"Acme": [{"title": "Engineer", "date": "5/1"}]}
        links = {"Acme": "https://acme.com"}
        icons = {"Acme": "https://cdn.example.com/acme.png"}
        readme = _call_generate(jobs, links, icons=icons)
        assert "<img" in readme
        assert "https://cdn.example.com/acme.png" in readme

    def test_skips_empty_company(self):
        jobs = {"Acme": [], "Beta": [{"title": "Dev", "date": "5/1"}]}
        links = {"Acme": "https://acme.com", "Beta": "https://beta.com"}
        readme = _call_generate(jobs, links)
        # Acme has no postings, only Beta should contribute a row
        assert "Dev" in readme

    def test_trims_rows_to_fit_byte_budget(self):
        jobs = {"Acme": [{"title": f"Role {i}", "date": "2026-09-01"} for i in range(500)]}
        icons_data = json.dumps({})
        with patch("builtins.open", mock_open(read_data=icons_data)):
            readme = generate_readme(jobs, {"Acme": "https://acme.com"}, max_bytes=20_000)
        assert len(readme.encode("utf-8")) <= 20_000
        assert "Role 0" in readme and "Role 499" not in readme
        assert "500 roles" in readme

    def test_caps_row_count(self):
        jobs = {"Acme": [{"title": f"Role {i}", "date": "2026-09-01"} for i in range(5)]}
        with patch("builtins.open", mock_open(read_data="{}")):
            readme = generate_readme(jobs, {}, max_rows=2)
        assert readme.count("<tr>") == 3  # header + 2 rows

    def test_fills_from_archive_after_rollover(self):
        jobs = {"Acme": [{"title": "Still Open", "date": "N/A"}]}
        archives = [{"Acme": [{"title": "Still Open", "date": "2026-09-20"}]},
                    {"Acme": [{"title": "Ancient", "date": "5/1"}]}]
        with patch("builtins.open", mock_open(read_data="{}")):
            readme = generate_readme(jobs, {}, archives)
        assert "Still Open" in readme
        assert "Ancient" not in readme  # archive M/D has no recoverable year


# ── parse_found_date ──────────────────────────────────────────────────────────

class TestParseFoundDate:
    def test_iso(self):
        assert parse_found_date("2026-09-27") == date(2026, 9, 27)

    def test_legacy_md_is_most_recent_past_occurrence(self):
        today = date(2027, 1, 3)
        assert parse_found_date("12/30", today) == date(2026, 12, 30)
        assert parse_found_date("1/2", today) == date(2027, 1, 2)

    def test_legacy_md_off_for_archives(self):
        assert parse_found_date("5/1", legacy_md=False) is None

    def test_na(self):
        assert parse_found_date("N/A") is None


# ── generate_listings ─────────────────────────────────────────────────────────

class TestGenerateListings:
    def test_one_page_per_month_plus_index(self):
        jobs = {"Acme": [{"title": "A", "date": "2026-10-02"}]}
        archives = [{"Acme": [{"title": "B", "date": "2026-09-01"}]}]
        pages = generate_listings(jobs, {"Acme": "https://acme.com"}, archives)
        assert set(pages) == {"2026-10.md", "2026-09.md", "README.md"}
        assert "[Acme][c0]" in pages["2026-10.md"]
        assert "[c0]: https://acme.com" in pages["2026-10.md"]
        assert "2026-10" in pages["README.md"]

    def test_splits_oversized_month(self):
        jobs = {"Acme": [{"title": f"Role {i}", "date": "2026-10-02"} for i in range(400)]}
        pages = generate_listings(jobs, {"Acme": "https://acme.com"}, max_bytes=5_000)
        parts = [name for name in pages if name.startswith("2026-10-")]
        assert len(parts) > 1
        assert all(len(pages[p].encode("utf-8")) <= 5_000 for p in parts)
        assert sum(len(re.findall(r"\| Role \d", pages[p])) for p in parts) == 400

    def test_backlog_skips_titles_dated_in_archive(self):
        jobs = {"Acme": [{"title": "Known", "date": "N/A"}, {"title": "Fresh", "date": "N/A"}]}
        archives = [{"Acme": [{"title": "Known", "date": "2026-09-01"}]}]
        pages = generate_listings(jobs, {}, archives)
        assert "Fresh" in pages["backlog.md"]
        assert "Known" not in pages["backlog.md"]
