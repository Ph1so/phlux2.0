"""Uber careers search (``jobs.uber.com/en/jobs/?...``).

The search page fetches its results from ``/api/jobs/search/`` with its own
query string (``countries``, ``team``, ``subTeam``, ``search``...), so the link's
query is passed through as is, adding ``page=N`` for each page of 10. The API
answers ``jobs``, ``totalJobs`` and ``totalPages``. Postings are keyed by
Uber's job id, the one in ``/en/jobs/<id>/``.
"""
from __future__ import annotations

from typing import List
from urllib.parse import parse_qsl, urlsplit

from ..models import Posting
from .base import adapter, get, unique

API = "https://jobs.uber.com/api/jobs/search/"
MAX_PAGES = 50


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
        postings += [Posting(f"uber:{j['Id']}", " ".join(j["Title"].split())) for j in result.get("jobs") or []]
        page += 1
    return unique(postings)
