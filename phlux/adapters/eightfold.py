"""Read Eightfold career sites (``…/careers?query=…``) from the JSON API behind them.

A row's Link is the careers search page a person opens, e.g.
``https://careers.qualcomm.com/careers?location=United%20States&seniority=Intern``.
Eightfold serves two generations of that page, and a tenant answers on only one:

* PCSX, the current one, whose page embeds its config in ``<code id="pcsx-data">``.
  It asks ``GET /api/pcsx/search?domain=…&query=…&location=…&start=N[&sort_by=…]``
  and sends each filter as ``filter_<snake_case key>=<value>``. The URL may name a
  filter by its key or its display name (``configs.pcsxConfig.searchOptionsMap``),
  and give a value as an option's label, which that config maps to the value the
  API wants: Deere's ``seniority=Intern`` is sent as ``filter_seniority=0``.
* The older page (``<code id="smartApplyData">``), which asks
  ``GET /api/apply/v2/jobs`` with the page URL's own parameters.

This module loads the Link first, as the browser does: the page says which
generation it is and the tenant's ``domain`` (the API refuses a call without
one), and the cookies it sets keep the API from answering 429 at once.

Both APIs return 10 positions a page whatever ``num`` asks, and answer 429 to
quick calls, so pages are :data:`DELAY` seconds apart. Keep a row's search
narrow (a ``query`` or filters): :data:`MAX_PAGES` pages is the most read.

The order isn't always stable between calls: from GitHub Actions, Qualcomm's
second page sometimes repeated positions from its first, so a walk came back
with 12 of 18. The positions skipped looked closed, the next run reopened
them, and every run committed (each bot commit starts another run). So a walk
reads every page up to the API's ``count``, even a page of positions already
seen (where ``base.paged`` would stop); one that ends short of the count is
repeated, up to :data:`WALKS` in all, and the positions of every walk are kept.

A position's ``id`` is the stable key. Its page is PCSX's ``positionUrl``
(relative, ``/careers/job/<id>``) on the careers site, or the older API's
absolute ``canonicalPositionUrl``. Its ``locations`` ("San Diego, California,
United States of America", …; the older API also names one ``location``) are
written "San Diego, CA +2".
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlsplit

import requests

from ..models import Posting
from .base import adapter, first, get, is_us, place, query, soup, tidy_place

logger = logging.getLogger(__name__)

NAME = "eightfold"
PAGE_SIZE = 10
# Seconds between API pages; quicker calls draw 429s.
DELAY = 2.0
# Requests per company per run (500 positions); a bigger scope is cut short.
MAX_PAGES = 50
# Walks through the pages before settling for fewer positions than the count.
WALKS = 3
PCSX_API = "/api/pcsx/search"
LEGACY_API = "/api/apply/v2/jobs"
# Parameters the careers page reads itself rather than as filters.
PAGE_PARAMS = {"domain", "query", "location", "sort_by", "start", "pid", "hl"}
# Parameters that only steer the page (paging, which position is open, tracking).
LEGACY_DROPPED = {"start", "num", "pid", "triggerGoButton"}
FILTER_PREFIX = "filter_"
# A position's page on the careers site, for an API answer that names none.
POSITION_PATH = "/careers/job/{id}"
# lodash's word split, which the page uses to snake_case filter keys.
_WORDS = re.compile(r"[A-Z]{2,}(?=[A-Z][a-z]+[0-9]*|\b)|[A-Z]?[a-z]+[0-9]*|[A-Z]|[0-9]+")


def snake_case(key: str) -> str:
    """Return *key* as lodash's ``snakeCase`` would, e.g. ``jobType`` → ``job_type``."""
    return "_".join(w.lower() for w in _WORDS.findall(key))


def page_data(html: str) -> Tuple[Optional[dict], Optional[dict]]:
    """Return ``(pcsx_data, legacy_data)`` embedded in a careers page; one is None."""
    page = soup(html)
    for node_id, pcsx in (("pcsx-data", True), ("smartApplyData", False)):
        node = page.find("code", id=node_id)
        if node is not None:
            data = json.loads(node.get_text())
            return (data, None) if pcsx else (None, data)
    return None, None


def pcsx_filters(params: Dict[str, List[str]], options: dict) -> List[Tuple[str, str]]:
    """Return the API's ``filter_*`` parameters for a careers URL's *params*.

    *options* is the page's ``searchOptionsMap``. Values may be comma-separated.
    """
    keys: Dict[str, str] = {}
    labels: Dict[str, Dict[str, str]] = {}
    for key, option in options.items():
        keys[key] = key
        name = (option or {}).get("displayName")
        if name:
            keys[name] = key
        for value, label in (((option or {}).get("options") or {}).get("labelMap") or {}).items():
            labels.setdefault(key, {})[label] = value

    filters: List[Tuple[str, str]] = []
    for name, values in params.items():
        if name.startswith(FILTER_PREFIX):
            key = name[len(FILTER_PREFIX):]
        elif name in PAGE_PARAMS or name not in keys:
            continue
        else:
            key = keys[name]
        for value in values:
            for part in value.split(","):
                if part:
                    filters.append((FILTER_PREFIX + snake_case(key), labels.get(key, {}).get(part, part)))
    return filters


def api_request(url: str, html: str) -> Tuple[str, List[Tuple[str, str]], bool]:
    """Return ``(api_url, params_without_start, is_pcsx)`` for a careers *url* and its page.

    Raises:
        ValueError: If the page is not an Eightfold careers page or names no domain.
    """
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    params = query(url)
    pcsx, legacy = page_data(html)
    if pcsx is None and legacy is None:
        raise ValueError(f"Not an Eightfold careers page: {url}")
    domain = first(params, "domain") or (pcsx or legacy).get("domain", "")
    if not domain:
        raise ValueError(f"No Eightfold domain for {url}")

    if pcsx is not None:
        options = ((pcsx.get("configs") or {}).get("pcsxConfig") or {}).get("searchOptionsMap") or {}
        api_params = [
            ("domain", domain),
            ("query", first(params, "query")),
            ("location", first(params, "location")),
        ]
        for key in ("sort_by", "hl"):
            if first(params, key):
                api_params.append((key, first(params, key)))
        api_params += pcsx_filters(params, options)
        return origin + PCSX_API, api_params, True

    api_params = [("domain", domain)] + [
        (key, value)
        for key, values in params.items()
        if key not in LEGACY_DROPPED and key != "domain"
        for value in values
    ]
    return origin + LEGACY_API, api_params, False


def position_url(origin: str, position: dict) -> str:
    """Return a position's page on the careers site at *origin*."""
    path = position.get("canonicalPositionUrl") or position.get("positionUrl")
    return urljoin(origin + "/", path or POSITION_PATH.format(id=position["id"]))


def _tidy(name: str) -> str:
    return "United States" if is_us(name) else tidy_place(name)


def location(position: dict) -> str:
    """Return a position's location: its first (or named) one and how many more it lists.

    Some tenants fill ``locations`` with their ATS's raw text ("United States |
    US-MN-Maple Grove"); their ``standardizedLocations`` ("Maple Grove, MN, US")
    are used instead.
    """
    names = position.get("locations") or []
    if isinstance(names, str):
        names = [names]
    standard = position.get("standardizedLocations") or []
    if isinstance(standard, str):
        standard = [standard]
    if not names or (standard and any("|" in n for n in names if isinstance(n, str))):
        names = standard
    main = position.get("location")
    if isinstance(main, str) and "|" in main and standard:
        main = None
    return place(_tidy(main) if isinstance(main, str) else None,
                 [_tidy(n) for n in names if isinstance(n, str)])


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the positions an Eightfold careers search URL shows, across all its pages."""
    session = requests.Session()
    html = get(url, session=session).text
    api, params, pcsx = api_request(url, html)
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    def fetch_page(start: int) -> Tuple[int, List[Posting]]:
        body = get(api, session=session, params=params + [("start", str(start))],
                   headers={"Accept": "application/json"}).json()
        data = body["data"] if pcsx else body
        return int(data.get("count") or 0), [
            Posting(f"{NAME}:{p['id']}", " ".join(str(p["name"]).split()), location(p), position_url(origin, p))
            for p in data.get("positions") or []
        ]

    postings: List[Posting] = []
    seen: set = set()
    count: Optional[int] = None
    calls = 0
    for _ in range(WALKS):
        # Every page up to the count, even one of positions already seen.
        start = 0
        while count is None or start < min(count, MAX_PAGES * PAGE_SIZE):
            if calls:
                time.sleep(DELAY)
            calls += 1
            count, page = fetch_page(start)
            if not page:
                break
            for posting in page:
                if posting.id not in seen:
                    seen.add(posting.id)
                    postings.append(posting)
            start += PAGE_SIZE
        if count > MAX_PAGES * PAGE_SIZE:
            logger.warning("%s has %d positions; read only the first %d", url, count, len(postings))
            break
        if len(postings) >= count:
            break
    else:
        logger.warning("%s: read %d of %d positions in %d walks", url, len(postings), count, WALKS)
    return postings
