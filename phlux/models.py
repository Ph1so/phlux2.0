"""Dataclasses used across the project."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class Company:
    """Representation of a company entry in ``companies.csv``."""

    name: str
    link: str
    selector: str


@dataclass
class ScrapeResult:
    """Results returned by a scraper for a specific company."""

    name: str
    jobs: List[str]
    link: str

