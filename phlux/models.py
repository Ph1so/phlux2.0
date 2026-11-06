"""Dataclasses used across the project."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Company:
    """Representation of a company entry in ``companies.csv``."""

    name: str
    link: str
    selector: str


@dataclass
class Posting:
    """One job read from a board or site: a stable ``source:id`` key and its title.

    ``location`` is shown in alert emails; it's empty where the source gives none.
    ``url`` is the posting's own page, so alerts can link straight to it; it's
    empty where the source has no page per job. ``description`` is the posting's
    text where the board sends it with the list (Greenhouse, Lever, Ashby); it is
    read for new-grad wording (:mod:`phlux.early_career`) and never stored.
    """

    id: str
    title: str
    location: str = ""
    url: str = ""
    description: str = ""


@dataclass
class ScrapeResult:
    """Results returned by a scraper for a specific company.

    ``ids`` is either empty, or parallel to ``jobs`` with each posting's
    ``board:id`` key (see :mod:`phlux.boards`); only board APIs provide ids.
    ``locations`` and ``urls`` are likewise empty or parallel to ``jobs``.
    """

    name: str
    jobs: List[str]
    link: str
    ids: List[Optional[str]] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    # Per job, the description line that shows it takes new grads, or "".
    early: List[str] = field(default_factory=list)

