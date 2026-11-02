"""Read Taleo Business Edition career sites (CWS v2) from their server-rendered pages.

A row's Link is the site's results page a person opens,
``https://<pod>.tbe.taleo.net/<pod>NN/ats/careers/v2/searchResults?org=<ORG>&cws=<N>[&…]``.
Taleo Business Edition has no public JSON API, but that page lists its jobs in
the HTML (``h4.oracletaleocwsv2-head-title a``) and says how many matched
("Positions Matched"). Longer lists load more rows as the visitor scrolls,
from the link in ``a.jscroll-next``; this module follows those links.

A job's ``rid`` (its requisition id, in its ``viewRequisition`` link) is the
stable key. That link, kept to the parameters that pick the job (``org``,
``cws``, ``rid``), is the job's page.

Under each title the page lists the job's other columns (function, location,
requisition number…) without labels; which one is the location is read from
the page's "Sort by" options, which name the columns in order (``sortColumn=N``).
Rows loaded on scroll come without those options, so the first page's order is used.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

from ..models import Posting
from .base import adapter, get, soup, text, tidy_place, unique

logger = logging.getLogger(__name__)

NAME = "taleo"
# Requests per company per run; a longer list is cut short.
MAX_PAGES = 50
# The parameters of a viewRequisition link that pick the job.
JOB_PARAMS = ("org", "cws", "rid")
SORT_COLUMN = re.compile(r"sortColumn=(\d+)")
LOCATION_COLUMNS = ("location", "locations", "job location")


def columns(page) -> Dict[str, int]:
    """Return the results' column numbers by name (lowercased), from a page's "Sort by" options."""
    found: Dict[str, int] = {}
    for option in page.select("select option[value*='sortColumn=']"):
        match = SORT_COLUMN.search(option["value"])
        if match:
            found.setdefault(text(option).casefold(), int(match.group(1)))
    return found


def location_column(page) -> Optional[int]:
    """Return which of a result's lines under its title holds its location (from 0), if a page says."""
    named = columns(page)
    location = next((named[n] for n in LOCATION_COLUMNS if n in named), None)
    if location is None:
        return None
    title = next((c for n, c in named.items() if "title" in n), 0)
    return location - 1 if location > title else location


def _location(link, column: Optional[int]) -> str:
    info = link.find_parent(class_="oracletaleocwsv2-accordion-head-info")
    if column is None or info is None:
        return ""
    lines = info.find_all("div", recursive=False)
    return tidy_place(text(lines[column])) if column < len(lines) else ""


def job_page(href: str) -> str:
    """Return a job's ``viewRequisition`` link with only :data:`JOB_PARAMS` (as is without a ``rid``)."""
    parts = urlsplit(href)
    params = parse_qs(parts.query)
    if not params.get("rid"):
        return href
    kept = [(key, params[key][0]) for key in JOB_PARAMS if params.get(key)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), ""))


def parse_results(html: str, base_url: str, column: Optional[int] = None
                  ) -> Tuple[List[Posting], Optional[str], Optional[int]]:
    """Return a results page's postings, its next-rows link, and its matched count.

    *column* is :func:`location_column` of the first page, for rows that come without it.
    """
    page = soup(html)
    own = location_column(page)
    column = own if own is not None else column
    postings = []
    for link in page.select("h4.oracletaleocwsv2-head-title a[href]"):
        href = urljoin(base_url, link["href"])
        rid = parse_qs(urlsplit(href).query).get("rid", [""])[0]
        title = text(link)
        if title:
            postings.append(Posting(f"{NAME}:{rid or href}", title, _location(link, column), job_page(href)))
    nxt = page.select("a.jscroll-next[href]")
    next_url = urljoin(base_url, nxt[-1]["href"]) if nxt else None
    count_node = page.select_one(".oracletaleocwsv2-totals-callout .oracletaleocwsv2-panel-number")
    count = text(count_node) if count_node is not None else ""
    return postings, next_url, int(count) if count.isdigit() else None


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the jobs a Taleo Business Edition results URL lists, following its scroll links."""
    postings: List[Posting] = []
    matched: Optional[int] = None
    next_url: Optional[str] = url
    seen_urls = set()
    column: Optional[int] = None
    for _ in range(MAX_PAGES):
        if not next_url or next_url in seen_urls:
            break
        seen_urls.add(next_url)
        html = get(next_url).text
        if column is None:
            column = location_column(soup(html))
        found, following, count = parse_results(html, next_url, column)
        matched = count if matched is None else matched
        if not found:
            break
        postings.extend(found)
        next_url = following
    postings = unique(postings)
    if matched is not None and matched > len(postings):
        logger.warning("%s matched %d jobs; read %d", url, matched, len(postings))
    return postings
