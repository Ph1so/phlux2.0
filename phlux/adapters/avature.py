"""Read Avature career sites (``…/careers/SearchJobs/?<n>=[…]``) from their server-rendered pages.

A row's Link is the search page a person opens, filters and all, e.g.
``https://jobs.acme.com/en_US/careers/SearchJobs/?8171=%5B10618%5D&8171_format=5683&listFilterMode=1``
(``@avature``). Avature names its filters by number (``8171=[10618]`` is one
facet set to one value); this module never interprets them, it reads the pages
the server renders for that URL. Each result is an ``article.article--result``
whose title links to the job's page, ``…/JobDetail/<slug>/<job id>`` or
``…/JobDetail?jobId=<job id>``; that id is the stable key. The page shows a
fixed number of results (some sites ignore ``jobRecordsPerPage``) and links the
next page as ``a.paginationNextLink`` (``…&jobOffset=10``), which is followed
until there is none. The site's RSS feed (``…/SearchJobs/feed/?…``) lists the
same jobs but without their locations, so it isn't used.

Where the job is comes from the result's own markup, which each site's
template words differently: ``.list-item-location`` ("Austin, United States of
America", "USA-Arizona") on most, found as any element whose class names a
location. A site whose template has no such class names its location element
with the row's argument, a CSS selector inside each result:
``@avature:.article__header__content__text > span`` ("United States - NY New
York"). Locations are written "Austin" (a US town with no state given), "New
York, NY", "Arizona" or "Hsinchu, Taiwan" (see :func:`avature_place`).
"""
from __future__ import annotations

import logging
import re
import time
from typing import List, Optional, Tuple
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

from ..models import Posting
from .base import (COUNTRIES, US_STATES, adapter, bare_url, format_place, get, is_us, place, soup, text,
                   tidy_place, us_state)

logger = logging.getLogger(__name__)

NAME = "avature"
# Requests per company per run; a longer list is cut short.
MAX_PAGES = 50
# Seconds between page requests.
DELAY = 0.5
RESULT = "article.article--result"
TITLE_LINK = "a[href*='JobDetail']"
NEXT = "a.paginationNextLink[href]"
LOCATION = "[class*='location' i]"
_COUNTRY_NAMES = {name.casefold() for name in COUNTRIES.values()}
# "USA-Arizona", "United States - NY New York": a country, a dash, then the place within it.
_COUNTRY_FIRST = re.compile(r"^(?P<country>[^,]+?)\s*-\s*(?P<rest>[^,]+)$")
# "NY New York": a state code before the town.
_STATE_FIRST = re.compile(r"^(?P<state>[A-Z]{2})\s+(?P<city>.+)$")
# "1-10 of 22 results", "10 results".
_TOTAL = re.compile(r"(?:of\s+)?([\d,]+)\s+results?\b", re.IGNORECASE)


def _is_country(name: str) -> bool:
    return is_us(name) or name.casefold() in _COUNTRY_NAMES


def avature_place(value: Optional[str]) -> str:
    """Return an Avature location as base.py writes places.

    "Austin, United States of America" → "Austin", "Rosslyn, Virginia, United
    States" → "Rosslyn, VA", "USA-Arizona" → "Arizona", "United States - NY New
    York" → "New York, NY", "Taiwan-Hsinchu" → "Hsinchu, Taiwan". Anything else
    keeps the site's wording ("Multiple Locations").
    """
    value = " ".join((value or "").split())
    dashed = _COUNTRY_FIRST.match(value)
    if dashed and _is_country(dashed.group("country")):
        country, rest = dashed.group("country"), dashed.group("rest")
        state_first = _STATE_FIRST.match(rest)
        if is_us(country) and state_first and us_state(state_first.group("state")):
            return format_place(state_first.group("city"), state_first.group("state"), "United States")
        if is_us(country) and us_state(rest):
            return US_STATES[us_state(rest)]
        return format_place(rest, "", country)
    tidied = tidy_place(value)
    parts = [p.strip() for p in tidied.split(",")]
    # A US town given without its state: "Austin, United States of America" is just "Austin".
    if len(parts) >= 2 and is_us(parts[-1]):
        return ", ".join(parts[:-1])
    return tidied


def job_id(href: str) -> str:
    """Return the job id in a ``JobDetail`` link: its ``jobId`` parameter, else its last path segment."""
    parts = urlsplit(href)
    by_param = parse_qs(parts.query).get("jobId")
    if by_param and by_param[0].strip():
        return by_param[0].strip()
    segments = [s for s in parts.path.split("/") if s]
    return segments[-1] if segments and segments[-1] != "JobDetail" else ""


def job_url(href: str, base_url: str, job: str) -> str:
    """Return a job's page without tracking parameters (``…/JobDetail?jobId=<id>`` keeps its id)."""
    absolute = urljoin(base_url, href)
    parts = urlsplit(absolute)
    if parse_qs(parts.query).get("jobId"):
        return urlunsplit((parts.scheme, parts.netloc, parts.path, f"jobId={job}", ""))
    return bare_url(absolute)


def _location(article, selector: str) -> str:
    nodes = article.select(selector or LOCATION)
    names = [avature_place(text(n)) for n in nodes]
    names = [n for n in names if n]
    return place(names[0], names[1:]) if names else ""


def parse_results(html: str, base_url: str, location_selector: str = ""
                  ) -> Tuple[List[Posting], Optional[str], Optional[int]]:
    """Return a results page's postings, its next page's URL (or None) and its result count (or None)."""
    page = soup(html)
    postings = []
    for article in page.select(RESULT):
        link = article.select_one(TITLE_LINK)
        if link is None:
            continue
        title, key = text(link), job_id(link["href"])
        if not title or not key:
            continue
        postings.append(Posting(f"{NAME}:{key}", title, _location(article, location_selector),
                                job_url(link["href"], base_url, key)))
    nxt = page.select_one(NEXT)
    total = None
    counted = page.select_one("[data-total]")
    if counted is not None and str(counted.get("data-total", "")).isdigit():
        total = int(counted["data-total"])
    else:
        for legend in page.select(".list-controls__text__legend, .list-controls__text"):
            found = _TOTAL.search(text(legend))
            if found:
                total = int(found.group(1).replace(",", ""))
                break
    return postings, urljoin(base_url, nxt["href"]) if nxt is not None else None, total


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the jobs an Avature search URL shows, following its next-page links.

    *arg* is an optional CSS selector for the location element inside each result.
    """
    postings: List[Posting] = []
    seen: set = set()
    page_url: Optional[str] = url
    total = None
    for page in range(MAX_PAGES):
        if page_url is None:
            break
        if page:
            time.sleep(DELAY)
        found, page_url, count = parse_results(get(page_url).text, url, arg)
        total = total if total is not None else count
        fresh = [p for p in found if p.id not in seen]
        if not fresh:
            break
        seen.update(p.id for p in fresh)
        postings.extend(fresh)
    else:
        if page_url is not None:
            logger.warning("%s has more than %d pages; read %d", url, MAX_PAGES, MAX_PAGES)
    if not postings:
        logger.warning("No Avature results at %s", url)
    elif total is not None and total > len(postings):
        logger.warning("%s lists %d jobs; read %d", url, total, len(postings))
    return postings
