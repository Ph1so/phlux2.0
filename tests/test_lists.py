"""Tests for phlux/lists.py and the picker's server-side helpers."""
import json

import pytest

from phlux.config import load_company_list_setting
from phlux.lists import (
    CompanyList,
    available_lists,
    filter_companies,
    load_company_list,
    resolve_list_path,
    save_company_list,
    select_companies,
    slugify,
)
from phlux.models import Company
from phlux.picker import activate_list, build_session, save_list_payload
from phlux.scraping import load_company_data


@pytest.fixture
def companies():
    return [
        Company("Microsoft", "https://microsoft.com", "CSS:.a"),
        Company("Nvidia", "https://nvidia.com", "CSS:.b"),
        Company("Tesla", "https://tesla.com", "CSS:.c"),
    ]


@pytest.fixture
def lists_dir(tmp_path):
    d = tmp_path / "lists"
    d.mkdir()
    return d


def write_list(lists_dir, stem, payload):
    path = lists_dir / f"{stem}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# ── resolve_list_path ─────────────────────────────────────────────────────────

class TestResolveListPath:
    def test_bare_stem_lands_in_lists_dir(self, lists_dir):
        assert resolve_list_path("robotics", lists_dir) == lists_dir / "robotics.json"

    def test_file_name_lands_in_lists_dir(self, lists_dir):
        assert resolve_list_path("robotics.json", lists_dir) == lists_dir / "robotics.json"

    def test_path_with_directory_is_used_as_given(self, lists_dir):
        from pathlib import Path
        assert resolve_list_path("custom/robotics.json", lists_dir) == Path("custom/robotics.json")

    def test_absolute_path_is_unchanged(self, tmp_path, lists_dir):
        target = tmp_path / "elsewhere.json"
        assert resolve_list_path(target, lists_dir) == target


# ── load_company_list ─────────────────────────────────────────────────────────

class TestLoadCompanyList:
    def test_reads_full_document(self, lists_dir):
        write_list(lists_dir, "robotics", {
            "name": "Robotics",
            "description": "hardware only",
            "created": "2026-09-17",
            "companies": ["Nvidia", "Tesla"],
        })
        result = load_company_list("robotics", lists_dir)
        assert result.name == "Robotics"
        assert result.description == "hardware only"
        assert result.companies == ["Nvidia", "Tesla"]

    def test_accepts_bare_array(self, lists_dir):
        write_list(lists_dir, "quick", ["Nvidia", "Tesla"])
        result = load_company_list("quick", lists_dir)
        assert result.companies == ["Nvidia", "Tesla"]
        assert result.name == "quick"

    def test_strips_whitespace_and_drops_blanks(self, lists_dir):
        write_list(lists_dir, "messy", {"companies": [" Nvidia ", "", "   ", "Tesla"]})
        assert load_company_list("messy", lists_dir).companies == ["Nvidia", "Tesla"]

    def test_missing_file_raises(self, lists_dir):
        with pytest.raises(FileNotFoundError):
            load_company_list("nope", lists_dir)

    def test_non_string_entries_raise(self, lists_dir):
        write_list(lists_dir, "bad", {"companies": ["Nvidia", 7]})
        with pytest.raises(ValueError):
            load_company_list("bad", lists_dir)

    def test_scalar_document_raises(self, lists_dir):
        write_list(lists_dir, "bad", "Nvidia")
        with pytest.raises(ValueError):
            load_company_list("bad", lists_dir)


# ── save / available ──────────────────────────────────────────────────────────

class TestSaveCompanyList:
    def test_round_trips(self, lists_dir):
        original = CompanyList(name="Robotics", companies=["Nvidia"], description="d")
        path = save_company_list(original, "robotics", lists_dir)
        assert path == lists_dir / "robotics.json"
        assert load_company_list("robotics", lists_dir).companies == ["Nvidia"]

    def test_stamps_created_date(self, lists_dir):
        save_company_list(CompanyList(name="R", companies=[]), "r", lists_dir)
        assert load_company_list("r", lists_dir).created

    def test_defaults_file_name_from_list_name(self, lists_dir):
        path = save_company_list(CompanyList(name="Big Tech!", companies=[]), None, lists_dir)
        assert path.name == "big-tech.json"

    def test_available_lists_sorted(self, lists_dir):
        write_list(lists_dir, "zeta", [])
        write_list(lists_dir, "alpha", [])
        assert [p.stem for p in available_lists(lists_dir)] == ["alpha", "zeta"]

    def test_available_lists_missing_dir(self, tmp_path):
        assert available_lists(tmp_path / "gone") == []


class TestSlugify:
    @pytest.mark.parametrize("raw,expected", [
        ("Robotics", "robotics"),
        ("Big Tech", "big-tech"),
        ("  Quant / HFT  ", "quant-hft"),
        ("!!!", "untitled"),
        ("", "untitled"),
    ])
    def test_slugify(self, raw, expected):
        assert slugify(raw) == expected


# ── filter_companies ──────────────────────────────────────────────────────────

class TestFilterCompanies:
    def test_keeps_only_named(self, companies):
        assert [c.name for c in filter_companies(companies, ["Tesla"])] == ["Tesla"]

    def test_preserves_csv_order(self, companies):
        result = filter_companies(companies, ["Tesla", "Microsoft"])
        assert [c.name for c in result] == ["Microsoft", "Tesla"]

    def test_matching_is_case_and_space_insensitive(self, companies):
        assert [c.name for c in filter_companies(companies, [" nVIDIA "])] == ["Nvidia"]

    def test_unknown_names_are_skipped(self, companies, caplog):
        result = filter_companies(companies, ["Tesla", "Ghost Corp"])
        assert [c.name for c in result] == ["Tesla"]
        assert "ghost corp" in caplog.text.lower()

    def test_empty_names_selects_nothing(self, companies):
        assert filter_companies(companies, []) == []


# ── select_companies ──────────────────────────────────────────────────────────

class TestSelectCompanies:
    def test_none_returns_everything(self, companies):
        assert select_companies(companies, None) == companies

    def test_empty_string_returns_everything(self, companies):
        assert select_companies(companies, "") == companies

    def test_applies_named_list(self, companies, lists_dir):
        write_list(lists_dir, "robotics", {"companies": ["Nvidia", "Tesla"]})
        result = select_companies(companies, "robotics", lists_dir)
        assert [c.name for c in result] == ["Nvidia", "Tesla"]

    def test_stale_list_still_runs(self, companies, lists_dir):
        write_list(lists_dir, "stale", {"companies": ["Nvidia", "Deleted Co"]})
        assert [c.name for c in select_companies(companies, "stale", lists_dir)] == ["Nvidia"]


# ── load_company_data filtering ───────────────────────────────────────────────

class TestLoadCompanyDataNames:
    @pytest.fixture
    def csv_file(self, tmp_path):
        path = tmp_path / "companies.csv"
        path.write_text(
            "Name,Link,ClassName\n"
            "Acme,https://acme.com,CSS:.a\n"
            "Beta,https://beta.com,CSS:.b\n",
            encoding="utf-8",
        )
        return path

    def test_names_none_keeps_all(self, csv_file):
        assert len(load_company_data(csv_file)) == 2

    def test_names_filters(self, csv_file):
        result = load_company_data(csv_file, names=["Beta"])
        assert [c.name for c in result] == ["Beta"]
        assert result[0].link == "https://beta.com"

    def test_empty_names_selects_nothing(self, csv_file):
        assert load_company_data(csv_file, names=[]) == []


# ── config ────────────────────────────────────────────────────────────────────

class TestCompanyListSetting:
    def test_missing_key_is_none(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text('{"EMAIL": {}}', encoding="utf-8")
        assert load_company_list_setting(cfg) is None

    def test_blank_is_none(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text('{"COMPANY_LIST": "   "}', encoding="utf-8")
        assert load_company_list_setting(cfg) is None

    def test_null_is_none(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text('{"COMPANY_LIST": null}', encoding="utf-8")
        assert load_company_list_setting(cfg) is None

    def test_returns_trimmed_value(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text('{"COMPANY_LIST": " robotics "}', encoding="utf-8")
        assert load_company_list_setting(cfg) == "robotics"

    def test_repo_config_points_at_a_real_list(self):
        """The committed config must never reference a list that doesn't exist."""
        ref = load_company_list_setting()
        if ref is not None:
            assert resolve_list_path(ref).is_file(), f"config.json COMPANY_LIST '{ref}' is missing"


# ── picker server helpers ─────────────────────────────────────────────────────

class TestPickerHelpers:
    @pytest.fixture
    def repo(self, tmp_path):
        (tmp_path / "companies.csv").write_text(
            "Name,Link,ClassName\n"
            "Nvidia,https://nvidia.com,CSS:.a\n"
            "Acme,https://acme.com,CSS:.b\n",
            encoding="utf-8",
        )
        (tmp_path / "icons.json").write_text(
            json.dumps({"Nvidia": "https://cdn.example/nvidia.png"}), encoding="utf-8"
        )
        (tmp_path / "industries.csv").write_text(
            "Name,Sector,RoboticsTier,RoboticsSegment\n"
            "Nvidia,robotics,adjacent,sensors_silicon\n",
            encoding="utf-8",
        )
        (tmp_path / "config.json").write_text('{"EMAIL": {}}', encoding="utf-8")
        (tmp_path / "lists").mkdir()
        return tmp_path

    def session(self, repo):
        return build_session(
            repo / "companies.csv", repo / "icons.json", repo / "industries.csv",
            repo / "lists", repo / "config.json",
        )

    def test_session_includes_every_company(self, repo):
        assert [c["name"] for c in self.session(repo)["companies"]] == ["Nvidia", "Acme"]

    def test_session_joins_icons_and_industries(self, repo):
        nvidia = self.session(repo)["companies"][0]
        assert nvidia["icon"] == "https://cdn.example/nvidia.png"
        assert nvidia["sector"] == "robotics"
        assert nvidia["segment"] == "sensors_silicon"

    def test_session_tolerates_companies_without_metadata(self, repo):
        acme = self.session(repo)["companies"][1]
        assert acme["icon"] == "" and acme["sector"] == ""

    def test_session_tolerates_missing_side_files(self, repo):
        (repo / "icons.json").unlink()
        (repo / "industries.csv").unlink()
        assert len(self.session(repo)["companies"]) == 2

    def test_session_lists_saved_lists(self, repo):
        write_list(repo / "lists", "robotics", {"name": "Robotics", "companies": ["Nvidia"]})
        assert self.session(repo)["lists"] == [
            {"stem": "robotics", "name": "Robotics", "description": "", "companies": ["Nvidia"]}
        ]

    def test_session_skips_unreadable_list(self, repo):
        (repo / "lists" / "broken.json").write_text("{{{", encoding="utf-8")
        assert self.session(repo)["lists"] == []

    def test_session_reports_active_list(self, repo):
        (repo / "config.json").write_text('{"COMPANY_LIST": "robotics"}', encoding="utf-8")
        assert self.session(repo)["active"] == "robotics"

    def test_save_writes_file(self, repo):
        result = save_list_payload(
            {"name": "Robotics", "companies": ["Nvidia"]}, repo / "lists"
        )
        assert result["stem"] == "robotics" and result["count"] == 1
        assert load_company_list("robotics", repo / "lists").companies == ["Nvidia"]

    def test_save_requires_a_name(self, repo):
        with pytest.raises(ValueError):
            save_list_payload({"name": "  ", "companies": []}, repo / "lists")

    def test_save_rejects_non_list_companies(self, repo):
        with pytest.raises(ValueError):
            save_list_payload({"name": "R", "companies": "Nvidia"}, repo / "lists")

    @pytest.mark.parametrize("stem", ["../escape", "/etc/passwd", "..", "a/b"])
    def test_save_cannot_escape_lists_dir(self, repo, stem):
        save_list_payload({"name": "R", "stem": stem, "companies": []}, repo / "lists")
        written = list((repo / "lists").glob("*.json"))
        assert len(written) == 1
        assert written[0].parent == repo / "lists"

    def test_activate_sets_config_key(self, repo):
        save_list_payload({"name": "Robotics", "companies": ["Nvidia"]}, repo / "lists")
        activate_list("robotics", repo / "config.json", repo / "lists")
        config = json.loads((repo / "config.json").read_text())
        assert config["COMPANY_LIST"] == "robotics"

    def test_activate_preserves_other_config_keys(self, repo):
        (repo / "config.json").write_text('{"EMAIL": {"to": "a@b.com"}}', encoding="utf-8")
        save_list_payload({"name": "Robotics", "companies": []}, repo / "lists")
        activate_list("robotics", repo / "config.json", repo / "lists")
        config = json.loads((repo / "config.json").read_text())
        assert config["EMAIL"] == {"to": "a@b.com"}

    def test_activate_empty_stem_clears_key(self, repo):
        (repo / "config.json").write_text('{"COMPANY_LIST": "robotics"}', encoding="utf-8")
        activate_list("", repo / "config.json", repo / "lists")
        assert "COMPANY_LIST" not in json.loads((repo / "config.json").read_text())

    def test_activate_unknown_list_raises(self, repo):
        with pytest.raises(ValueError):
            activate_list("ghost", repo / "config.json", repo / "lists")


# ── Dependency isolation ──────────────────────────────────────────────────────

class TestPickerRunsWithoutScrapingStack:
    """The picker only reads companies.csv and lists/, so it must import even
    when Selenium and friends are not installed."""

    SCRAPING_DEPS = ("selenium", "undetected_chromedriver", "webdriver_manager", "tenacity")

    def _import_with_deps_blocked(self, target):
        import subprocess
        import sys
        from pathlib import Path

        repo_root = Path(__file__).resolve().parent.parent
        script = f"""
import sys

BLOCKED = {self.SCRAPING_DEPS!r}

class Blocker:
    def find_module(self, name, path=None):
        return self.find_spec(name, path)
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            raise ImportError(f"blocked for test: {{name}}")
        return None

sys.meta_path.insert(0, Blocker())
sys.path.insert(0, {str(repo_root)!r})
import {target}
assert not any(m.split(".")[0] in BLOCKED for m in sys.modules), "scraping stack was imported"
print("ok")
"""
        return subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, cwd=repo_root
        )

    def test_phlux_package_imports(self):
        result = self._import_with_deps_blocked("phlux")
        assert result.returncode == 0, result.stderr

    def test_picker_imports(self):
        result = self._import_with_deps_blocked("phlux.picker")
        assert result.returncode == 0, result.stderr

    def test_picker_main_imports(self):
        result = self._import_with_deps_blocked("phlux.picker.__main__")
        assert result.returncode == 0, result.stderr

    def test_blocker_actually_blocks(self):
        """Guard against the test passing because the blocker does nothing."""
        result = self._import_with_deps_blocked("phlux.scraping")
        assert result.returncode != 0
