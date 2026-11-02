"""Fetch a company's home page and likely careers pages, politely, without a browser.

A company's job board is usually one or two clicks from its home page, so the
crawl reads the home page, then the links whose address or text says careers
or jobs (best first), then the usual places (``/careers``, ``/jobs``,
``careers.<domain>``…). It stays on the company's own domain and stops after
:data:`MAX_PAGES` requests. Redirects count: ``/careers`` often redirects
straight to ``jobs.lever.co/<slug>``, and a page's final URL is part of what
gets searched.

Sites behind a bot wall (a Cloudflare challenge, Akamai, DataDome…) are left
alone: the first walled page ends the crawl and is reported, never worked
around.
"""
from __future__ import annotations

import heapq
import logging
import re
from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

from ..adapters.base import get, soup
from .names import host, registrable_domain

logger = logging.getLogger(__name__)

# Requests per company site, redirects not counted.
MAX_PAGES = 8
PAGE_TIMEOUT = 15
# Career links followed from each page, best first.
LINKS_PER_PAGE = 4
# Bigger pages are cut here before being searched.
MAX_HTML = 3_000_000

GUESS_PATHS = ("/careers", "/jobs", "/company/careers", "/about/careers")
GUESS_SUBDOMAINS = ("careers", "jobs")

_CAREER_PATH = re.compile(
    r"/(?:careers?|jobs|join(?:-us|-the-team)?|open-(?:positions|roles)|openings|work-with-us|hiring|vacancies)(?:[/.?#]|$)",
    re.IGNORECASE,
)
_CAREER_TEXT = re.compile(
    r"\bcareers?\b|\bjobs?\b|join (?:us|the team|our team)|we'?re hiring|open (?:roles|positions)|openings|work (?:with|at) us",
    re.IGNORECASE,
)
_SKIP_HREF = re.compile(r"^(?:mailto:|tel:|javascript:|#)|\.(?:pdf|png|jpe?g|gif|svg|webp|mp4|zip)(?:[?#]|$)", re.I)

# Markers of a bot wall's challenge page, by vendor.
WALLS = {
    "Cloudflare": ("cf-chl-", "challenge-platform", "cf_chl_opt", "<title>Just a moment...</title>"),
    "Akamai": ("Access Denied</h1>", "errors.edgesuite.net"),
    "PerimeterX": ("px-captcha", "_pxAppId"),
    "Imperva": ("_Incapsula_Resource", "Incapsula incident"),
    "DataDome": ("captcha-delivery.com", "datadome"),
    "Vercel": ("Vercel Security Checkpoint",),
    "Sucuri": ("Sucuri WebSite Firewall",),
}


@dataclass
class Page:
    """A fetched page: where it ended up, the URLs it passed through, and its HTML."""

    url: str
    html: str
    redirects: List[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Everything worth searching for a board: the URLs, then the HTML."""
        return "\n".join([*self.redirects, self.url, self.html])


def wall_of(status: int, html: str) -> str:
    """Return the bot wall vendor whose challenge *html* is, or ""."""
    if status < 400 and "<title>Just a moment...</title>" not in html:
        return ""
    sample = html[:200_000]
    for vendor, markers in WALLS.items():
        if any(marker in sample for marker in markers):
            return vendor
    return ""


def normalize_url(url: str) -> str:
    """Return *url* with a scheme (https unless given) and without its fragment."""
    url = url.strip()
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url.lstrip("/")
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, ""))


def site_name(html: str) -> str:
    """Return the name a page gives its site (``og:site_name``, else the start of its title), or ""."""
    page = soup(html)
    meta = page.select_one("meta[property='og:site_name'][content]")
    if meta and meta["content"].strip():
        return meta["content"].strip()
    title = page.title.get_text(" ", strip=True) if page.title else ""
    name = re.split(r"\s+[|\-–—:·]\s+", title)[0].strip()
    return name if 0 < len(name) <= 40 else ""


def career_score(url: str, text: str) -> int:
    """Return how much a link looks like the way to a company's jobs (0: not at all)."""
    parts = urlsplit(url)
    score = 0
    if _CAREER_PATH.search(parts.path or "/"):
        score += 2
    if host(url).split(".")[0] in GUESS_SUBDOMAINS:
        score += 2
    if _CAREER_TEXT.search(text):
        score += 1
    return score


class Crawler:
    """Walks one company's site, best careers candidates first, for at most *max_pages* requests.

    Iterate :meth:`pages`; afterwards :attr:`blocked` names a bot wall that
    stopped the crawl, :attr:`error` why the home page could not be read, and
    :attr:`domains` every domain the site turned out to live on (a home page
    may redirect to a new domain after a rename).
    """

    def __init__(self, start: str, max_pages: int = MAX_PAGES):
        self.start = normalize_url(start)
        self.domains: Set[str] = {registrable_domain(self.start)}
        self.max_pages = max_pages
        self.fetched = 0
        self.blocked = ""
        self.error = ""
        self._queue: List[Tuple[Tuple[int, int, int, int], str, int]] = []
        self._seen: Set[str] = set()
        self._order = 0

    def pages(self) -> Iterator[Page]:
        """Yield each page read, best careers candidates first."""
        self._push(self.start, tier=0, depth=0, score=0)
        while self._queue and self.fetched < self.max_pages and not self.blocked:
            _, url, depth = heapq.heappop(self._queue)
            page = self._fetch(url, home=self.fetched == 0)
            if page is None:
                if self.fetched == 1 and (self.error or self.blocked):
                    return
                continue
            if depth == 0:
                self.domains.add(registrable_domain(page.url))
            for link, score in self.career_links(page):
                self._push(link, tier=1, depth=depth + 1, score=score)
            if depth == 0:
                self._push_guesses(page.url)
            yield page

    def career_links(self, page: Page) -> List[Tuple[str, int]]:
        """Return the page's best links to careers pages on the company's own site."""
        scored = []
        for anchor in soup(page.html).select("a[href]"):
            href = anchor["href"].strip()
            if not href or _SKIP_HREF.search(href):
                continue
            url = normalize_url(urljoin(page.url, href))
            if registrable_domain(url) not in self.domains:
                continue
            score = career_score(url, anchor.get_text(" ", strip=True))
            if score:
                scored.append((url, score))
        scored.sort(key=lambda pair: -pair[1])
        best: List[Tuple[str, int]] = []
        for url, score in scored:
            if url.rstrip("/") not in self._seen and all(url != u for u, _ in best):
                best.append((url, score))
        return best[:LINKS_PER_PAGE]

    def _push_guesses(self, home: str) -> None:
        parts = urlsplit(home)
        for path in GUESS_PATHS:
            self._push(urlunsplit((parts.scheme, parts.netloc, path, "", "")), tier=2, depth=1, score=0)
        domain = registrable_domain(home)
        for sub in GUESS_SUBDOMAINS:
            self._push(f"https://{sub}.{domain}/", tier=2, depth=1, score=0)

    def _push(self, url: str, tier: int, depth: int, score: int) -> None:
        key = url.rstrip("/")
        if key in self._seen:
            return
        self._seen.add(key)
        self._order += 1
        heapq.heappush(self._queue, ((tier, depth, -score, self._order), url, depth))

    def _fetch(self, url: str, home: bool) -> Optional[Page]:
        self.fetched += 1
        try:
            response = get(url, timeout=PAGE_TIMEOUT, headers={"Accept": "text/html,application/xhtml+xml"})
        except requests.HTTPError as error:
            response = error.response
            vendor = wall_of(response.status_code, response.text) if response is not None else ""
            if vendor:
                self.blocked = f"{vendor} bot wall on {url}"
            elif home:
                self.error = f"{url} answered {response.status_code if response is not None else 'an error'}"
            return None
        except (requests.RequestException, ValueError) as error:
            if home:
                self.error = f"{url} unreachable ({type(error).__name__})"
            return None
        for seen in [r.url for r in response.history] + [response.url]:
            self._seen.add(seen.rstrip("/"))
        vendor = wall_of(response.status_code, response.text)
        if vendor:
            self.blocked = f"{vendor} bot wall on {url}"
            return None
        if "html" not in response.headers.get("Content-Type", "text/html"):
            return None
        return Page(response.url, response.text[:MAX_HTML], [r.url for r in response.history])
