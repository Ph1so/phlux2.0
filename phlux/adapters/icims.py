"""Read classic iCIMS career portals (``careers-<company>.icims.com/jobs/search``).

A row's Link is the portal's search page a person opens, e.g.
``https://careers-acme.icims.com/jobs/search?ss=1&searchKeyword=intern``.
The portal renders its results on the server, inside an iframe whose URL is
the same search plus ``in_iframe=1``; this module reads that page as HTML,
keeping every search parameter of the Link (``searchKeyword``,
``searchCategory``, ``searchLocation``…).

Pages hold about 20 jobs and are chosen with ``pr`` (counting from 0); the
first page says "Page 1 of N". A job's id, from its link
``/jobs/<id>/<slug>/job``, is the stable key.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urlencode, urlsplit, urlunsplit

from ..models import Posting
from .base import adapter, get, paged, query, soup, text

logger = logging.getLogger(__name__)

NAME = "icims"
# Requests per company per run (about 1,000 jobs); a bigger scope is cut short.
MAX_PAGES = 50
# Set by this module: the results page, and the iframe's server-rendered view.
DROPPED = {"pr", "in_iframe"}
JOB_ID = re.compile(r"/jobs/(\d+)/")
PAGE_COUNT = re.compile(r"Page\s+\d+\s+of\s+(\d+)")


def page_url(url: str, page: int) -> str:
    """Return the server-rendered results page *page* (from 0) of a portal search *url*."""
    parts = urlsplit(url)
    params = [(k, v) for k, values in query(url).items() if k not in DROPPED for v in values]
    params += [("in_iframe", "1"), ("pr", str(page))]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), ""))


def parse_results(html: str) -> tuple[List[Posting], Optional[int]]:
    """Return the postings on a results page and its page count, if shown."""
    page = soup(html)
    postings = []
    for anchor in page.select("a.iCIMS_Anchor[href]"):
        match = JOB_ID.search(anchor["href"])
        if not match:
            continue
        heading = anchor.find(["h3", "h2", "h4"])
        if heading is not None:
            title = text(heading)
        else:
            for label in anchor.select(".sr-only, .field-label"):
                label.decompose()
            title = text(anchor)
        if title:
            postings.append(Posting(f"{NAME}:{match.group(1)}", title))
    count = PAGE_COUNT.search(page.get_text(" "))
    return postings, int(count.group(1)) if count else None


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the jobs an iCIMS portal search URL shows, across all its pages."""
    pages: Dict[str, int] = {}

    def fetch_page(page: int) -> List[Posting]:
        if "count" in pages and page >= pages["count"]:
            return []
        postings, count = parse_results(get(page_url(url, page)).text)
        if count is not None:
            pages["count"] = count
        return postings

    return paged(fetch_page, max_pages=MAX_PAGES)
