"""Read Workday job boards (``*.myworkdayjobs.com``) from the JSON API behind them.

A board URL looks like
``https://<tenant>.<wdN>.myworkdayjobs.com/[<locale>/]<site>[/jobs]?<facet>=<id>&…``
(or ``https://<wdN>.myworkdaysite.com/[<locale>/]recruiting/<tenant>/<site>``).
The page is a script that asks ``POST /wday/cxs/<tenant>/<site>/jobs`` for
20 postings at a time, sending the URL's query parameters as
``appliedFacets`` (a repeated parameter selects several values) and ``q`` as
the search text. This module sends the same requests, so a row's Link shows a
person exactly what is scraped.

Each posting's ``externalPath`` ends in ``_<job id>`` (the requisition id,
plus ``-N`` when a requisition is posted more than once). The slug before it
keeps the title from when the job was first posted, so the id, not the path,
is the stable key.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, NamedTuple, Optional, Set
from urllib.parse import urlsplit

import requests

from ..models import Posting
from .base import adapter, paged, post, query, title_id, unique

logger = logging.getLogger(__name__)

NAME = "workday"
API = "https://{host}/wday/cxs/{tenant}/{site}/jobs"
# The API refuses a larger page.
PAGE_SIZE = 20
# Requests per company per run; a scope bigger than this many pages is cut short.
MAX_PAGES = 50
# The board's search box, kept in the URL as ``?q=``.
SEARCH_PARAM = "q"
# Query parameters a board link may carry that are not facets; the board
# ignores them, while the API answers 400 to an unknown facet.
IGNORED_PARAMS = {"source", "src", "redirect", "ref", "referrer", "lang"}
# A path segment naming the page's language, e.g. ``en-US``.
LOCALE = re.compile(r"^[a-z]{2}(-[A-Za-z0-9]{2,4})?$")


class Board(NamedTuple):
    """Where a board URL's postings come from and how they are narrowed."""

    api: str
    facets: Dict[str, List[str]]
    search: str


def parse_board(url: str) -> Board:
    """Return the API endpoint, facets and search text of a Workday board URL.

    Raises:
        ValueError: If *url* is not a Workday board URL.
    """
    parts = urlsplit(url)
    host = parts.netloc.lower()
    segments = [s for s in parts.path.split("/") if s and not LOCALE.match(s)]
    if host.endswith(".myworkdayjobs.com"):
        tenant = host.split(".")[0]
        site = segments[0] if segments else ""
    elif host.endswith(".myworkdaysite.com") and len(segments) >= 3 and segments[0] == "recruiting":
        tenant, site = segments[1], segments[2]
    else:
        raise ValueError(f"Not a Workday board URL: {url}")
    if not site:
        raise ValueError(f"No career site named in {url}")

    params = query(url)
    search = " ".join(v for v in params.pop(SEARCH_PARAM, []) if v)
    facets = {
        key: [v for v in values if v]
        for key, values in params.items()
        if key not in IGNORED_PARAMS and not key.startswith("utm_") and any(values)
    }
    return Board(API.format(host=host, tenant=tenant, site=site), facets, search)


def _page(board_api: str, facets: Dict[str, List[str]], search: str, offset: int, referer: str) -> dict:
    body = {"appliedFacets": facets, "limit": PAGE_SIZE, "offset": offset, "searchText": search}
    headers = {"Accept": "application/json", "Referer": referer}
    return post(board_api, json=body, headers=headers).json()


def facet_names(facets: list) -> Set[str]:
    """Return every facet parameter in an API response's ``facets``, nested ones included."""
    names: Set[str] = set()
    for facet in facets:
        if not isinstance(facet, dict):
            continue
        if facet.get("facetParameter"):
            names.add(facet["facetParameter"])
        names |= facet_names([v for v in facet.get("values", []) if isinstance(v, dict) and "values" in v])
    return names


def job_id(job: dict) -> Optional[str]:
    """Return the job id that ends a posting's ``externalPath`` (its path if it has no id)."""
    path = (job.get("externalPath") or "").strip()
    if not path:
        return None
    tail = path.rstrip("/").rsplit("/", 1)[-1]
    return tail.rsplit("_", 1)[-1] if "_" in tail else path


def to_posting(job: dict) -> Posting:
    title = " ".join((job.get("title") or "").split())
    key = job_id(job)
    return Posting(f"{NAME}:{key}", title) if key else Posting(title_id(NAME, title), title)


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the postings a Workday board URL shows, paging 20 at a time.

    A query parameter the board does not offer as a facet (an unknown tracking
    parameter, say) makes the API answer 400; the board page ignores it, so
    here it is dropped, with a warning, and the request repeated.
    """
    board = parse_board(url)
    facets = board.facets
    try:
        first = _page(board.api, facets, board.search, 0, url)
    except requests.HTTPError as error:
        if error.response is None or error.response.status_code != 400 or not facets:
            raise
        known = facet_names(_page(board.api, {}, "", 0, url).get("facets", []))
        unknown = sorted(set(facets) - known)
        if not unknown:
            raise
        logger.warning("Ignoring %s in %s: not a facet of this board", ", ".join(unknown), url)
        facets = {k: v for k, v in facets.items() if k in known}
        first = _page(board.api, facets, board.search, 0, url)

    # Later pages of some tenants report a total of 0, so trust the first.
    total = first.get("total") or 0

    def fetch_page(page: int) -> List[Posting]:
        if page == 0:
            jobs = first.get("jobPostings", [])
        elif total and page * PAGE_SIZE >= total:
            return []
        else:
            jobs = _page(board.api, facets, board.search, page * PAGE_SIZE, url).get("jobPostings", [])
        return [to_posting(j) for j in jobs if j.get("title")]

    postings = paged(fetch_page, max_pages=MAX_PAGES)
    if total > MAX_PAGES * PAGE_SIZE:
        logger.warning("%s lists %d jobs; read only the first %d", url, total, MAX_PAGES * PAGE_SIZE)
    return unique(postings)
