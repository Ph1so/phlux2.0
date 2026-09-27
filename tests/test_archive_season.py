"""Tests for archive_season.py."""
import json
from datetime import date
from unittest.mock import patch

import pytest

import archive_season


def test_to_iso_resolves_years_and_keeps_na():
    companies = {"Acme": [{"title": "a", "date": "N/A"}, {"title": "b", "date": "12/30"},
                          {"title": "c", "date": "1/2"}, "legacy"]}
    out = archive_season.to_iso(companies, date(2025, 6, 6), date(2026, 1, 6))
    assert [r["date"] for r in out["Acme"]] == ["N/A", "2025-12-30", "2026-01-02", "N/A"]
    assert out["Acme"][3]["title"] == "legacy"


def test_archive_moves_storage_and_turns_on_seeding(tmp_path):
    storage = tmp_path / "storage.json"
    storage.write_text(json.dumps({"companies": {"Acme": [{"title": "a", "date": "9/1"}]}}))
    with patch.object(archive_season, "PREV_YEARS_DIR", tmp_path / "prev"):
        target = archive_season.archive("2026", storage, date(2026, 1, 6), today=date(2026, 9, 27))
        with pytest.raises(FileExistsError):
            archive_season.archive("2026", storage, date(2026, 1, 6), today=date(2026, 9, 27))
    assert json.loads(target.read_text())["companies"]["Acme"][0]["date"] == "2026-09-01"
    assert json.loads(storage.read_text()) == {"seed_new_companies": True, "companies": {}}
