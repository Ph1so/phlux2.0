"""Read Radancy TalentBrew career sites (``…/search-jobs``) from their server-rendered pages.

A row's Link is the site's search page a person opens, e.g.
``https://careers.acme.com/search-jobs`` or ``…/search-jobs?k=intern``. The
server renders the first page of results into that page's
``section#search-results``, whose attributes give the result and page counts
(``data-total-results``, ``data-total-pages``) and the search it shows
(``data-keywords``); each job is an ``a[data-job-id]`` link there.

Later pages are the same URL with ``p=<page>`` (counting from 1). Put the
search in the query (``?k=intern``), not the path (``/search-jobs/intern``):
the site drops a path keyword once ``p`` is added. If a later page reports a
different search, or a total far from the first page's (totals drift by a few
between requests), this module stops there rather than read jobs outside the
Link's scope.

A job's ``data-job-id`` is the stable key.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode, urlsplit, urlunsplit

from ..models import Posting
from .base import adapter, get, query, soup, text, unique

logger = logging.getLogger(__name__)

NAME = "talentbrew"
# Requests per company per run; a longer list is cut short.
MAX_PAGES = 50
PAGE_PARAM = "p"
# Attributes of section#search-results that must match across pages of one search.
SCOPE_ATTRS = ("data-keywords", "data-location")
TOTAL_ATTR = "data-total-results"


def page_url(url: str, page: int) -> str:
    """Return results page *page* (from 1) of a search *url*."""
    if page <= 1:
        return url
    parts = urlsplit(url)
    params = [(k, v) for k, values in query(url).items() if k != PAGE_PARAM for v in values]
    params.append((PAGE_PARAM, str(page)))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), ""))


def parse_results(html: str) -> Tuple[List[Posting], Dict[str, str], Optional[int]]:
    """Return a results page's postings, its scope attributes and its page count."""
    page = soup(html)
    section = page.select_one("#search-results")
    if section is None:
        raise ValueError("No #search-results section: not a TalentBrew search page")
    postings = []
    for link in section.select("a[data-job-id]"):
        heading = link.select_one("h2, h3, h4, [class*='job-title']")
        title = text(heading if heading is not None else link)
        if title:
            postings.append(Posting(f"{NAME}:{link['data-job-id']}", title))
    scope = {attr: section.get(attr, "") for attr in SCOPE_ATTRS + (TOTAL_ATTR,)}
    pages = section.get("data-total-pages", "")
    if not pages.isdigit():
        total, per_page = section.get("data-total-results", ""), section.get("data-records-per-page", "")
        pages = str(-(-int(total) // int(per_page))) if total.isdigit() and per_page.isdigit() and int(per_page) else ""
    return postings, scope, int(pages) if pages.isdigit() else None


def same_search(first: Dict[str, str], other: Dict[str, str]) -> bool:
    """Return True if two pages' scope attributes describe the same search."""
    if any(first.get(a) != other.get(a) for a in SCOPE_ATTRS):
        return False
    a, b = first.get(TOTAL_ATTR, ""), other.get(TOTAL_ATTR, "")
    if not (a.isdigit() and b.isdigit()):
        return a == b
    return abs(int(a) - int(b)) <= max(5, int(a) // 10)


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the jobs a TalentBrew search URL shows, across all its pages."""
    postings, scope, pages = parse_results(get(url).text)
    for page in range(2, min(pages or 1, MAX_PAGES) + 1):
        found, page_scope, _ = parse_results(get(page_url(url, page)).text)
        if not same_search(scope, page_scope):
            logger.warning("%s page %d shows another search (%s, not %s); stopped there",
                           url, page, page_scope, scope)
            break
        if not found:
            break
        postings.extend(found)
    if pages and pages > MAX_PAGES:
        logger.warning("%s has %d pages; read %d", url, pages, MAX_PAGES)
    return unique(postings)
