"""Read Bank of America's career site (``careers.bankofamerica.com``) from the JSON behind it.

A row's Link is the job search page a person opens, e.g.
``https://careers.bankofamerica.com/en-us/students/job-search?ref=search&rows=24&search=jobsByLocation&searchstring=United+States``.
That page asks ``GET /services/campusjobssearchservlet?<its query>`` (students
pages; ``/services/jobssearchservlet`` for the experienced-hire search) for
``rows`` jobs from ``start``, and the answer's ``totalMatches`` says how many
there are. This module sends the URL's own search parameters (``search``,
``searchstring``, ``division``…) and pages with ``start``/``rows`` itself.

A job's ``jobRequisitionId`` is the stable key, and its ``jcrURL``
(``/en-us/students/job-detail/<id>/<slug>``) is the job's page. Its ``city``,
``state`` and ``country`` are where it is ("New York, NY"), and
``additionalLocations`` ("Chicago, Illinois, United States; …") the others,
counted after it.
"""
from __future__ import annotations

import logging
from typing import List
from urllib.parse import urlsplit

from ..models import Posting
from .base import adapter, format_place, get, paged, place, query, tidy_place, title_id

logger = logging.getLogger(__name__)

NAME = "bankofamerica"
ORIGIN = "https://careers.bankofamerica.com"
CAMPUS_API = ORIGIN + "/services/campusjobssearchservlet"
CAREERS_API = ORIGIN + "/services/jobssearchservlet"
PAGE_SIZE = 100
# Requests per company per run; a bigger search is cut short.
MAX_PAGES = 20
# Set here for paging, or only steer the page (``ref``).
DROPPED = {"start", "rows", "ref"}


def api_for(url: str) -> str:
    """Return the servlet that answers the search page *url*."""
    return CAMPUS_API if "/students/" in urlsplit(url).path.lower() else CAREERS_API


def _where(text: str) -> str:
    """Return "New York, New York, United States" (city, state, country) as "New York, NY"."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) >= 3:
        return format_place(parts[0], ", ".join(parts[1:-1]), parts[-1])
    return tidy_place(text)


def to_posting(job: dict) -> Posting:
    title = " ".join(str(job.get("postingTitle") or "").split())
    key = str(job.get("jobRequisitionId") or "").strip()
    path = job.get("jcrURL") or ""
    url = ORIGIN + path if path.startswith("/") else ""
    others = [_where(p) for p in str(job.get("additionalLocations") or "").split(";")]
    location = place(format_place(job.get("city"), job.get("state"), job.get("country")), others)
    return Posting(f"{NAME}:{key}" if key else title_id(NAME, title), title, location, url)


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every job a Bank of America search URL shows."""
    api = api_for(url)
    params = [(k, v) for k, values in query(url).items() if k not in DROPPED for v in values]
    total = None

    def fetch_page(page: int) -> List[Posting]:
        nonlocal total
        if total is not None and page * PAGE_SIZE >= total:
            return []
        answer = get(api, params=params + [("start", str(page * PAGE_SIZE)), ("rows", str(PAGE_SIZE))],
                     headers={"Accept": "application/json", "Referer": url}).json()
        if not isinstance(answer, dict) or "jobsList" not in answer:
            raise ValueError(f"Unexpected answer from {api}")
        total = int(answer.get("totalMatches") or 0)
        return [to_posting(j) for j in answer.get("jobsList") or [] if j.get("postingTitle")]

    return paged(fetch_page, delay=1.0, max_pages=MAX_PAGES)
