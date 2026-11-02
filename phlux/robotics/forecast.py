"""Forecast when each company will open its summer internships, from past seasons.

Most companies open summer internships about the same time every year, so the
day a company's first internship appeared last season is a fair guess for this
season. The guess is only as good as that first day, and the scrape history
blurs it in two ways, both of which turn an exact date into an upper bound
("opened by Sep 2"):

* **Already open when tracking started.** Postings live on a file's first
  scrape (seed rows) have no open date at all.
* **Already open when the company was added.** A company's first scrape in a
  file records its backlog with that day's date (see the analytics package's
  ``backlogDays``).

A recruiting *cycle* is named for the summer it hires for. Most postings don't
name their year, so a posting belongs to the cycle of its date, with cycles
turning over in July, when the first companies start hiring for the summer
after next. Only "Summer <year>" in a title overrides that (a bare year is as
often the graduation year, "Class of 2027"), and only for the two cases that
are common: a late posting for the summer just gone, and an early one in the
May or June before a cycle starts. A posting more than a year ahead, like
Citadel's "Summer Internship 2027" in November 2025, is a one-off rather than
the company opening, so it stays in its date's cycle.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional

# Summer N's recruiting starts in July of N-1.
CYCLE_START_MONTH = 7
# How far ahead an expected opening counts as "soon", and how long after it a
# company still counts as "due" rather than "late".
SOON_DAYS = 45
DUE_DAYS = 30

# Statuses, in the order the dashboard lists them.
OPEN, DUE, SOON, LATER, LATE, UNKNOWN = "open", "due", "soon", "later", "late", "unknown"


def cycle_of(day: date, season: Optional[str] = None, target_year: Optional[float] = None) -> int:
    """Return the summer a posting dated *day* hires for (see the module docstring)."""
    by_date = day.year + (1 if day.month >= CYCLE_START_MONTH else 0)
    if season == "summer" and target_year:
        year = int(target_year)
        if year == by_date - 1 or (year == by_date + 1 and CYCLE_START_MONTH - 2 <= day.month < CYCLE_START_MONTH):
            return year
    return by_date


@dataclass(frozen=True)
class Opening:
    """When a company's first internship of a cycle appeared.

    ``on_or_before`` means it was already open on ``first_seen``, so the real
    opening is that day or earlier.
    """

    cycle: int
    first_seen: date
    on_or_before: bool


@dataclass(frozen=True)
class Forecast:
    """A company's opening status for the current cycle."""

    company: str
    status: str
    cycle: int
    opened: Optional[Opening] = None  # this cycle's opening, once it has one
    last: Optional[Opening] = None  # last cycle's opening, which the forecast follows
    expected: Optional[date] = None  # last cycle's opening moved forward a year

    def as_dict(self) -> dict:
        out = asdict(self)
        for key in ("opened", "last"):
            if out[key]:
                out[key]["first_seen"] = out[key]["first_seen"].isoformat()
        out["expected"] = self.expected.isoformat() if self.expected else None
        return out


@dataclass(frozen=True)
class SeasonRow:
    """One internship posting from the history, with the cycle it belongs to.

    ``backlog`` means it was already open when first seen (see the module
    docstring), so ``day`` is when it was found rather than when it opened.
    """

    company: str
    title: str
    day: date
    cycle: int
    backlog: bool
    season: str = ""
    target_year: int = 0
    degree: str = ""
    domain: str = ""


def season_rows(df, summer_only: bool = True, keep_uncertain: bool = False) -> List[SeasonRow]:
    """Return the history's internships, cycle by cycle.

    Leaves out duplicates and junk titles. Rows from mass re-detection days and
    from companies whose scrape was mostly junk are real postings with doubtful
    dates; they are dropped, or with *keep_uncertain* kept as ``backlog``
    (already open when first seen), which suits browsing but not measuring
    openings.

    Args:
        df: The frame from :func:`phlux.analytics.build_dataset`.
        summer_only: Keep only summer (or season-less) internships, which is
            what openings are measured by; fall, winter and spring co-ops are
            hired on their own clocks.
        keep_uncertain: Keep rows with doubtful dates, marked as backlog.
    """
    uncertain = df["is_bulk_day"].astype(bool) | df["company_is_junk"].astype(bool)
    usable = (
        df["is_internship"].astype(bool)
        & ~df["is_duplicate"].astype(bool)
        & ~df["is_junk_title"].astype(bool)
    )
    if not keep_uncertain:
        usable &= ~uncertain
    if summer_only:
        usable &= df["season"].fillna("").isin(["summer", ""])
    doubtful = set(df.index[uncertain & usable])
    # The first day each company appears in each file: anything stamped then
    # was a backlog already on its careers page.
    first_day = df.groupby(["company", "source"], observed=True)["date"].min().dt.date.to_dict()
    out = []
    for index, row in zip(df.index[usable], df[usable].itertuples(index=False)):
        day = row.date.date()
        year = None if row.target_year != row.target_year else row.target_year  # NaN when absent
        # Missing text is NaN in the frame; test frames carry fewer columns.
        text = lambda field: v if isinstance(v := getattr(row, field, ""), str) else ""  # noqa: E731
        out.append(SeasonRow(
            company=row.company,
            title=text("title").replace("⭐️", "").strip(),
            day=day,
            cycle=cycle_of(day, text("season") or None, year),
            backlog=bool(row.is_seed) or day == first_day.get((row.company, row.source)) or index in doubtful,
            season=text("season"),
            target_year=int(year or 0),
            degree=text("degree"),
            domain=text("domain"),
        ))
    return out


def openings(df) -> Dict[str, Dict[int, Opening]]:
    """Return each company's opening per cycle: its first internship of that cycle."""
    found: Dict[str, Dict[int, Opening]] = {}
    for row in season_rows(df):
        current = found.setdefault(row.company, {}).get(row.cycle)
        if current is None or row.day < current.first_seen or (row.day == current.first_seen and row.backlog):
            found[row.company][row.cycle] = Opening(row.cycle, row.day, row.backlog)
    return found


def forecast(companies: Iterable[str], history: Dict[str, Dict[int, Opening]], today: date) -> List[Forecast]:
    """Return each company's status for the cycle *today* falls in.

    ``open``: it has posted an internship this cycle. Otherwise, by last
    cycle's opening moved forward a year: ``soon`` (within :data:`SOON_DAYS`),
    ``due`` (passed less than :data:`DUE_DAYS` ago), ``late`` (passed longer
    ago), ``later`` (further off), or ``unknown`` without last cycle's opening.
    """
    cycle = cycle_of(today)
    out = []
    for company in companies:
        cycles = history.get(company, {})
        opened, last = cycles.get(cycle), cycles.get(cycle - 1)
        expected = _a_year_after(last.first_seen) if last else None
        if opened:
            status = OPEN
        elif not expected:
            status = UNKNOWN
        elif expected < today - timedelta(days=DUE_DAYS):
            status = LATE
        elif expected <= today:
            status = DUE
        elif expected <= today + timedelta(days=SOON_DAYS):
            status = SOON
        else:
            status = LATER
        out.append(Forecast(company, status, cycle, opened, last, expected))
    return out


def _a_year_after(day: date) -> date:
    try:
        return day.replace(year=day.year + 1)
    except ValueError:  # Feb 29
        return day.replace(year=day.year + 1, day=28)
