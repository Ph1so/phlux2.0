"""Read Oracle Cloud HCM (Candidate Experience) career sites from their REST API.

A row's Link is the search page a person opens,
``https://<host>/hcmUI/CandidateExperience/<lang>/sites/<site>/jobs?keyword=…&locationId=…``.
That page asks
``GET https://<host>/hcmRestApi/resources/latest/recruitingCEJobRequisitions``
with ``finder=findReqs;siteNumber=<site>,keyword=…,locationId=…,limit=…,offset=…``
(the URL's search parameters become the finder's), and ``expand=requisitionList``,
without which the answer has no jobs. This module sends the same request.

Carried over from the URL: ``keyword``, ``locationId`` (or the ``location``
text when no id is given), ``sortBy``, ``radius``/``radiusUnit``,
``lastSelectedFacet`` and the ``selected…Facet(s)`` lists (several ids joined
by ``;``). ``mode`` and ``locationLevel`` only steer the page. Like the page,
``keyword`` also matches job descriptions; add ``->FILTER:`` to the row to
match titles.

The API returns at most :data:`PAGE_SIZE` jobs per request (a larger limit
returns none); pages follow ``offset`` until ``TotalJobsCount``. A job's
``Id`` (the requisition number) is the stable key.
"""
from __future__ import annotations

import logging
from typing import Dict, List
from urllib.parse import unquote, urlsplit

from ..models import Posting
from .base import adapter, first, get, paged, query

logger = logging.getLogger(__name__)

NAME = "oraclehcm"
API = "{origin}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
PAGE_SIZE = 200
# Requests per company per run (10,000 jobs); a bigger scope is cut short.
MAX_PAGES = 50
# Search-page parameters that are finder parameters under the same name.
FINDER_PARAMS = ("keyword", "locationId", "sortBy", "radius", "radiusUnit", "lastSelectedFacet",
                 "workLocationCountryCode", "workLocationZipCode")


def finder_terms(url: str) -> List[str]:
    """Return the ``name=value`` terms of the ``findReqs`` finder for a search page *url*.

    Raises:
        ValueError: If *url* is not a Candidate Experience site URL.
    """
    segments = [unquote(s) for s in urlsplit(url).path.split("/") if s]
    if "sites" not in segments or segments.index("sites") + 1 >= len(segments):
        raise ValueError(f"No Candidate Experience site in {url}")
    site = segments[segments.index("sites") + 1]

    params = query(url)
    terms = [f"siteNumber={site}"]
    for key in FINDER_PARAMS:
        if first(params, key):
            terms.append(f"{key}={first(params, key)}")
    if not first(params, "locationId") and first(params, "location"):
        terms.append(f"location={first(params, 'location')}")
    for key in sorted(params):
        if key.startswith("selected") and (key.endswith("Facet") or key.endswith("Facets")) and first(params, key):
            terms.append(f"{key}={';'.join(v for v in params[key] if v)}")
    return terms


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the jobs an Oracle Cloud HCM search URL shows, across all its pages."""
    parts = urlsplit(url)
    api = API.format(origin=f"{parts.scheme}://{parts.netloc}")
    terms = finder_terms(url)
    total: Dict[str, int] = {}

    def fetch_page(page: int) -> List[Posting]:
        offset = page * PAGE_SIZE
        if "count" in total and offset >= total["count"]:
            return []
        finder = "findReqs;" + ",".join(terms + [f"limit={PAGE_SIZE}", f"offset={offset}"])
        body = get(api, params={"onlyData": "true", "expand": "requisitionList", "finder": finder}).json()
        items = body.get("items") or []
        if not items:
            return []
        total["count"] = int(items[0].get("TotalJobsCount") or 0)
        return [
            Posting(f"{NAME}:{job['Id']}", " ".join(job["Title"].split()))
            for job in items[0].get("requisitionList") or []
        ]

    postings = paged(fetch_page, max_pages=MAX_PAGES)
    if total.get("count", 0) > len(postings):
        logger.warning("%s lists %d jobs; read %d", url, total["count"], len(postings))
    return postings
