"""Read classic iCIMS career portals (``careers-<company>.icims.com/jobs/search``).

A row's Link is the portal's search page a person opens, e.g.
``https://careers-acme.icims.com/jobs/search?ss=1&searchKeyword=intern``.
The portal renders its results on the server, inside an iframe whose URL is
the same search plus ``in_iframe=1``; this module reads that page as HTML,
keeping every search parameter of the Link (``searchKeyword``,
``searchCategory``, ``searchLocation``…).

Pages hold about 20 jobs and are chosen with ``pr`` (counting from 0); the
first page says "Page 1 of N". A job's id, from its link
``/jobs/<id>/<slug>/job``, is the stable key; that link, without the iframe
view's ``in_iframe=1``, is the job's page.

Each result's "Job Locations" field codes its place as country, region and
city (``US-CA-San Carlos``, ``JP-13-Tokyo``), written "San Carlos, CA" and
"Tokyo, Japan"; several are separated by ``|``.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urlencode, urlsplit, urlunsplit

from ..models import Posting
from .base import adapter, bare_url, format_place, get, paged, place, query, soup, text, us_state

logger = logging.getLogger(__name__)

NAME = "icims"
# Requests per company per run (about 1,000 jobs); a bigger scope is cut short.
MAX_PAGES = 50
# Set by this module: the results page, and the iframe's server-rendered view.
DROPPED = {"pr", "in_iframe"}
JOB_ID = re.compile(r"/jobs/(\d+)/")
PAGE_COUNT = re.compile(r"Page\s+\d+\s+of\s+(\d+)")
# The labels a result gives its location field.
LOCATION_LABELS = {"job locations", "job location", "locations", "location"}
COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")
REGION_CODE = re.compile(r"^[A-Za-z0-9]{1,3}$")


def coded_place(code: str) -> str:
    """Return an iCIMS location code written out: ``US-CA-San Carlos`` → "San Carlos, CA".

    A numeric region (``JP-13-Tokyo``) is left out, and a city may hold hyphens
    (``US-NC-Winston-Salem``). Text that is no such code is kept as it is.
    """
    code = " ".join(code.split())
    country, _, rest = code.partition("-")
    if not COUNTRY_CODE.match(country) or not rest:
        return code
    region, _, city = rest.partition("-")
    if not city:
        # "US-CA" names a state; "US-Remote" or "SG-Singapore" a place.
        if country == "US" and us_state(region):
            return format_place("", region, country)
        return format_place(rest, "", country)
    if not REGION_CODE.match(region):
        region, city = "", rest
    return format_place(city, "" if region.isdigit() else region, country)


def location(anchor) -> str:
    """Return the location field of the result a job link is in, and how many more it names."""
    card = anchor.find_parent(class_="iCIMS_JobCardItem") or anchor.find_parent(class_="row")
    if card is None:
        return ""
    for label in card.select(".field-label"):
        if text(label).casefold() in LOCATION_LABELS:
            value = label.find_next_sibling()
            if value is None and label.parent is not None and label.parent.name == "dt":
                # Newer cards put the label in a <dt> and the codes in the <dd> after it.
                value = label.parent.find_next_sibling("dd")
            codes = text(value).split("|") if value is not None else []
            return place(None, [coded_place(c) for c in codes])
    return ""


def page_url(url: str, page: int) -> str:
    """Return the server-rendered results page *page* (from 0) of a portal search *url*."""
    parts = urlsplit(url)
    params = [(k, v) for k, values in query(url).items() if k not in DROPPED for v in values]
    params += [("in_iframe", "1"), ("pr", str(page))]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), ""))


def parse_results(html: str, base_url: str = "") -> tuple[List[Posting], Optional[int]]:
    """Return the postings on a results page at *base_url* and its page count, if shown."""
    page = soup(html)
    postings = []
    for anchor in page.select("a.iCIMS_Anchor[href]"):
        match = JOB_ID.search(anchor["href"])
        if not match:
            continue
        where = location(anchor)
        heading = anchor.find(["h3", "h2", "h4"])
        if heading is not None:
            title = text(heading)
        else:
            for label in anchor.select(".sr-only, .field-label"):
                label.decompose()
            title = text(anchor)
        if title:
            postings.append(Posting(f"{NAME}:{match.group(1)}", title, where, bare_url(anchor["href"], base_url)))
    count = PAGE_COUNT.search(page.get_text(" "))
    return postings, int(count.group(1)) if count else None


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the jobs an iCIMS portal search URL shows, across all its pages."""
    pages: Dict[str, int] = {}

    def fetch_page(page: int) -> List[Posting]:
        if "count" in pages and page >= pages["count"]:
            return []
        results = page_url(url, page)
        postings, count = parse_results(get(results).text, results)
        if count is not None:
            pages["count"] = count
        return postings

    return paged(fetch_page, max_pages=MAX_PAGES)
