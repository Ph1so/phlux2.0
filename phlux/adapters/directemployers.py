"""Read DirectEmployers microsites (e.g. jobs.sw.siemens.com) from their search API.

These career sites are Nuxt apps run by DirectEmployers (``seo.nlx.org``,
``microsites.dejobs.org``). A row's Link is the search page a person opens,
e.g. ``https://jobs.sw.siemens.com/locations/usa/jobs/?q=intern``
(``@directemployers``). The page asks
``GET https://prod-search-api.jobsyn.org/api/v1/<source>/search`` with the
site's host in an ``X-Origin`` header (required) and the search as parameters:
the Link's query (``q``, ``location``…) is passed through, and a
``/locations/<slug>/`` path segment becomes ``location=<slug>``, as the site's
router does. Other path filters (``/job-family/<x>/``…) are named per site,
so put those in the query instead.

The search page ranks a keyword with Google's Cloud Talent Solution
(``google-talent``), which matches loosely (``q=intern`` brings back senior
roles) and so needs a ``FILTER`` on the row anyway; this module reads the
site's Solr index (``solr``, which the site's own job widgets use) instead: the
same postings, matched by keyword, in a stable order. The API returns 10 jobs a
page whatever ``num_items`` says; ``page`` counts from 1 to ``total_pages``.

A job's ``guid`` (32 hex digits) is the stable key; one requisition (``reqid``)
posted in several towns has a guid per town. Its page is
``https://<host>/<location slug>/<title_slug>/<guid>/job/``; the site reads the
job by guid and corrects the slugs if they differ. ``city_exact``,
``state_short_exact`` and ``country_exact`` are where it is ("St. Louis, MO").
"""
from __future__ import annotations

import logging
import re
import time
from typing import List, Tuple
from urllib.parse import urlsplit

from ..models import Posting
from .base import adapter, format_place, get, query, tidy_place

logger = logging.getLogger(__name__)

NAME = "directemployers"
API = "https://prod-search-api.jobsyn.org/api/v1/solr/search"
# Requests per company per run (1,000 jobs); a bigger scope is cut short.
MAX_PAGES = 100
# Seconds between page requests.
DELAY = 0.5
# Paging is this module's job.
DROPPED = {"page", "offset", "num_items"}
_LOCATIONS = re.compile(r"/locations/([^/]+)/")
_GUID = re.compile(r"^[0-9A-Fa-f]{32}$")


def api_request(url: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Return the ``X-Origin`` host and the search parameters of a microsite search *url*."""
    parts = urlsplit(url)
    params = [(key, v) for key, values in query(url).items() if key not in DROPPED for v in values if v]
    located = _LOCATIONS.search(parts.path + "/")
    if located and not any(key == "location" for key, _ in params):
        params.append(("location", located.group(1)))
    return parts.netloc, params


def slug(value: str) -> str:
    """Return *value* as a URL slug ("St. Louis, MO" → "st-louis-mo")."""
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def location(job: dict) -> str:
    city, state, country = job.get("city_exact"), job.get("state_short_exact"), job.get("country_exact")
    if city or state or country:
        return format_place(city, state, country)
    return tidy_place(job.get("location_exact"))


def job_url(host: str, job: dict) -> str:
    where = slug(str(job.get("location_exact") or job.get("country_exact") or "")) or "none"
    title = str(job.get("title_slug") or slug(str(job.get("title_exact") or ""))) or "job"
    return f"https://{host}/{where}/{title}/{job['guid']}/job/"


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the jobs a DirectEmployers microsite search URL shows, across all its pages."""
    host, params = api_request(url)
    headers = {"Accept": "application/json", "X-Origin": host}
    postings: List[Posting] = []
    seen: set = set()
    pages = 1
    total = 0
    for page in range(1, MAX_PAGES + 1):
        if page > pages:
            break
        if page > 1:
            time.sleep(DELAY)
        body = get(API, params=params + [("page", str(page))], headers=headers).json()
        pagination = body.get("pagination") or {}
        pages = int(pagination.get("total_pages") or 0)
        total = int(pagination.get("total") or 0)
        jobs = body.get("jobs") or []
        fresh = 0
        for job in jobs:
            guid = str(job.get("guid") or "")
            title = " ".join(str(job.get("title_exact") or "").split())
            if not _GUID.match(guid) or not title or guid in seen:
                continue
            seen.add(guid)
            fresh += 1
            postings.append(Posting(f"{NAME}:{guid.upper()}", title, location(job), job_url(host, job)))
        if not fresh:
            break
    if pages > MAX_PAGES:
        logger.warning("%s has %d pages; read %d", url, pages, MAX_PAGES)
    elif total > len(postings):
        logger.warning("%s lists %d jobs; read %d", url, total, len(postings))
    return postings
