"""Turn the raw scrape history into an analysis-ready table.

The scraper stores only ``{title, date}`` per posting, where ``date`` is a bare
``M/D`` stamp of the day the title was first seen. Three steps make that usable:

1. :mod:`phlux.analytics.clean` — flag duplicates, seed backlogs, mass re-detection
   days and junk scrapes, so artifacts stop looking like hiring waves.
2. :mod:`phlux.analytics.dates` — reconstruct the year each posting belongs to.
3. :mod:`phlux.analytics.titles` — parse season, target year, level, degree and
   domain out of the title text.

:func:`build_dataset` runs all three and returns the tidy frame.
"""
from .dataset import build_dataset, load_known_companies, load_source_rows, read_dataset
from .sources import SOURCES, Source, iter_sources
from .titles import ParsedTitle, parse_title

__all__ = [
    "build_dataset",
    "load_known_companies",
    "load_source_rows",
    "read_dataset",
    "SOURCES",
    "Source",
    "iter_sources",
    "ParsedTitle",
    "parse_title",
]
