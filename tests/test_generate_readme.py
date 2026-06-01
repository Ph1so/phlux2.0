"""Tests for generate_readme.py."""
import json
from unittest.mock import mock_open, patch

import pytest

from generate_readme import generate_readme, load_jobs


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
                {"title": "Old Job", "date": "1/5"},
                {"title": "New Job", "date": "5/1"},
            ]
        }
        links = {"Acme": "https://acme.com"}
        readme = _call_generate(jobs, links)
        assert readme.index("New Job") < readme.index("Old Job")

    def test_handles_legacy_string_job_format(self):
        jobs = {"Acme": ["Just a string role"]}
        links = {"Acme": "https://acme.com"}
        readme = _call_generate(jobs, links)
        assert "Just a string role" in readme

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

    def test_handles_invalid_date_gracefully(self):
        jobs = {"Acme": [{"title": "Engineer", "date": "N/A"}]}
        links = {"Acme": "https://acme.com"}
        readme = _call_generate(jobs, links)  # must not raise
        assert "Engineer" in readme

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
