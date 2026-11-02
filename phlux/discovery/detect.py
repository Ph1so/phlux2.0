"""Find a company's job board from its website, and check that phlux can read it.

The steps, cheapest and surest first:

1. If the URL given is itself a board (``jobs.lever.co/acme``), use it.
2. Crawl the company's site (:mod:`phlux.discovery.crawl`) and fingerprint
   every page (:mod:`phlux.discovery.fingerprints`). A board the company's own
   site links is trusted; leads like a CareerPuck board are resolved first.
3. Failing that, guess slugs from the name and domain on Greenhouse, Ashby and
   Lever, keeping a board only if it is corroborated as this company's
   (:func:`phlux.discovery.identify.corroborate`). A board whose name is all
   that matches is kept but marked unverified, for a person to check. A
   board the site mentions (``gh_jid`` job links, a board URL built in script)
   is guessed on first, and a job id from the site proves a guess.

Every board found is confirmed by reading it with
:func:`phlux.boards.board_postings`, exactly as the bot will: a board that
fails there (a BambooHR account that redirects to bamboohr.com, a deleted
Greenhouse board) does not count. Postings and internship titles (by
:func:`phlux.utils.is_internship`, the alerts' own test) are counted then.
"""
from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import requests

from ..boards import board_postings
from ..utils import is_internship
from .crawl import MAX_PAGES, Crawler, normalize_url
from .fingerprints import Hit, board_link, find_boards, find_hints, find_unsupported
from .identify import CONFIRMED, IDENTIFY, REJECTED, company_domain, corroborate, resolve_lead
from .names import core_key, display_name, domain_label, name_key, slug_guesses, slug_key

logger = logging.getLogger(__name__)

# Boards read per company before giving up on the ones its site links.
MAX_CONFIRM = 4
# A board with more postings than this gets ``->FILTER:intern``, keeping storage small.
FILTER_ABOVE = 50
SAMPLE_TITLES = 3
GUESS_BOARDS = ("greenhouse", "ashby", "lever")


@dataclass
class Detection:
    """A company's job board as phlux would read it, or why none was found.

    ``verified`` is False for a guessed board whose name is all that ties it
    to the company.
    """

    board: str = ""
    slug: str = ""
    link: str = ""
    evidence: str = ""
    postings: Optional[int] = None
    internships: Optional[int] = None
    internship_titles: List[str] = field(default_factory=list)
    reason: str = ""
    notes: List[str] = field(default_factory=list)
    pages: int = 0
    verified: bool = True

    @property
    def found(self) -> bool:
        return bool(self.board)

    @property
    def action(self) -> str:
        """The row's ClassName: ``@board``, filtered to internships on a big board."""
        return f"@{self.board}" + ("->FILTER:intern" if (self.postings or 0) > FILTER_ABOVE else "")

    def row(self, name: str) -> str:
        """Return the ``companies.csv`` row for this board, quoted as the csv module would."""
        out = io.StringIO()
        csv.writer(out, lineterminator="").writerow([display_name(name), self.link, self.action])
        return out.getvalue()


def confirm(hit: Hit, evidence: str) -> Detection:
    """Read *hit*'s board as the bot would and count its postings and internships.

    Raises whatever the board's reader raises when the board can't be read.
    """
    titles = [" ".join(p.title.split()) for p in board_postings(hit.board, hit.link)]
    interns = [t for t in titles if is_internship(t)]
    return Detection(board=hit.board, slug=hit.slug, link=hit.link, evidence=evidence, postings=len(titles),
                     internships=len(interns), internship_titles=interns[:SAMPLE_TITLES])


def resembles(slug: str, name: str, domains: Set[str]) -> bool:
    """Return True if a board slug looks like the company's name or domain."""
    key = slug_key(slug)
    return bool(key) and key in {name_key(name), core_key(name), *(domain_label(d) for d in domains)}


def _rank(detection: Detection) -> tuple:
    return detection.verified, bool(detection.postings)


class _Search:
    """One company's detection: the hits tried so far and the best board confirmed."""

    def __init__(self, name: str, batch: str = ""):
        self.name = name
        self.batch = batch
        self.best: Optional[Detection] = None
        self.tried: Set[tuple] = set()
        self.failures: List[str] = []
        self.notes: List[str] = []
        self.unsupported: List[str] = []
        # Boards the site mentions without a slug, with the job ids it links.
        self.hints: Dict[str, Set[str]] = {}

    @property
    def done(self) -> bool:
        """True once a verified board with postings is confirmed, or the read budget is spent."""
        return bool(self.best and _rank(self.best) == (True, True)) or len(self.tried) >= MAX_CONFIRM

    def scan(self, text: str, url: str, domains: Set[str], source: str = "") -> None:
        """Fingerprint one page (or URL) and try the boards it names, likeliest first.

        *source* is the company page that led there, when *url* is where it redirected.
        """
        self.unsupported += [ats for ats in find_unsupported(text) if ats not in self.unsupported]
        for board, ids in find_hints(text).items():
            self.hints.setdefault(board, set()).update(ids)
        hits = find_boards(text, url)
        hits.sort(key=lambda h: not resembles(h.slug, self.name, domains))
        for hit in hits:
            if self.done:
                return
            self.attempt(hit, f"linked from {source or url}")

    def attempt(self, hit: Hit, evidence: str, verified: bool = True) -> Optional[Detection]:
        """Resolve and confirm one hit, keeping it if it beats the best so far."""
        board, why_not = resolve_lead(hit)
        if board is None:
            self.notes.append(why_not)
            return None
        if board is not hit:
            evidence = f"{hit.board} {hit.slug!r} reads from it; {evidence}"
        key = (board.board, board.link.lower())
        if key in self.tried:
            return None
        self.tried.add(key)
        try:
            found = confirm(board, evidence)
        except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError) as error:
            self.failures.append(f"{board.board} {board.slug!r} could not be read: {_short(error)}")
            return None
        found.verified = verified
        if self.best is None or _rank(found) > _rank(self.best):
            self.best = found
        return found

    def guess(self, domains: Set[str]) -> None:
        """Try slugs from the name and domain on the public board APIs, keeping a corroborated one."""
        hinted = [b for b in GUESS_BOARDS if b in self.hints]
        slugs = slug_guesses(self.name, domains)
        # The site names its board, so less likely slugs are worth trying there first.
        extra = [f"{s}{suffix}" for s in slugs[:2] for suffix in ("inc", "hq", "careers")]
        tries = [(slug, board) for board in hinted for slug in slugs + extra]
        tries += [(slug, board) for slug in slugs for board in GUESS_BOARDS if board not in hinted]
        for slug, board in dict.fromkeys(tries):
            try:
                identity = IDENTIFY[board](slug)
            except (requests.RequestException, ValueError, KeyError) as error:
                logger.info("%s %r: %s", board, slug, _short(error))
                continue
            if identity is None:
                continue
            verdict, why = corroborate(identity, self.name, domains, self.hints.get(board, ()), self.batch)
            if verdict == REJECTED:
                self.notes.append(f"guessed {board} {slug!r} rejected: {why}")
                continue
            found = self.attempt(Hit(board, slug, board_link(board, slug)),
                                 f"guessed {board} slug {slug!r}; {why}", verified=verdict == CONFIRMED)
            if found and _rank(found) == (True, True):
                return

    def result(self, crawler: Optional[Crawler]) -> Detection:
        detection = self.best or Detection(reason=self.reason(crawler))
        detection.notes = self.failures + self.notes + (
            [f"uses {ats}" for ats in self.unsupported] if detection.found else [])
        detection.pages = crawler.fetched if crawler else 0
        return detection

    def reason(self, crawler: Optional[Crawler]) -> str:
        if self.failures:
            return self.failures[0]
        if self.unsupported:
            return f"uses {', '.join(self.unsupported)}, which phlux has no reader for"
        if crawler and crawler.blocked:
            return f"site blocked: {crawler.blocked}"
        if crawler and crawler.error:
            return f"site unreachable: {crawler.error}"
        pages = crawler.fetched if crawler else 0
        return f"no board linked from its site ({pages} pages) or found under its name"


def _short(error: Exception) -> str:
    return (str(error) or type(error).__name__).splitlines()[0][:200]


def detect(name: str, website: str, batch: str = "", max_pages: int = MAX_PAGES) -> Detection:
    """Return the job board of the company *name* whose website (or careers/board URL) is *website*.

    *batch* is the company's YC batch ("Summer 2024"), which a board naming it confirms a guess.
    """
    search = _Search(name, batch)
    if not website:
        search.guess(set())
        detection = search.result(None)
        if not detection.found:
            detection.reason = "no website, and no board found under its name"
        return detection
    start = normalize_url(website)
    domains = {d for d in [company_domain(start)] if d}
    search.scan(start, start, domains)
    crawler = None
    if not search.done and company_domain(start):
        crawler = Crawler(start, max_pages)
        for page in crawler.pages():
            domains |= {d for d in crawler.domains if company_domain(d)}
            search.scan(page.text, page.url, domains, source=page.redirects[0] if page.redirects else "")
            if search.done:
                break
    if search.best is None:
        search.guess(domains)
    return search.result(crawler)
