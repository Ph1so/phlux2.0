"""Tests for phlux/robotics/forecast.py."""
from datetime import date

import pandas as pd
import pytest

from phlux.robotics.forecast import (
    DUE,
    LATE,
    LATER,
    OPEN,
    SOON,
    UNKNOWN,
    Opening,
    cycle_of,
    forecast,
    openings,
)


class TestCycleOf:
    @pytest.mark.parametrize("day, season, year, cycle", [
        (date(2025, 7, 1), None, None, 2026),       # July starts the next summer's hiring
        (date(2026, 6, 30), None, None, 2026),
        (date(2026, 8, 3), "summer", 2026, 2026),   # a late posting for the summer just gone
        (date(2026, 6, 10), "summer", 2027, 2027),  # an early one just before the cycle starts
        (date(2025, 11, 22), "summer", 2027, 2026),  # a one-off more than a year ahead
        (date(2025, 9, 1), "", 2027, 2026),         # a bare year may be the graduation year
        (date(2025, 9, 1), "fall", 2025, 2026),
    ])
    def test_cycle(self, day, season, year, cycle):
        assert cycle_of(day, season, year) == cycle


def frame(rows):
    """An analytics-shaped postings frame; each row needs company, date and title fields."""
    defaults = {"source": "2026", "is_internship": True, "is_duplicate": False, "is_junk_title": False,
                "company_is_junk": False, "is_bulk_day": False, "season": "", "target_year": None,
                "is_seed": False}
    df = pd.DataFrame([{**defaults, **row} for row in rows])
    df["date"] = pd.to_datetime(df["date"])
    return df


class TestOpenings:
    def test_first_internship_of_each_cycle(self):
        df = frame([
            {"company": "Acme", "date": "2025-06-01", "is_internship": False},  # first look: a full-time role
            {"company": "Acme", "date": "2025-09-02"},
            {"company": "Acme", "date": "2025-08-14"},
            {"company": "Acme", "date": "2026-08-20"},
        ])
        assert openings(df)["Acme"] == {
            2026: Opening(2026, date(2025, 8, 14), False),
            2027: Opening(2027, date(2026, 8, 20), False),
        }

    def test_seed_rows_and_a_first_day_backlog_are_upper_bounds(self):
        df = frame([
            {"company": "Acme", "date": "2025-08-01", "is_seed": True},
            {"company": "Beta", "date": "2025-10-03"},  # Beta's first scrape
            {"company": "Beta", "date": "2025-10-09"},
        ])
        found = openings(df)
        assert found["Acme"][2026] == Opening(2026, date(2025, 8, 1), True)
        assert found["Beta"][2026] == Opening(2026, date(2025, 10, 3), True)

    def test_every_season_on_request(self):
        df = frame([
            {"company": "Acme", "date": "2025-06-01", "is_internship": False},
            {"company": "Acme", "date": "2025-08-03", "season": "fall", "title": "Controls Co-op, Fall 2026"},
            {"company": "Acme", "date": "2025-09-10", "season": "summer"},
        ])
        from phlux.robotics.forecast import season_rows
        assert [r.season for r in season_rows(df)] == ["summer"]
        assert [r.season for r in season_rows(df, summer_only=False)] == ["fall", "summer"]

    def test_uncertain_rows_kept_as_backlog_on_request(self):
        from phlux.robotics.forecast import season_rows
        df = frame([
            {"company": "Acme", "date": "2025-06-01", "is_internship": False},
            {"company": "Acme", "date": "2025-08-01", "is_bulk_day": True},
            {"company": "Junk", "date": "2025-06-01", "is_internship": False},
            {"company": "Junk", "date": "2025-09-01", "company_is_junk": True},
            {"company": "Acme", "date": "2025-08-02", "is_duplicate": True},
        ])
        assert season_rows(df) == []
        kept = season_rows(df, keep_uncertain=True)
        assert [(r.company, r.backlog) for r in kept] == [("Acme", True), ("Junk", True)]

    def test_leaves_out_artifacts_and_off_season_internships(self):
        df = frame([
            {"company": "Acme", "date": "2025-06-01", "is_internship": False},
            {"company": "Acme", "date": "2025-08-01", "is_bulk_day": True},
            {"company": "Acme", "date": "2025-08-02", "is_duplicate": True},
            {"company": "Acme", "date": "2025-08-03", "season": "fall"},
            {"company": "Acme", "date": "2025-08-04", "is_junk_title": True},
            {"company": "Acme", "date": "2025-09-10", "season": "summer"},
        ])
        assert openings(df)["Acme"] == {2026: Opening(2026, date(2025, 9, 10), False)}


class TestForecast:
    TODAY = date(2026, 11, 1)

    def status(self, last=None, opened=None):
        history = {}
        if last:
            history[2026] = Opening(2026, last, False)
        if opened:
            history[2027] = Opening(2027, opened, False)
        [result] = forecast(["Acme"], {"Acme": history}, self.TODAY)
        return result

    @pytest.mark.parametrize("last, status", [
        (date(2025, 11, 20), SOON),
        (date(2025, 12, 20), LATER),
        (date(2025, 10, 20), DUE),
        (date(2025, 9, 10), LATE),
    ])
    def test_status_follows_last_cycle_moved_forward_a_year(self, last, status):
        result = self.status(last=last)
        assert result.status == status
        assert result.expected == last.replace(year=2026)
        assert result.cycle == 2027

    def test_open_once_this_cycle_has_an_internship(self):
        result = self.status(last=date(2025, 9, 10), opened=date(2026, 9, 1))
        assert result.status == OPEN
        assert result.opened.first_seen == date(2026, 9, 1)

    def test_unknown_without_last_cycle(self):
        assert self.status().status == UNKNOWN
        assert forecast(["Nobody"], {}, self.TODAY)[0].status == UNKNOWN

    def test_leap_day_moves_to_the_28th(self):
        [result] = forecast(["Acme"], {"Acme": {2024: Opening(2024, date(2024, 2, 29), False)}}, date(2025, 1, 1))
        assert result.expected == date(2025, 2, 28)

    def test_as_dict_is_json_ready(self):
        result = self.status(last=date(2025, 11, 20)).as_dict()
        assert result["expected"] == "2026-11-20"
        assert result["last"] == {"cycle": 2026, "first_seen": "2025-11-20", "on_or_before": False}
        assert result["opened"] is None
