"""Read Taleo Business Edition career sites (CWS v2) from their server-rendered pages.

A row's Link is the site's results page a person opens,
``https://<pod>.tbe.taleo.net/<pod>NN/ats/careers/v2/searchResults?org=<ORG>&cws=<N>[&…]``.
Taleo Business Edition has no public JSON API, but that page lists its jobs in
the HTML (``h4.oracletaleocwsv2-head-title a``) and says how many matched
("Positions Matched"). Longer lists load more rows as the visitor scrolls,
from the link in ``a.jscroll-next``; this module follows those links.

A job's ``rid`` (its requisition id, in its ``viewRequisition`` link) is the
stable key.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple
from urllib.parse import parse_qs, urljoin, urlsplit

from ..models import Posting
from .base import adapter, get, soup, text, unique

logger = logging.getLogger(__name__)

NAME = "taleo"
# Requests per company per run; a longer list is cut short.
MAX_PAGES = 50


def parse_results(html: str, base_url: str) -> Tuple[List[Posting], Optional[str], Optional[int]]:
    """Return a results page's postings, its next-rows link, and its matched count."""
    page = soup(html)
    postings = []
    for link in page.select("h4.oracletaleocwsv2-head-title a[href]"):
        href = urljoin(base_url, link["href"])
        rid = parse_qs(urlsplit(href).query).get("rid", [""])[0]
        title = text(link)
        if title:
            postings.append(Posting(f"{NAME}:{rid or href}", title))
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
    for _ in range(MAX_PAGES):
        if not next_url or next_url in seen_urls:
            break
        seen_urls.add(next_url)
        found, following, count = parse_results(get(next_url).text, next_url)
        matched = count if matched is None else matched
        if not found:
            break
        postings.extend(found)
        next_url = following
    postings = unique(postings)
    if matched is not None and matched > len(postings):
        logger.warning("%s matched %d jobs; read %d", url, matched, len(postings))
    return postings
