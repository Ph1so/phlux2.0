"""Read IBM's careers search (www.ibm.com/careers/search) from the search API behind it.

A row's Link is the search page a person opens, e.g.
``https://www.ibm.com/careers/search?field_keyword_18[0]=Internship&field_keyword_05[0]=United%20States``
(``@ibm``). The page's search box asks ``POST https://www-api.ibm.com/search/api/v2``
(app ``careers``, scope ``careers2``) with an Elasticsearch-style body; each
``field_keyword_NN[i]=<value>`` facet in the Link becomes a filter on that
field (several values of one field match any of them, as on the page):
``field_keyword_18`` is the job's level (Internship, Entry Level, Professional),
``field_keyword_05`` its country, ``field_keyword_08`` its category. The Link's
``q`` keyword search is not read (the page ranks it with its own query logic),
so it is ignored with a warning.

The API returns at most :data:`PAGE_SIZE` jobs per request. The page sorts by
relevance and page views, which shift between requests and would shuffle jobs
across pages, so this module sorts by document id and steps ``from`` until the
total. A job's ``url`` is its page, ``https://careers.ibm.com/careers/JobDetail?jobId=<id>``,
and that ``jobId`` is the stable key. ``field_keyword_19`` is where it is,
"POUGHKEEPSIE, US", written "Poughkeepsie" (the API gives no state), or
"Multiple Cities" as the site says.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Dict, List
from urllib.parse import parse_qs, urlsplit

from ..models import Posting
from .base import adapter, country_name, format_place, is_us, post, tidy_place

logger = logging.getLogger(__name__)

NAME = "ibm"
API = "https://www-api.ibm.com/search/api/v2"
# The API refuses a larger size.
PAGE_SIZE = 100
# Requests per company per run (2,000 jobs); a bigger scope is cut short.
MAX_PAGES = 20
# Seconds between page requests.
DELAY = 0.5
FIELDS = ["_id", "title", "url", "field_keyword_05", "field_keyword_08", "field_keyword_18", "field_keyword_19"]
# "field_keyword_18[0]": a facet, with the page's index of the chosen value.
_FACET = re.compile(r"^(field_keyword_\d+)(?:\[\d*\])?$")


def filters(url: str) -> Dict[str, List[str]]:
    """Return the facet filters (field → chosen values) of an IBM careers search *url*."""
    chosen: Dict[str, List[str]] = {}
    for key, values in parse_qs(urlsplit(url).query, keep_blank_values=False).items():
        facet = _FACET.match(key)
        if facet:
            for value in values:
                if value not in chosen.setdefault(facet.group(1), []):
                    chosen[facet.group(1)].append(value)
        elif key == "q":
            logger.warning("Ignoring q=%r in %s: the IBM adapter reads only field_keyword facets", values, url)
    return chosen


def search_body(chosen: Dict[str, List[str]], start: int) -> dict:
    """Return the API request for one page of the jobs matching *chosen* facets, from *start*."""
    must = [{"term": {field: values[0]}} if len(values) == 1 else {"terms": {field: values}}
            for field, values in chosen.items()]
    return {
        "appId": "careers",
        "scopes": ["careers2"],
        "query": {"bool": {"must": []}},
        "post_filter": {"bool": {"must": must}},
        "size": PAGE_SIZE,
        "from": start,
        "sort": [{"_id": "asc"}],
        "lang": "zz",
        "localeSelector": {},
        "sm": {"query": "", "lang": "zz"},
        "_source": FIELDS,
    }


def ibm_place(value: str | None) -> str:
    """Return IBM's "CITY, CC" location as base.py writes places ("POUGHKEEPSIE, US" → "Poughkeepsie")."""
    value = " ".join((value or "").split())
    city, _, country = value.rpartition(",")
    city, country = city.strip(), country.strip()
    if not city or not country:
        return tidy_place(value)
    if city.isupper():
        city = city.title()
    if is_us(country):
        return tidy_place(f"{city}, {country}") if "," in city else format_place(city, "", "United States")
    return format_place(city, "", country_name(country))


def job_id(job_url: str) -> str:
    """Return the ``jobId`` of a job page URL, or ""."""
    return (parse_qs(urlsplit(job_url).query).get("jobId") or [""])[0]


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the jobs an IBM careers search URL shows, across all its pages."""
    chosen = filters(url)
    postings: List[Posting] = []
    seen: set = set()
    total = None
    for page in range(MAX_PAGES):
        start = page * PAGE_SIZE
        if total is not None and start >= total:
            break
        if page:
            time.sleep(DELAY)
        body = post(API, json=search_body(chosen, start)).json()
        hits = body.get("hits") or {}
        count = hits.get("total")
        total = int(count.get("value", 0) if isinstance(count, dict) else count or 0)
        jobs = [h.get("_source") or {} for h in hits.get("hits") or []]
        if not jobs:
            break
        for job in jobs:
            page_url = str(job.get("url") or "")
            key = job_id(page_url) or page_url
            if not key or key in seen or not job.get("title"):
                continue
            seen.add(key)
            postings.append(Posting(f"{NAME}:{key}", " ".join(str(job["title"]).split()),
                                    ibm_place(job.get("field_keyword_19")), page_url))
    if total and total > len(postings):
        logger.warning("%s lists %d jobs; read %d", url, total, len(postings))
    return postings
