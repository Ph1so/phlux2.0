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
class ScrapeResult:
    """Results returned by a scraper for a specific company.

    ``ids`` is either empty, or parallel to ``jobs`` with each posting's
    ``board:id`` key (see :mod:`phlux.boards`); only board APIs provide ids.
    """

    name: str
    jobs: List[str]
    link: str
    ids: List[Optional[str]] = field(default_factory=list)

