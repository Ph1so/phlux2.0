"""Registry of the raw job-history files and the time window each one covers.

Each JSON file is an *epoch*: a stretch of scraping that starts when the file was
created (or wiped) and ends when it was archived. The epoch boundaries are not
recorded in the files themselves — postings only carry an ``M/D`` string — so they
are pinned here from the repository history. Older postings only carry an ``M/D``
string; since 2026-09-27 new ones are stamped ISO ``YYYY-MM-DD``:

* ``prev_years/2025_internships.json`` holds everything scraped from the first run
  on 2025-06-06 until commit ``2313bab1`` ("new year", 2026-01-06), which moved
  44,760 lines out of ``storage.json`` into that archive.
* ``prev_years/2026_internships.json`` holds 2026-01-06 until the rollover on
  2026-09-27 (``archive_season.py 2026``), which also converted its dates to ISO.
* ``storage.json`` was reset by that rollover and has been filling up since
  2026-09-27. Its first scrape recorded the live backlog as ``"N/A"`` seed rows.

Archiving another year (``python archive_season.py <label>``) means adding a :class:`Source` for the new file and moving
``STORAGE``'s ``epoch_start`` forward; :func:`iter_sources` warns about any file in
``prev_years/`` that nobody registered.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PREV_YEARS_DIR = REPO_ROOT / "prev_years"


@dataclass(frozen=True)
class Source:
    """One raw job-history file and the calendar window it covers.

    Attributes:
        label: Short name for the epoch, used as a column value in the dataset.
        path: Location of the JSON file.
        epoch_start: First day the file could contain. Bare ``M/D`` dates are
            resolved forward from this day, and ``"N/A"`` dates collapse onto it.
        epoch_end: Last day the file can contain, or ``None`` for the live file
            (which runs up to today).
    """

    label: str
    path: Path
    epoch_start: date
    epoch_end: date | None = None

    def resolved_end(self, today: date | None = None) -> date:
        """Return :attr:`epoch_end`, falling back to *today* for the live file."""
        return self.epoch_end or today or date.today()


ARCHIVE_2025 = Source(
    label="2025",
    path=PREV_YEARS_DIR / "2025_internships.json",
    epoch_start=date(2025, 6, 6),
    epoch_end=date(2026, 1, 6),
)

ARCHIVE_2026 = Source(
    label="2026",
    path=PREV_YEARS_DIR / "2026_internships.json",
    epoch_start=date(2026, 1, 6),
    epoch_end=date(2026, 9, 27),
)

STORAGE = Source(
    label="2027",
    path=REPO_ROOT / "storage.json",
    epoch_start=date(2026, 9, 27),
    epoch_end=None,
)

SOURCES: List[Source] = [ARCHIVE_2025, ARCHIVE_2026, STORAGE]


def iter_sources(sources: List[Source] | None = None) -> List[Source]:
    """Return the sources that exist on disk, warning about gaps.

    Args:
        sources: Sources to check. Defaults to :data:`SOURCES`.

    Returns:
        The subset whose files are present.
    """
    sources = sources or SOURCES
    registered = {s.path for s in sources}

    if PREV_YEARS_DIR.is_dir():
        for path in sorted(PREV_YEARS_DIR.glob("*.json")):
            if path not in registered:
                logger.warning(
                    "%s is not registered in phlux.analytics.sources; it will be "
                    "skipped. Add a Source for it to include it.",
                    path.name,
                )

    present = []
    for source in sources:
        if source.path.exists():
            present.append(source)
        else:
            logger.warning("Source %s missing at %s", source.label, source.path)
    return present
