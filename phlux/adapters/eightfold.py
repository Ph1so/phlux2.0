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
A position's ``id`` is the stable key.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlsplit

import requests

from ..models import Posting
from .base import adapter, first, get, paged, query, soup

logger = logging.getLogger(__name__)

NAME = "eightfold"
PAGE_SIZE = 10
# Seconds between API pages; quicker calls draw 429s.
DELAY = 2.0
# Requests per company per run (500 positions); a bigger scope is cut short.
MAX_PAGES = 50
PCSX_API = "/api/pcsx/search"
LEGACY_API = "/api/apply/v2/jobs"
# Parameters the careers page reads itself rather than as filters.
PAGE_PARAMS = {"domain", "query", "location", "sort_by", "start", "pid", "hl"}
# Parameters that only steer the page (paging, which position is open, tracking).
LEGACY_DROPPED = {"start", "num", "pid", "triggerGoButton"}
FILTER_PREFIX = "filter_"
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


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the positions an Eightfold careers search URL shows, across all its pages."""
    session = requests.Session()
    html = get(url, session=session).text
    api, params, pcsx = api_request(url, html)
    total: Dict[str, int] = {}

    def fetch_page(page: int) -> List[Posting]:
        start = page * PAGE_SIZE
        if "count" in total and start >= total["count"]:
            return []
        body = get(api, session=session, params=params + [("start", str(start))],
                   headers={"Accept": "application/json"}).json()
        data = body["data"] if pcsx else body
        total["count"] = int(data.get("count") or 0)
        return [
            Posting(f"{NAME}:{p['id']}", " ".join(str(p["name"]).split()))
            for p in data.get("positions") or []
        ]

    postings = paged(fetch_page, delay=DELAY, max_pages=MAX_PAGES)
    if total.get("count", 0) > MAX_PAGES * PAGE_SIZE:
        logger.warning("%s has %d positions; read only the first %d", url, total["count"], len(postings))
    return postings
