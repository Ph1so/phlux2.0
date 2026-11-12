"""Read SAP SuccessFactors career sites (Career Site Builder, ``…/search/?q=…``) from their pages.

A row's Link is the site's search page a person opens, e.g.
``https://jobs.kuka.com/search/?q=&locationsearch=United+States`` or
``https://jobs.acme.com/acme/search/?q=intern``. The server renders the
search's first page of results into that page, and later pages are the same URL
with ``startrow=<offset>`` (25 a page). Sites use one of two templates:

* a table: one ``tr.data-row`` per job, its place in ``.jobLocation``
  ("San Jose, CA, US", with a ``<small>+1 more…</small>`` for a job in several);
* tiles: one ``li.job-tile`` per job, its place in the ``.section-field.location``
  field (each tile repeats its fields for desktop, tablet and phone).

Either way the job's link is ``a.jobTitle-link``, ``/job/<slug>/<id>/`` (some
sites put a brand first: ``/Teradyne/job/…``), and that number is the stable
key. A label above the list gives the search's total ("Results 1 – 25 of 299",
"Showing 1 to 25 of 48 Jobs").

A search that finds nothing says so in ``#noresults``, and some sites (KUKA)
then list their latest jobs below it; those are not the search's, so such a
page counts as empty. A page past the end is one, so pages are read up to the
total and no further. A page whose total differs (a job posted or closed during
the walk) is skipped. While the walks have found fewer jobs than the total (as
when the sort order shifts between pages), another is made, up to
:data:`WALKS` in all, and the jobs of every walk are kept, so a job never drops
out of one run only to come back in the next.

Places are "City, ST, CC" or "City, CC" with country codes; they are written
"North Reading, MA" or "Augsburg, Germany", and "San Jose, CA +1" for a job
with more places.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode, urlsplit, urlunsplit

from ..models import Posting
from .base import adapter, bare_url, format_place, get, query, soup, text, tidy_place

logger = logging.getLogger(__name__)

NAME = "successfactors"
PAGE_PARAM = "startrow"
# Seconds between pages.
DELAY = 1.0
# Requests per walk (1000 jobs); a bigger search is cut short.
MAX_PAGES = 40
# Walks through the pages before settling for fewer jobs than the total.
WALKS = 3
ROWS = "tr.data-row, li.job-tile"
TITLE_LINK = "a.jobTitle-link"
# Where a row names its place: the table's column, else a tile's location field.
LOCATIONS = ("td.colLocation .jobLocation", ".jobLocation", ".section-field.location [id$='-value']")
TOTAL_LABELS = ".paginationLabel, #tile-search-results-label"
# Shown above a search that found nothing (and the site's latest jobs instead).
NO_RESULTS = "#noresults"
_JOB_ID = re.compile(r"/job/[^/]+/(\d+)/?$")
_MORE = re.compile(r"\+\s*(\d+)\s*more", re.IGNORECASE)
_NUMBER = re.compile(r"\d[\d,.]*")
_CODE = re.compile(r"[A-Z]{2,3}")


def page_url(url: str, start: int) -> str:
    """Return the results page of search *url* that starts at row *start* (from 0)."""
    params = [(k, v) for k, values in query(url).items() if k != PAGE_PARAM for v in values]
    if start:
        params.append((PAGE_PARAM, str(start)))
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), ""))


def format_location(raw: str) -> str:
    """Return a site's "City, ST, CC" place as a person writes it ("North Reading, MA").

    *raw* may end in "+N more…" for a job in several places; that becomes " +N".
    """
    more = _MORE.search(raw)
    raw = _MORE.sub("", raw).replace("…", "").strip().rstrip(",")
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) in (2, 3) and _CODE.fullmatch(parts[-1]):
        where = format_place(parts[0], parts[1] if len(parts) == 3 else "", parts[-1])
    else:
        where = tidy_place(raw)
    return f"{where} +{more.group(1)}" if where and more else where


def _location(row) -> str:
    for selector in LOCATIONS:
        node = row.select_one(selector)
        if node is not None and text(node):
            return format_location(text(node))
    return ""


def parse_results(html: str, base_url: str) -> Tuple[List[Posting], Optional[int]]:
    """Return a results page's jobs and the search's total (None if the page gives none).

    Job links are made absolute against *base_url*, the page's URL. A page that
    says the search found nothing has no jobs and a total of 0.

    Raises:
        ValueError: The page has no job list or total label: not a Career Site Builder search.
    """
    page = soup(html)
    if page.select_one(NO_RESULTS) is not None:
        return [], 0
    label = page.select_one(TOTAL_LABELS)
    numbers = _NUMBER.findall(text(label)) if label is not None else []
    total = int(re.sub(r"\D", "", numbers[-1])) if numbers else None
    rows = page.select(ROWS) or [link.parent for link in page.select(TITLE_LINK)]
    if total is None and not rows:
        raise ValueError("No job list or result count: not a SuccessFactors search page")
    postings: Dict[str, Posting] = {}
    for row in rows:
        link = row.select_one(TITLE_LINK)
        if link is None or not link.get("href"):
            continue
        url = bare_url(link["href"], base_url)
        found = _JOB_ID.search(urlsplit(url).path)
        title = text(link)
        if not (found and title) or found.group(1) in postings:
            continue
        postings[found.group(1)] = Posting(f"{NAME}:{found.group(1)}", title, _location(row), url)
    return list(postings.values()), total


def walk(url: str) -> Tuple[Dict[str, Posting], Optional[int]]:
    """Read every page of search *url* once.

    Returns:
        Its jobs by id, and how many a walk should find: the search's total, or
        as many as :data:`MAX_PAGES` pages hold; None if the site gives no total.
    """
    found, total = parse_results(get(page_url(url, 0)).text, url)
    jobs = {p.id: p for p in found}
    step = len(found)
    if total is None:
        logger.warning("%s gives no result count; read its first page only", url)
        return jobs, None
    pages = -(-total // step) if step else 0
    for page in range(1, min(pages, MAX_PAGES)):
        time.sleep(DELAY)
        more, page_total = parse_results(get(page_url(url, page * step)).text, url)
        if page_total != total:
            logger.info("%s page %d counts %s jobs, not %s; skipped", url, page + 1, page_total, total)
            continue
        for p in more:
            jobs.setdefault(p.id, p)
    if pages > MAX_PAGES:
        logger.warning("%s has %d pages; read %d", url, pages, MAX_PAGES)
    return jobs, min(total, MAX_PAGES * step)


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the jobs a Career Site Builder search URL shows, across all its pages."""
    jobs: Dict[str, Posting] = {}
    for attempt in range(WALKS):
        if attempt:
            time.sleep(DELAY)
        found, expected = walk(url)
        for job_id, posting in found.items():
            jobs.setdefault(job_id, posting)
        if expected is None or len(jobs) >= expected:
            break
        logger.info("%s walks read %d of %d jobs; reading again", url, len(jobs), expected)
    return list(jobs.values())
