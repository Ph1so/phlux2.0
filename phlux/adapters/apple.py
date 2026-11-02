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
location, e.g. ``200673612-0157``). That page is linked as
``/<locale>/details/<id>``, in the search's language; Apple redirects it to
the full path with the title's slug, which the id alone survives.
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
JOB_PAGE = "https://jobs.apple.com/{locale}/details/{id}"
DEFAULT_LOCALE = "en-us"
LOCALE = re.compile(r"^[a-z]{2}-[a-z]{2,4}$", re.I)
# Tries for a page that comes back empty, and the wait between them.
TRIES = 4
RETRY_SECONDS = 2


def page_url(url: str, page: int) -> str:
    """Return *url* asking for results page *page* (1-based), other filters kept."""
    parts = urlsplit(url)
    params = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "page"]
    params.append(("page", str(page)))
    return urlunsplit(parts._replace(query=urlencode(params)))


def job_url(url: str, job_id: str) -> str:
    """Return job *job_id*'s page in the language of the search *url*."""
    segments = [s for s in urlsplit(url).path.split("/") if s]
    locale = segments[0] if segments and LOCALE.match(segments[0]) else DEFAULT_LOCALE
    return JOB_PAGE.format(locale=locale, id=job_id)


def parse(html: str, url: str = "") -> Tuple[List[Posting], int]:
    """Return ``(postings, total)`` from a results page of the search *url*.

    Raises:
        ValueError: If the page carries no search data.
    """
    match = DATA.search(html)
    if not match:
        raise ValueError("No search data on the Apple jobs page")
    search = json.loads(json.loads(match.group(1)))["loaderData"]["search"]
    jobs = search.get("searchResults") or []
    postings = [Posting(f"apple:{j['id']}", " ".join(j["postingTitle"].split()), url=job_url(url, j["id"]))
                for j in jobs]
    return postings, search.get("totalRecords") or 0


def _page(url: str, page: int) -> Tuple[List[Posting], int]:
    for attempt in range(TRIES):
        if attempt:
            time.sleep(RETRY_SECONDS)
        postings, total = parse(get(page_url(url, page)).text, url)
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
