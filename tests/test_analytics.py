"""Tests for phlux/analytics — date reconstruction, title parsing, artifact flags."""
from datetime import date

import pandas as pd
import pytest

from phlux.analytics import clean, titles
from phlux.analytics.dates import parse_month_day, resolve_company_dates
from phlux.analytics.sources import Source


# ── Date reconstruction ───────────────────────────────────────────────────────

EPOCH_START = date(2025, 6, 6)
EPOCH_END = date(2026, 1, 6)


def resolve(raw_dates, start=EPOCH_START, end=EPOCH_END):
    return [r.value for r in resolve_company_dates(raw_dates, start, end)]


class TestParseMonthDay:
    def test_parses_single_digits(self):
        assert parse_month_day("1/6") == (1, 6)

    def test_parses_double_digits(self):
        assert parse_month_day("12/19") == (12, 19)

    def test_rejects_out_of_range_month(self):
        with pytest.raises(ValueError):
            parse_month_day("13/1")

    def test_rejects_non_numeric(self):
        with pytest.raises(ValueError):
            parse_month_day("N/A")


class TestResolveCompanyDates:
    def test_dates_after_epoch_start_keep_the_start_year(self):
        assert resolve(["8/8", "8/11", "9/5"]) == [
            date(2025, 8, 8), date(2025, 8, 11), date(2025, 9, 5)
        ]

    def test_year_rolls_over_when_month_day_goes_backwards(self):
        # The only signal that the calendar turned is Dec -> Jan.
        assert resolve(["12/19", "12/30", "1/5"]) == [
            date(2025, 12, 19), date(2025, 12, 30), date(2026, 1, 5)
        ]

    def test_first_date_is_pushed_forward_into_the_epoch(self):
        # A company first seen in January belongs to the epoch's second year, even
        # though there is no earlier row to roll over from.
        assert resolve(["1/5", "1/6"]) == [date(2026, 1, 5), date(2026, 1, 6)]

    def test_na_rows_collapse_onto_the_epoch_start(self):
        assert resolve(["N/A", "N/A", "8/8"]) == [
            EPOCH_START, EPOCH_START, date(2025, 8, 8)
        ]

    def test_na_rows_are_flagged_as_seed(self):
        resolved = resolve_company_dates(["N/A", "8/8"], EPOCH_START, EPOCH_END)
        assert [r.is_seed for r in resolved] == [True, False]

    def test_na_rows_do_not_trigger_a_rollover(self):
        # "N/A" must not become a predecessor, or the following date looks backwards.
        assert resolve(["N/A", "12/1", "12/2"]) == [
            EPOCH_START, date(2025, 12, 1), date(2025, 12, 2)
        ]

    def test_row_dated_the_epoch_start_is_seed(self):
        resolved = resolve_company_dates(["6/6", "8/8"], EPOCH_START, EPOCH_END)
        assert [r.is_seed for r in resolved] == [True, False]

    def test_repeated_same_day_rows_do_not_roll_over(self):
        assert resolve(["9/2", "9/2", "9/2"]) == [date(2025, 9, 2)] * 3

    def test_raw_string_is_preserved(self):
        resolved = resolve_company_dates(["8/8"], EPOCH_START, EPOCH_END)
        assert resolved[0].raw == "8/8"

    def test_unparseable_date_falls_back_to_seed(self):
        resolved = resolve_company_dates(["garbage"], EPOCH_START, EPOCH_END)
        assert resolved[0].is_seed is True
        assert resolved[0].value == EPOCH_START

    def test_impossible_day_is_clamped_to_month_end(self):
        assert resolve(["2/30"], date(2026, 1, 1), date(2026, 12, 31)) == [date(2026, 2, 28)]

    def test_multiple_rollovers(self):
        assert resolve(["7/1", "1/1", "7/1", "1/1"], date(2025, 1, 1), date(2027, 12, 31)) == [
            date(2025, 7, 1), date(2026, 1, 1), date(2026, 7, 1), date(2027, 1, 1)
        ]


class TestSource:
    def test_resolved_end_uses_epoch_end_when_set(self):
        source = Source("x", "x.json", date(2025, 1, 1), date(2025, 12, 31))
        assert source.resolved_end(date(2026, 5, 1)) == date(2025, 12, 31)

    def test_resolved_end_falls_back_to_today_for_the_live_file(self):
        source = Source("x", "x.json", date(2025, 1, 1), None)
        assert source.resolved_end(date(2026, 5, 1)) == date(2026, 5, 1)


# ── Title parsing ─────────────────────────────────────────────────────────────

class TestIsInternship:
    @pytest.mark.parametrize("title", [
        "Software Engineering Intern",
        "2026 Summer Internship",
        "Mechanical Co-Op",
        "Hardware Coop Program",
        "Summer Analyst, Equities",
        "Student Researcher, BS/MS",
        "Manufacturing Apprenticeship",
    ])
    def test_matches(self, title):
        assert titles.is_internship(title) is True

    @pytest.mark.parametrize("title", [
        "Leadership Development Program",
        "Shipping Operations Analyst",
        "Relationship Manager",
        "International Tax Associate",
        "Senior Software Engineer",
    ])
    def test_does_not_match_lookalikes(self, title):
        # phlux.utils.is_internship matches the bare substring "ship" and fires on
        # these; the analytics parser uses word boundaries so charts stay clean.
        assert titles.is_internship(title) is False


class TestParseTitle:
    def test_extracts_season_and_year(self):
        parsed = titles.parse_title("Software Engineer Intern, Summer 2026")
        assert parsed.season == "summer"
        assert parsed.target_year == 2026

    def test_keeps_every_season_in_order_of_appearance(self):
        parsed = titles.parse_title("Student Researcher, Winter/Summer 2026")
        assert parsed.season == "winter"
        assert parsed.seasons == "winter|summer"

    def test_takes_the_first_year_mentioned(self):
        assert titles.parse_title("Summer 2026 Intern, 2027 Grads").target_year == 2026

    def test_missing_fields_are_none(self):
        parsed = titles.parse_title("Software Engineer")
        assert parsed.season is None
        assert parsed.target_year is None
        assert parsed.degree is None

    def test_level_intern(self):
        assert titles.parse_title("Data Science Intern").level == "intern"

    def test_level_new_grad(self):
        assert titles.parse_title("Software Engineer, University Graduate").level == "new_grad"

    @pytest.mark.parametrize("title", [
        "Junior Perception Engineer",
        "2027 Early Career Firmware Engineer",
        "Early-Career Controls Engineer",
        "Quantitative Researcher PhD Graduate (US)",
        "Software Engineer, Infrastructure, PhD, Early Career, 2027 Start",
        "Software Engineer, Class of 2027",
        "New Graduate Engineer, Propulsion (Raptor)",
    ])
    def test_level_new_grad_wordings(self, title):
        assert titles.parse_title(title).level == "new_grad"

    @pytest.mark.parametrize("title, expected", [
        ("Software Engineer - New Grad", True),
        ("Forward Deployed Software Engineer, New Grad", True),
        ("Quantitative Developer, New Grad", True),
        ("Engineer I, PCB - New Grad", True),
        ("Product Designer, New Grad", False),
        ("Area Manager, Early Career (2027)", False),
        ("Junior IT Support Engineer", False),
        ("Solutions Engineer, Early Career", False),
        ("Early Career & University Relations Recruiter", False),
        ("Entry-Level Production Technician", False),
        ("Entry-Level - AI/Machine Learning Researcher", True),
        ("Autonomy Scientist, New Grad", True),
        ("Driving Simulation Researcher, Entry Level", True),
        ("Perception - New Grad", True),
        ("Robot Operator, Entry Level", False),
        ("AI Trainer, Early Career", False),
        ("Robotics Data Collector - Entry Level", False),
        ("Robotics AI Strategy & Program Lead, Early Career", False),
        ("Research Scientist, Materials, Entry Level", False),
        ("Clinical Robot Associate, Entry Level", False),
        ("Associate Robotics Engineer, New Grad", True),
    ])
    def test_is_engineering_role(self, title, expected):
        assert titles.is_engineering_role(title) is expected

    def test_level_unspecified(self):
        assert titles.parse_title("Staff Software Engineer").level == "unspecified"

    def test_intern_wins_over_new_grad(self):
        # "Early Career" often sits alongside an internship title; intern is the
        # more specific claim.
        assert titles.parse_title("Early Career Intern Program").level == "intern"

    def test_degree_reports_the_most_advanced(self):
        parsed = titles.parse_title("Student Researcher, BS/MS, Summer 2026")
        assert parsed.degree == "masters"
        assert parsed.degrees == "masters|bachelors"

    def test_phd_outranks_masters(self):
        assert titles.parse_title("Research Scientist, MS/PhD").degree == "phd"

    @pytest.mark.parametrize("title,domain", [
        ("Machine Learning Software Engineer", "ml_ai"),
        ("Quantitative Trading Intern", "quant_finance"),
        ("Equity Analyst Internship", "quant_finance"),
        ("Data Scientist, Analytics", "data"),
        ("Security Engineer Intern", "security"),
        ("RTL Design Engineer, Silicon", "hardware"),
        ("Chemical Engineering Intern", "other_engineering"),
        ("Backend Software Engineer", "software"),
        ("Associate Product Manager", "product"),
        ("UX Designer Intern", "design"),
        ("Student Researcher", "research"),
        ("Marketing Intern", "business"),
        ("Technical Writer Intern", "business"),
        ("Systems Engineering Intern", "engineering_general"),
        ("Automation Engineer Intern", "engineering_general"),
        ("Rotation Programme", "other"),
    ])
    def test_domain(self, title, domain):
        assert titles.parse_title(title).domain == domain

    def test_named_discipline_outranks_the_engineering_catch_all(self):
        # engineering_general only takes titles no specific rule claimed.
        assert titles.parse_title("Embedded Systems Engineering Intern").domain == "hardware"

    def test_ml_outranks_software(self):
        # Ordering matters: an ML role that also says "software" is an ML role.
        assert titles.parse_title("Software Engineer, AI/Machine Learning").domain == "ml_ai"

    @pytest.mark.parametrize("title", ["Varun for President!", "All Locations", "View all"])
    def test_page_furniture_has_no_role_word(self, title):
        assert titles.parse_title(title).has_role_word is False

    def test_real_title_has_role_word(self):
        assert titles.parse_title("Software Engineer Intern").has_role_word is True


# ── Flagging ──────────────────────────────────────────────────────────────────

def make_frame(rows):
    """Build a minimal postings frame with the columns the flaggers expect."""
    df = pd.DataFrame(rows)
    for column, default in (("source", "test"), ("is_seed", False),
                            ("has_role_word", True), ("is_internship", False)):
        if column not in df:
            df[column] = default
        else:
            df[column] = df[column].fillna(default)
    return df


class TestMarkDuplicates:
    def test_first_appearance_is_kept(self):
        df = clean.mark_duplicates(make_frame([
            {"company": "Acme", "title": "SWE Intern"},
            {"company": "Acme", "title": "SWE Intern"},
        ]))
        assert list(df["is_duplicate"]) == [False, True]

    def test_same_title_at_different_companies_is_not_a_duplicate(self):
        df = clean.mark_duplicates(make_frame([
            {"company": "Acme", "title": "SWE Intern"},
            {"company": "Globex", "title": "SWE Intern"},
        ]))
        assert list(df["is_duplicate"]) == [False, False]


class TestMarkJunk:
    def test_titles_without_role_words_are_flagged(self):
        df = clean.mark_junk(make_frame([
            {"company": "Acme", "title": "All Locations", "has_role_word": False},
            {"company": "Acme", "title": "SWE Intern", "has_role_word": True},
        ]))
        assert list(df["is_junk_title"]) == [True, False]

    def test_company_flagged_when_most_titles_are_junk(self):
        df = clean.mark_junk(make_frame([
            {"company": "Acme", "title": "a", "has_role_word": False},
            {"company": "Acme", "title": "b", "has_role_word": False},
            {"company": "Acme", "title": "SWE Intern", "has_role_word": True},
        ]))
        assert df["company_is_junk"].all()

    def test_company_not_flagged_below_threshold(self):
        df = clean.mark_junk(make_frame([
            {"company": "Acme", "title": "a", "has_role_word": False},
            {"company": "Acme", "title": "SWE Intern", "has_role_word": True},
            {"company": "Acme", "title": "Data Intern", "has_role_word": True},
        ]))
        assert not df["company_is_junk"].any()


class TestMarkBulkDays:
    def test_flags_the_day_far_above_the_epoch_baseline(self):
        rows = []
        # Twelve quiet days, two companies each.
        for day in range(1, 13):
            rows += [{"company": f"C{i}", "title": f"t{day}{i}", "date": day} for i in range(2)]
        # One day where thirty companies "post" at once.
        rows += [{"company": f"C{i}", "title": f"spike{i}", "date": 99} for i in range(30)]

        df = clean.mark_bulk_days(make_frame(rows))
        assert set(df.loc[df["is_bulk_day"], "date"]) == {99}

    def test_small_absolute_days_are_never_flagged(self):
        # A baseline of one company must not make a two-company day an artifact.
        rows = [{"company": "C0", "title": f"t{d}", "date": d} for d in range(1, 11)]
        rows += [{"company": c, "title": "x", "date": 99} for c in ("C0", "C1", "C2")]

        df = clean.mark_bulk_days(make_frame(rows))
        assert not df["is_bulk_day"].any()

    def test_seed_rows_are_never_bulk_days(self):
        rows = [{"company": f"C{i}", "title": f"s{i}", "date": 1, "is_seed": True}
                for i in range(50)]
        rows += [{"company": "C0", "title": "real", "date": 2}]

        df = clean.mark_bulk_days(make_frame(rows))
        assert not df["is_bulk_day"].any()


class TestMarkBulkBatches:
    def test_large_batch_dominating_a_company_is_flagged(self):
        rows = [{"company": "Acme", "title": f"t{i}", "date": 1} for i in range(60)]
        rows += [{"company": "Acme", "title": "later", "date": 2}]

        df = clean.mark_bulk_batches(make_frame(rows))
        assert df.loc[df["date"] == 1, "is_bulk_batch"].all()
        assert not df.loc[df["date"] == 2, "is_bulk_batch"].any()

    def test_small_batch_is_not_flagged_even_at_full_share(self):
        rows = [{"company": "Acme", "title": f"t{i}", "date": 1} for i in range(5)]
        df = clean.mark_bulk_batches(make_frame(rows))
        assert not df["is_bulk_batch"].any()

    def test_large_batch_that_is_a_small_share_is_not_flagged(self):
        # A company that posts steadily can clear the row threshold on one day
        # without that day being a re-read of its whole page.
        rows = [{"company": "Acme", "title": f"a{i}", "date": 1} for i in range(60)]
        rows += [{"company": "Acme", "title": f"b{d}-{i}", "date": d}
                 for d in range(2, 12) for i in range(30)]

        df = clean.mark_bulk_batches(make_frame(rows))
        assert not df["is_bulk_batch"].any()


class TestApplyFlags:
    def base_rows(self):
        return [
            {"company": "Acme", "title": "SWE Intern", "date": 1, "is_internship": True},
            {"company": "Acme", "title": "SWE Intern", "date": 2, "is_internship": True},
            {"company": "Acme", "title": "Seeded", "date": 0, "is_seed": True,
             "is_internship": False},
            {"company": "Acme", "title": "All Locations", "date": 3,
             "has_role_word": False, "is_internship": False},
        ]

    def test_keep_excludes_duplicate_seed_and_junk(self):
        df = clean.apply_flags(make_frame(self.base_rows()))
        assert list(df["keep"]) == [True, False, False, False]

    def test_suspect_does_not_remove_rows(self):
        df = clean.apply_flags(make_frame(self.base_rows()))
        assert "is_suspect" in df
        assert len(df) == 4


class TestCompanyQuality:
    def test_summarises_per_company(self):
        df = clean.apply_flags(make_frame([
            {"company": "Acme", "title": "SWE Intern", "date": 1, "is_internship": True},
            {"company": "Acme", "title": "SWE Intern", "date": 2, "is_internship": True},
        ]))
        summary = clean.company_quality(df)
        row = summary.iloc[0]
        assert row["rows"] == 2
        assert row["kept"] == 1
        assert row["duplicates"] == 1

    def test_configured_companies_with_no_postings_appear(self):
        df = clean.apply_flags(make_frame([
            {"company": "Acme", "title": "SWE Intern", "date": 1, "is_internship": True},
        ]))
        summary = clean.company_quality(df, ["Acme", "Ghost"])
        ghost = summary[summary["company"] == "Ghost"].iloc[0]
        assert bool(ghost["scraped_nothing"]) is True
        assert ghost["rows"] == 0


class TestIsoDates:
    def test_iso_dates_pass_through_and_anchor_later_md_rows(self):
        from datetime import date

        from phlux.analytics.dates import resolve_company_dates

        out = resolve_company_dates(
            ["2026-12-30", "1/2"], date(2026, 9, 27), date(2027, 6, 1)
        )
        assert [r.value for r in out] == [date(2026, 12, 30), date(2027, 1, 2)]
        assert not any(r.is_seed for r in out)
