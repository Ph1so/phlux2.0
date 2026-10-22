"""Tests for the picker's prune mode (phlux/picker)."""
import json

import pytest

from phlux.picker import build_session, prune_list_payload


@pytest.fixture
def repo(tmp_path):
    """A companies.csv, a lists/ dir with an active 'robotics' list, and config.json."""
    csv_path = tmp_path / "companies.csv"
    csv_path.write_text(
        "Name,Link,ClassName\n"
        "Zoox,https://zoox.example,@lever\n"
        "ABB,https://abb.example,@workday\n"
        "Tesla,https://tesla.example,API:tesla\n"
        "Google,https://google.example,@workday\n",
        encoding="utf-8",
    )
    lists_dir = tmp_path / "lists"
    lists_dir.mkdir()
    (lists_dir / "robotics.json").write_text(
        json.dumps(
            {
                "name": "robotics",
                "description": "Robots",
                "created": "2026-09-17",
                "companies": ["Tesla", "Zoox", "ABB"],
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"EMAIL": "x", "COMPANY_LIST": "robotics"}), encoding="utf-8")
    return {
        "csv_path": csv_path,
        "icons_path": tmp_path / "icons.json",
        "industries_path": tmp_path / "industries.csv",
        "lists_dir": lists_dir,
        "config_path": config_path,
    }


def read_list(repo):
    return json.loads((repo["lists_dir"] / "robotics.json").read_text(encoding="utf-8"))


class TestPruneSession:
    def test_only_active_list_companies_in_csv_order(self, repo):
        session = build_session(**repo, prune=True)
        assert [c["name"] for c in session["companies"]] == ["Zoox", "ABB", "Tesla"]

    def test_describes_list_being_pruned(self, repo):
        prune = build_session(**repo, prune=True)["prune"]
        assert prune["stem"] == "robotics"
        assert prune["name"] == "robotics"
        assert prune["description"] == "Robots"

    def test_normal_session_unchanged(self, repo):
        session = build_session(**repo)
        assert len(session["companies"]) == 4
        assert "prune" not in session

    def test_no_active_list_raises(self, repo):
        repo["config_path"].write_text(json.dumps({"EMAIL": "x"}), encoding="utf-8")
        with pytest.raises(ValueError):
            build_session(**repo, prune=True)


class TestPruneListPayload:
    def test_removes_skipped_and_keeps_metadata(self, repo):
        result = prune_list_payload({"companies": ["Zoox", "Tesla"]}, repo["config_path"], repo["lists_dir"])
        assert result["removed"] == ["ABB"]
        assert result["count"] == 2
        saved = read_list(repo)
        assert saved["companies"] == ["Tesla", "Zoox"]  # original order kept
        assert saved["created"] == "2026-09-17"
        assert saved["description"] == "Robots"

    def test_does_not_touch_config(self, repo):
        before = repo["config_path"].read_text(encoding="utf-8")
        prune_list_payload({"companies": ["Zoox"]}, repo["config_path"], repo["lists_dir"])
        assert repo["config_path"].read_text(encoding="utf-8") == before

    def test_matching_is_case_insensitive(self, repo):
        result = prune_list_payload({"companies": ["zoox", "TESLA", "abb"]}, repo["config_path"], repo["lists_dir"])
        assert result["removed"] == []

    def test_cannot_add_companies(self, repo):
        with pytest.raises(ValueError, match="Google"):
            prune_list_payload({"companies": ["Zoox", "Google"]}, repo["config_path"], repo["lists_dir"])
        assert read_list(repo)["companies"] == ["Tesla", "Zoox", "ABB"]

    def test_malformed_payload_raises(self, repo):
        with pytest.raises(ValueError):
            prune_list_payload({"companies": "Zoox"}, repo["config_path"], repo["lists_dir"])
