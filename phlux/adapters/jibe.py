"""Read Jibe (iCIMS Attract) career sites from the JSON API behind them.

A row's Link is the job search page a person opens, e.g.
``https://careers.rivian.com/careers-home/jobs?categories=Internships%20%26%20Early%20Career``.
That page asks ``GET https://<host>/api/jobs?page=N&limit=…`` with the URL's
own search parameters (``keywords``, ``location``, ``categories``, ``tags1``,
``sortBy``…), so they are passed through as they are; this module only sets
``page`` and ``limit``.

The API returns at most :data:`PAGE_SIZE` jobs per request (a larger limit is
an error); pages count from 1 until ``totalCount``. A job's ``req_id`` (its
iCIMS requisition number, also its ``slug``) is the stable key.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple
from urllib.parse import urlsplit

from ..models import Posting
from .base import adapter, get, paged, query

logger = logging.getLogger(__name__)

NAME = "jibe"
API = "{origin}/api/jobs"
PAGE_SIZE = 100
# Requests per company per run (5,000 jobs); a bigger scope is cut short.
MAX_PAGES = 50
# Paging is this module's job.
DROPPED = {"page", "limit"}


def api_request(url: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Return the jobs API URL and the search parameters of a Jibe search page *url*."""
    parts = urlsplit(url)
    params = [(key, v) for key, values in query(url).items() if key not in DROPPED for v in values if v]
    return API.format(origin=f"{parts.scheme}://{parts.netloc}"), params


def _job_id(job: dict) -> str:
    return str(job.get("req_id") or job.get("slug") or job.get("apply_url") or "")


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the jobs a Jibe search URL shows, across all its pages."""
    api, params = api_request(url)
    total: Dict[str, int] = {}

    def fetch_page(page: int) -> List[Posting]:
        if "count" in total and page * PAGE_SIZE >= total["count"]:
            return []
        body = get(api, params=params + [("page", str(page + 1)), ("limit", str(PAGE_SIZE))]).json()
        total["count"] = int(body.get("totalCount") or 0)
        jobs = [j.get("data", j) for j in body.get("jobs") or []]
        return [Posting(f"{NAME}:{_job_id(j)}", " ".join(j["title"].split())) for j in jobs if _job_id(j)]

    postings = paged(fetch_page, max_pages=MAX_PAGES)
    if total.get("count", 0) > len(postings):
        logger.warning("%s lists %d jobs; read %d", url, total["count"], len(postings))
    return postings
