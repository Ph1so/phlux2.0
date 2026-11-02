"""Uber careers search (``jobs.uber.com/en/jobs/?...``).

The search page fetches its results from ``/api/jobs/search/`` with its own
query string (``countries``, ``team``, ``subTeam``, ``search``...), so the link's
query is passed through as is, adding ``page=N`` for each page of 10. The API
answers ``jobs``, ``totalJobs`` and ``totalPages``. Postings are keyed by
Uber's job id, the one in ``/en/jobs/<id>/``; each job's ``Urls`` give that
page's path. Its ``Locations`` (city, region, country) are written "New York
City, NY", the first with a count of the rest; a remote job with none is "Remote".
"""
from __future__ import annotations

from typing import List
from urllib.parse import parse_qsl, urljoin, urlsplit

from ..models import Posting
from .base import adapter, format_place, get, place, unique

SITE = "https://jobs.uber.com"
API = SITE + "/api/jobs/search/"
MAX_PAGES = 50


def job_url(job: dict) -> str:
    """Return a job's page: its default ``Urls`` entry (a path), on the careers site."""
    urls = [u for u in job.get("Urls") or [] if u.get("Url")]
    chosen = next((u for u in urls if u.get("IsDefault")), urls[0] if urls else None)
    return urljoin(SITE, chosen["Url"] if chosen else f"/en/jobs/{job['Id']}/")


def location(job: dict) -> str:
    """Return a job's first location and how many more it lists."""
    names = [format_place(loc.get("City"), loc.get("Region"), loc.get("Country") or loc.get("CountryCode"))
             for loc in job.get("Locations") or [] if isinstance(loc, dict)]
    return place(None, names) or ("Remote" if job.get("Remote") else "")


@adapter("uber")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every posting the Uber careers search in *url* finds."""
    params = [(k, v) for k, v in parse_qsl(urlsplit(url).query) if k != "page"]
    postings: List[Posting] = []
    page, pages = 1, 1
    while page <= pages:
        result = get(API, params=params + [("page", page)], headers={"Accept": "application/json"}).json()
        pages = result.get("totalPages") or 1
        if pages > MAX_PAGES:
            raise RuntimeError(f"Uber careers search finds {result.get('totalJobs')} jobs; narrow {url}")
        postings += [Posting(f"uber:{j['Id']}", " ".join(j["Title"].split()), location(j), job_url(j))
                     for j in result.get("jobs") or []]
        page += 1
    return unique(postings)
