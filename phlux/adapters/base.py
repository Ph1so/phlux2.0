"""Shared plumbing for adapters: HTTP with backoff, paging, HTML parsing, registry.

An adapter reads one kind of job system or company site without a browser. It
is a function ``fetch(url) -> List[Posting]`` registered under a name with
:func:`adapter`; a ``companies.csv`` row selects it with ``@name`` and gives the
URL. Adapters read their filters from that URL (as the board would), so a
person opening the link sees what the scraper reads.

Every posting needs a stable ``source:id`` key: storage uses it to tell an
edited title from a new posting, and to switch a company over from browser
scraping without alerting on its backlog (see phlux.scraping.switching_to_ids).
Use the site's own job id; only when a site exposes none, fall back to the job's
URL, and only when it has no URL either, to the title (:func:`title_id`).
"""
from __future__ import annotations

import logging
import time
from typing import Callable, Dict, Iterable, List, Optional
from urllib.parse import parse_qs, unquote, urlsplit

import requests
from bs4 import BeautifulSoup

from ..models import Posting

logger = logging.getLogger(__name__)

TIMEOUT = 30
# Some sites refuse requests' default user agent.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
# Rate-limited sites answer 429; wait this long, doubling, before each retry.
BACKOFF_SECONDS = 5
RETRIES_429 = 3
# A guard against a site whose paging never ends.
MAX_PAGES = 200

ADAPTERS: Dict[str, Callable[[str], List[Posting]]] = {}


def adapter(name: str):
    """Register the decorated ``fetch(url)`` as the ``@name`` adapter."""

    def register(fetch: Callable[[str], List[Posting]]):
        if name in ADAPTERS:
            raise ValueError(f"Adapter {name!r} registered twice")
        ADAPTERS[name] = fetch
        return fetch

    return register


def request(method: str, url: str, session: Optional[requests.Session] = None, **kwargs) -> requests.Response:
    """Send a request with browser-like headers, retrying 429s with backoff.

    Raises:
        requests.HTTPError: For any other error status, or a 429 that outlasts the retries.
    """
    kwargs.setdefault("timeout", TIMEOUT)
    kwargs["headers"] = {**HEADERS, **kwargs.get("headers", {})}
    send = (session or requests).request
    wait = BACKOFF_SECONDS
    for attempt in range(RETRIES_429 + 1):
        response = send(method, url, **kwargs)
        if response.status_code != 429 or attempt == RETRIES_429:
            break
        logger.info("429 from %s; retrying in %ss", urlsplit(url).netloc, wait)
        time.sleep(wait)
        wait *= 2
    response.raise_for_status()
    return response


def get(url: str, **kwargs) -> requests.Response:
    return request("GET", url, **kwargs)


def post(url: str, **kwargs) -> requests.Response:
    return request("POST", url, **kwargs)


def query(url: str) -> Dict[str, List[str]]:
    """Return *url*'s query parameters with ``name[]`` keys folded into ``name``."""
    params: Dict[str, List[str]] = {}
    for key, values in parse_qs(urlsplit(url).query, keep_blank_values=True).items():
        params.setdefault(key.removesuffix("[]"), []).extend(values)
    return params


def first(params: Dict[str, List[str]], key: str, default: str = "") -> str:
    """Return the first value of *key* in parsed query *params*, or *default*."""
    values = params.get(key)
    return values[0] if values else default


def path_slug(url: str, index: int = 0) -> str:
    """Return a path segment of *url* (the first by default), URL-decoded."""
    parts = [p for p in urlsplit(url).path.split("/") if p]
    if len(parts) <= index:
        raise ValueError(f"No path segment {index} in {url}")
    return unquote(parts[index])


def paged(fetch_page: Callable[[int], List[Posting]], delay: float = 0.0,
          max_pages: int = MAX_PAGES) -> List[Posting]:
    """Collect postings from ``fetch_page(0)``, ``fetch_page(1)``… until one comes back empty.

    Postings already seen (same id) are dropped, and a page made only of seen
    postings also ends the walk, which stops sites that repeat their last page.
    *delay* seconds are slept between pages, for rate-limited sites.
    """
    seen: set = set()
    postings: List[Posting] = []
    for page in range(max_pages):
        if page and delay:
            time.sleep(delay)
        fresh = [p for p in fetch_page(page) if p.id not in seen]
        if not fresh:
            break
        seen.update(p.id for p in fresh)
        postings.extend(fresh)
    else:
        logger.warning("Stopped after %d pages", max_pages)
    return postings


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def text(node) -> str:
    """Return *node*'s visible text with whitespace collapsed."""
    return " ".join(node.get_text(" ").split())


def title_id(source: str, title: str) -> str:
    """Last-resort key for a site that gives a posting neither an id nor a URL."""
    return f"{source}:title:{' '.join(title.split())}"


def unique(postings: Iterable[Posting]) -> List[Posting]:
    """Drop repeated ids, keeping the first."""
    seen: set = set()
    out = []
    for p in postings:
        if p.id not in seen:
            seen.add(p.id)
            out.append(p)
    return out
