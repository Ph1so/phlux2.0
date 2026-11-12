"""Read Phenom career sites (``…/<country>/<lang>/search-results``) without a browser.

A row's Link is the site's search page a person opens, e.g.
``https://careers.adobe.com/us/en/search-results?qkexperienceLevel=University%20Intern``
or ``https://careers.cisco.com/global/en/search-results?keywords=intern&qcountry=United%20States%20of%20America``.
The server renders that page with two scripts this module reads:

* ``phApp = phApp || {…}``: the site's ``widgetApiEndpoint`` (``https://<host>/widgets``),
  ``locale``, ``country``, ``pageId``, ``siteType`` and ``baseUrl``;
* ``phApp.ddo = {…}``, whose ``eagerLoadRefineSearch`` is the search the URL asks
  for: its ``keywords`` (``?keywords=``), the facets the server read from the query
  (``ui_selections``; ``q<field>=`` or ``qk<field>=``, for the fields the site lets a
  URL set, so check that the page shows the narrowed count), ``totalHits``, and the
  first 10 jobs.

When those 10 jobs are all of them, they are the result. Otherwise the same search
(keywords, facets, location) is sent to the site's ``POST /widgets`` with
``ddoKey: refineSearch``, which answers up to 500 jobs per request. Relevance order
is not stable from one request to the next (a job can come up on two pages and
another on none), so a search that fits one request is read in one; a bigger one is
read page by page with a warning that it may differ between runs; narrow its Link.
A landing page's own hidden filter (e.g. ``…/splunk/search-page``) is not part of
that search: if the API reports a total far from the page's, this module raises
rather than read jobs outside the Link's scope.

A job's ``jobId`` (its requisition id) is the stable key; its page is
``<baseUrl>job/<jobId>/<title slug>`` (the slug is decoration the site ignores).
Its ``location`` ("San Jose, California, United States of America") and
``multi_location`` give where it is ("San Jose, CA +3").
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Dict, List, NamedTuple, Optional

from ..models import Posting
from .base import adapter, format_place, get, place, post, tidy_place, title_id, unique

logger = logging.getLogger(__name__)

NAME = "phenom"
# The most jobs the widgets API returns per request.
PAGE_SIZE = 500
# Requests per company per run beyond the page itself.
MAX_PAGES = 10
# Seconds between API requests when a search spans several.
DELAY = 1.0
APP = re.compile(r"phApp\s*=\s*phApp\s*\|\|\s*(\{.*?\})\s*;", re.S)
DDO = re.compile(r"phApp\.ddo\s*=\s*(\{.*?\})\s*;\s*phApp\.", re.S)
SESSION = re.compile(r"phApp\.sessionParams\s*=\s*(\{.*?\})\s*;", re.S)


class Search(NamedTuple):
    """What a search page shows and how to ask the widgets API for the same."""

    api: str
    body: dict
    total: int
    # The jobs rendered into the page (the first 10).
    jobs: List[dict]
    # Where job pages live, e.g. ``https://careers.adobe.com/us/en/``.
    base_url: str
    landing: bool


def _json(pattern: re.Pattern, html: str) -> Optional[dict]:
    match = pattern.search(html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except ValueError:
        return None


def parse_page(html: str) -> Search:
    """Return the search a Phenom search page shows.

    Raises:
        ValueError: If *html* is not a Phenom page with server-rendered results.
    """
    app, ddo = _json(APP, html), _json(DDO, html)
    if not app or not ddo or not app.get("widgetApiEndpoint"):
        raise ValueError("No phApp data: not a Phenom career site page")
    results = ddo.get("eagerLoadRefineSearch")
    if not isinstance(results, dict) or not isinstance(results.get("data"), dict):
        raise ValueError("No eagerLoadRefineSearch in the page: not a Phenom search page")
    data = results["data"]
    session = _json(SESSION, html) or {}
    body = {
        "lang": app.get("locale", ""),
        "deviceType": app.get("deviceType") or "desktop",
        "country": app.get("country", ""),
        "pageName": "search-results",
        "ddoKey": "refineSearch",
        "sortBy": "",
        "subsearch": data.get("subsearch") or "",
        "from": 0,
        "jobs": True,
        "counts": False,
        "all_fields": [],
        "size": PAGE_SIZE,
        "clearAll": False,
        "jdsource": "facets",
        "isSliderEnable": False,
        "pageId": app.get("pageId", ""),
        "siteType": app.get("siteType") or "external",
        "keywords": data.get("keywords") or "",
        "global": True,
        "selected_fields": data.get("ui_selections") or {},
        "locationData": data.get("locationData") or {},
    }
    return Search(
        app["widgetApiEndpoint"],
        body,
        int(results.get("totalHits") or 0),
        [j for j in data.get("jobs") or [] if isinstance(j, dict)],
        app.get("baseUrl") or "",
        session.get("pageType") == "landingPage",
    )


def slug(title: str) -> str:
    """Return *title* as the site writes it in a job's link ("2027 Intern - SWE" → "2027-Intern-SWE")."""
    return re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-")


def _where(text: str) -> str:
    """Return a Phenom "City, State, Country" text as a person writes it.

    The state can hold a comma itself ("London, London, City of, United Kingdom").
    """
    parts = [p.strip() for p in (text or "").split(",") if p.strip()]
    if len(parts) >= 3:
        return format_place(parts[0], ", ".join(parts[1:-1]), parts[-1])
    return tidy_place(text)


def location(job: dict) -> str:
    """Return where *job* is: its main location, plus a count of the others."""
    primary = _where(job.get("location") or "")
    if not primary and (job.get("city") or job.get("country")):
        primary = format_place(job.get("city"), job.get("state"), job.get("country"))
    others = job.get("multi_location") or []
    return place(primary, [_where(o) for o in others if isinstance(o, str)])


def to_posting(job: dict, base_url: str = "") -> Posting:
    """Return *job* as a posting; *base_url* (the site's ``baseUrl``) makes its link."""
    title = " ".join(str(job.get("title") or "").split())
    key = str(job.get("jobId") or job.get("reqId") or job.get("jobSeqNo") or "").strip()
    url = f"{base_url}job/{key}/{slug(title)}".rstrip("/") if base_url and key else ""
    return Posting(f"{NAME}:{key}" if key else title_id(NAME, title), title, location(job), url)


def close_enough(page_total: int, api_total: int) -> bool:
    """Return True if two totals describe the same search; they drift by a few between requests."""
    return abs(page_total - api_total) <= max(5, page_total // 10)


def _ask(search: Search, offset: int, referer: str) -> dict:
    body = {**search.body, "from": offset}
    headers = {"Accept": "application/json", "Content-Type": "application/json", "Referer": referer}
    answer = post(search.api, json=body, headers=headers).json()
    results = answer.get("refineSearch") if isinstance(answer, dict) else None
    if not isinstance(results, dict) or not isinstance(results.get("data"), dict):
        raise ValueError(f"Unexpected answer from {search.api}")
    return results


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every job a Phenom search URL shows."""
    search = parse_page(get(url).text)
    if len(search.jobs) >= search.total:
        return unique(to_posting(j, search.base_url) for j in search.jobs if j.get("title"))

    first = _ask(search, 0, url)
    total = int(first.get("totalHits") or 0)
    if not close_enough(search.total, total):
        hint = " (a landing page's own filter is not sent to the API)" if search.landing else ""
        raise ValueError(f"{search.api} reports {total} jobs for the search on {url}, "
                         f"which shows {search.total}{hint}")
    jobs = list(first["data"].get("jobs") or [])
    if total > PAGE_SIZE:
        logger.warning("%s shows %d jobs, more than one request of %d; they may come out "
                       "different on each run, so narrow the link", url, total, PAGE_SIZE)
    for page in range(1, MAX_PAGES):
        if page * PAGE_SIZE >= total:
            break
        time.sleep(DELAY)
        found = _ask(search, page * PAGE_SIZE, url)["data"].get("jobs") or []
        if not found:
            break
        jobs.extend(found)
    else:
        logger.warning("%s shows %d jobs; read %d", url, total, MAX_PAGES * PAGE_SIZE)
    return unique(to_posting(j, search.base_url) for j in jobs if isinstance(j, dict) and j.get("title"))
