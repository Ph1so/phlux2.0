"""Apple job search (``jobs.apple.com/<locale>/search``).

The search page is server-rendered: ``window.__staticRouterHydrationData``
carries the page's results (``loaderData.search``: ``searchResults``, 20 a page,
and ``totalRecords``). Every filter in the link (``location``, ``team``,
``search``...) is the page's own, so the link is fetched as is, adding
``page=N`` for each page. A ``page`` already in the link is ignored.

Apple's search backend now and then answers a request with no results at all
(about one in four during testing, on the page and on its JSON API alike), so
an empty page is asked for again before it is believed.

Postings are keyed by the job's id in ``/details/<id>/...`` (one per posting
location, e.g. ``200673612-0157``).
"""
from __future__ import annotations

import json
import math
import re
import time
from typing import List, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..models import Posting
from .base import adapter, get, unique

DATA = re.compile(r"window\.__staticRouterHydrationData\s*=\s*JSON\.parse\((\".*?\")\);", re.S)
MAX_PAGES = 50
# Tries for a page that comes back empty, and the wait between them.
TRIES = 4
RETRY_SECONDS = 2


def page_url(url: str, page: int) -> str:
    """Return *url* asking for results page *page* (1-based), other filters kept."""
    parts = urlsplit(url)
    params = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "page"]
    params.append(("page", str(page)))
    return urlunsplit(parts._replace(query=urlencode(params)))


def parse(html: str) -> Tuple[List[Posting], int]:
    """Return ``(postings, total)`` from a search results page.

    Raises:
        ValueError: If the page carries no search data.
    """
    match = DATA.search(html)
    if not match:
        raise ValueError("No search data on the Apple jobs page")
    search = json.loads(json.loads(match.group(1)))["loaderData"]["search"]
    jobs = search.get("searchResults") or []
    postings = [Posting(f"apple:{j['id']}", " ".join(j["postingTitle"].split())) for j in jobs]
    return postings, search.get("totalRecords") or 0


def _page(url: str, page: int) -> Tuple[List[Posting], int]:
    for attempt in range(TRIES):
        if attempt:
            time.sleep(RETRY_SECONDS)
        postings, total = parse(get(page_url(url, page)).text)
        if postings:
            break
    return postings, total


@adapter("apple")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every posting the Apple job search in *url* finds."""
    postings, total = _page(url, 1)
    if not postings:
        return []
    pages = math.ceil(total / len(postings))
    if pages > MAX_PAGES:
        raise RuntimeError(f"Apple job search finds {total} jobs ({pages} pages); narrow {url}")
    for page in range(2, pages + 1):
        more, _ = _page(url, page)
        if not more:
            raise RuntimeError(f"Apple job search page {page} of {pages} came back empty: {url}")
        postings += more
    return unique(postings)
