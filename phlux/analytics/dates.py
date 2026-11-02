"""Step 2: turn bare ``M/D`` scrape dates back into real calendar dates.

Since 2026-09-27 the scraper writes ISO ``YYYY-MM-DD`` stamps, which pass through
as-is; the reconstruction below only matters for the older ``M/D`` rows.

``process_jobs`` in :mod:`phlux.scraping` stamps every newly seen posting with
``f"{now.month}/{now.day}"`` and appends it to that company's list, so within a
company the rows are in scrape order and their month/day pairs never go backwards
except when the calendar rolls over into January. That makes the year recoverable:
walk each company's list from the epoch start and bump the year every time the
month/day steps backwards.

A leading run of ``"N/A"`` rows marks the batch that was already on the careers page
the first time the scraper ever looked at that company. Those have no discoverable
open date, so they collapse onto the epoch start and are flagged as seed rows.
"""
from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Sequence, Tuple

logger = logging.getLogger(__name__)

NA_DATE = "N/A"


@dataclass(frozen=True)
class ResolvedDate:
    """A scrape date with its year filled in.

    Attributes:
        value: The reconstructed calendar date.
        raw: The original ``M/D`` string (or ``"N/A"``).
        is_seed: True when the row came from the initial backlog rather than
            from a posting the scraper watched appear.
    """

    value: date
    raw: str
    is_seed: bool


def parse_month_day(raw: str) -> Tuple[int, int]:
    """Parse a ``"M/D"`` scrape stamp into a ``(month, day)`` pair.

    Args:
        raw: Date string as written by the scraper, e.g. ``"3/19"``.

    Returns:
        The month and day as integers.

    Raises:
        ValueError: If *raw* is not two slash-separated integers in range.
    """
    month_str, _, day_str = raw.partition("/")
    month, day = int(month_str), int(day_str)
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        raise ValueError(f"month/day out of range: {raw!r}")
    return month, day


def _parse_iso(raw: str) -> date | None:
    """Return the date for a ``YYYY-MM-DD`` stamp, or ``None`` for anything else."""
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _build_date(year: int, month: int, day: int, context: str) -> date:
    """Build a date, clamping a day that does not exist in that month."""
    last = calendar.monthrange(year, month)[1]
    if day > last:
        logger.warning(
            "%s: %d/%d does not exist in %d, clamping to %d/%d",
            context, month, day, year, month, last,
        )
        day = last
    return date(year, month, day)


def resolve_company_dates(
    raw_dates: Sequence[str],
    epoch_start: date,
    epoch_end: date,
    context: str = "",
) -> List[ResolvedDate]:
    """Reconstruct calendar dates for one company's postings, in scrape order.

    Args:
        raw_dates: The company's ``date`` fields, in the order they appear in the
            JSON file (which is append order — see :func:`phlux.scraping.process_jobs`).
        epoch_start: First day the file can contain. Seed rows land here, and the
            first real date is pushed forward until it is not before this day.
        epoch_end: Last day the file can contain. Only used to warn about rows that
            overshoot it, which would mean the append order is not what we assume.
        context: Label used in log messages, normally the company name.

    Returns:
        One :class:`ResolvedDate` per input, in the same order.
    """
    resolved: List[ResolvedDate] = []
    year = epoch_start.year
    previous: Tuple[int, int] | None = None

    for raw in raw_dates:
        if raw == NA_DATE:
            resolved.append(ResolvedDate(epoch_start, raw, is_seed=True))
            continue

        # Postings stamped since the switch to ISO dates carry their own year.
        iso = _parse_iso(raw)
        if iso is not None:
            year = iso.year
            previous = (iso.month, iso.day)
            resolved.append(ResolvedDate(iso, raw, is_seed=iso == epoch_start))
            continue

        try:
            month, day = parse_month_day(raw)
        except ValueError:
            logger.warning("%s: unparseable date %r, treating as seed", context, raw)
            resolved.append(ResolvedDate(epoch_start, raw, is_seed=True))
            continue

        # Month/day going backwards is the only signal that the year rolled over.
        if previous is not None and (month, day) < previous:
            year += 1

        value = _build_date(year, month, day, context)

        # The first real date has no predecessor to roll over from, so a company
        # first seen in January of the epoch's second year would otherwise be dated
        # a year early. Push it forward until it lands inside the epoch.
        if previous is None:
            while value < epoch_start:
                year += 1
                value = _build_date(year, month, day, context)

        if value > epoch_end:
            logger.warning(
                "%s: resolved %s to %s, past the epoch end %s",
                context, raw, value, epoch_end,
            )

        previous = (month, day)
        # A row dated the epoch start is part of the backlog the scraper found on
        # its first pass, not a posting it watched open.
        resolved.append(ResolvedDate(value, raw, is_seed=value == epoch_start))

    return resolved


def resolve_all(
    companies: dict,
    epoch_start: date,
    epoch_end: date,
) -> dict:
    """Run :func:`resolve_company_dates` over every company in a raw file.

    Args:
        companies: The ``"companies"`` mapping from a storage JSON file.
        epoch_start: First day the file can contain.
        epoch_end: Last day the file can contain.

    Returns:
        Mapping of company name to its list of :class:`ResolvedDate`.
    """
    return {
        name: resolve_company_dates(
            [posting["date"] for posting in postings], epoch_start, epoch_end, name
        )
        for name, postings in companies.items()
    }
