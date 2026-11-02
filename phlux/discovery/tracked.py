"""Recognize candidates that phlux already tracks, however they are spelled.

``companies.csv`` names a company once, but a source may spell it differently
("Relativity Space" vs "Relativity"), list it under a former name, or point at
a site whose board slug is all the CSV has (``jobs.ashbyhq.com/1x`` for 1X at
1x.tech). Each tracked row is indexed by:

* its name, without case, punctuation or legal suffix (:mod:`phlux.discovery.names`);
* the domain of its link, when the link is on the company's own site;
* the account slug and board of its link, when the link is a job board.

A candidate matching one of these (:meth:`TrackedIndex.match`) is skipped
before its site is crawled. A board detected later is checked again against
the boards already read (:meth:`TrackedIndex.match_board`), which is how
"Relativity Space" is found to be the tracked "Relativity".

Names that agree only once generic words are dropped (:meth:`TrackedIndex.similar`)
are not enough to skip a company: Navier AI (navier.ai, engineering software)
is not the tracked Navier (navierboat.com, boats), and General Aviation
Company is not General Motors. Such a candidate is checked and reported with
a note instead.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from ..config import DEFAULT_CONFIG_PATH, load_company_list_setting
from ..lists import load_companies, load_company_list
from ..models import Company
from .fingerprints import find_boards
from .identify import company_domain
from .names import MIN_CORE, core_key, domain_label, legal_key, name_key, name_variants, slug_key
from .sources import Candidate


@dataclass(frozen=True)
class Tracked:
    """A ``companies.csv`` row, and whether the active list (what the bot scrapes) includes it."""

    name: str
    listed: bool


@dataclass(frozen=True)
class Match:
    tracked: Tracked
    why: str


class TrackedIndex:
    """Every ``companies.csv`` row, indexed by name, core name, domain and board slug."""

    def __init__(self, companies: Iterable[Company], active: Optional[Iterable[str]] = None):
        active_names = None if active is None else {n.strip().casefold() for n in active}
        self.names: Dict[str, Tracked] = {}
        self.cores: Dict[str, Tracked] = {}
        self.domains: Dict[str, Tracked] = {}
        self.slugs: Dict[str, Tracked] = {}
        self.boards: Dict[Tuple[str, str], Tracked] = {}
        for company in companies:
            listed = active_names is None or company.name.strip().casefold() in active_names
            self._add(company, Tracked(company.name, listed))

    @classmethod
    def load(cls, csv_path: Path, config_path: Path = DEFAULT_CONFIG_PATH) -> "TrackedIndex":
        """Index ``companies.csv``, marking rows in the active list named by ``config.json``."""
        setting = load_company_list_setting(config_path)
        active = load_company_list(setting).companies if setting else None
        return cls(load_companies(csv_path), active)

    def _add(self, company: Company, tracked: Tracked) -> None:
        self.names.setdefault(legal_key(company.name), tracked)
        core = core_key(company.name)
        if len(core) >= MIN_CORE:
            self.cores.setdefault(core, tracked)
        for url in company.link.split("->"):
            url = url.strip()
            if not url:
                continue
            domain = company_domain(url)
            if domain:
                self.domains.setdefault(domain, tracked)
            for hit in find_boards(url):
                self.boards.setdefault((hit.board, slug_key(hit.slug)), tracked)
                self.slugs.setdefault(slug_key(hit.slug), tracked)

    def match(self, candidate: Candidate) -> Optional[Match]:
        """Return the tracked row *candidate* surely is (same domain, name or board slug), or None."""
        domain = company_domain(candidate.website) if candidate.website else None
        if domain and domain in self.domains:
            return Match(self.domains[domain], f"same domain, {domain}")
        names: List[str] = []
        for name in [candidate.name, *candidate.former_names]:
            names += name_variants(name) or [name]
        for name in names:
            if legal_key(name) in self.names:
                return Match(self.names[legal_key(name)], f"same name, {name!r}")
        keys = [name_key(n) for n in names] + ([domain_label(domain)] if domain else [])
        for key in keys:
            if len(key) >= 2 and key in self.slugs:
                return Match(self.slugs[key], f"its name or domain is the board slug {key!r}")
        return None

    def similar(self, candidate: Candidate) -> Optional[Match]:
        """Return a tracked row whose name agrees with *candidate*'s once generic words are dropped."""
        for name in [candidate.name, *candidate.former_names]:
            core = core_key(name)
            if len(core) >= MIN_CORE and core in self.cores:
                return Match(self.cores[core], f"similar name, {core!r}")
        return None

    def match_board(self, board: str, slug: str) -> Optional[Match]:
        """Return the tracked row already reading this board account, if any."""
        tracked = self.boards.get((board, slug_key(slug)))
        return Match(tracked, f"same {board} board, {slug!r}") if tracked else None
