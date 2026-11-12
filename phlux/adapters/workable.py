"""Workable boards (``apply.workable.com/<slug>/``).

Jobs come from the v3 jobs endpoint the board page itself calls, which pages
with a ``nextPage`` token and takes the board's filters in its request body.
The board URL's ``query`` (search text, which Workable matches against
descriptions too), ``department`` (ids), ``worktype`` and ``workplace`` are
passed on. Its ``location`` filter is not understood here, so a URL with one
is refused rather than read as the whole board. A job's page is
``apply.workable.com/<slug>/j/<shortcode>/``. Its ``location`` (city, region,
country) is written "Fremont, CA", followed by a count of its other shown
``locations``; a remote job naming no city is "Remote".
"""
from __future__ import annotations

import time
from typing import List

from ..models import Posting
from .base import adapter, first, format_place, path_slug, place, post, query

API = "https://apply.workable.com/api/v3/accounts/{slug}/jobs"
JOB_PAGE = "https://apply.workable.com/{slug}/j/{shortcode}/"
MAX_PAGES = 50
# Workable answers 429 to a burst of requests from one address (the bot reads
# several Workable boards at once), so pages are spaced out.
PAGE_DELAY = 1.0


def search_body(url: str) -> dict:
    """Return the v3 search body for the filters in a board URL's query."""
    params = query(url)
    if any(params.get("location", [])):
        raise ValueError(f"Workable location filters are not supported: {url}")
    return {
        "query": first(params, "query") or first(params, "search"),
        "location": [],
        "department": [int(d) for d in params.get("department", []) if d],
        "worktype": [w for w in params.get("worktype", []) if w],
        "workplace": [w for w in params.get("workplace", []) if w],
        "remote": [],
    }


def _place(loc) -> str:
    if not isinstance(loc, dict):
        return ""
    return format_place(loc.get("city"), loc.get("region"), loc.get("countryCode") or loc.get("country"))


def location(job: dict) -> str:
    """Return a job's location, plus a count of the other locations it shows."""
    others = [_place(loc) for loc in job.get("locations") or [] if isinstance(loc, dict) and not loc.get("hidden")]
    found = place(_place(job.get("location")), others)
    remote = job.get("remote") or job.get("workplace") == "remote"
    if remote and not (job.get("location") or {}).get("city"):
        return "Remote"
    return found


@adapter("workable")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the postings a Workable board URL shows, filtered by its query."""
    slug = path_slug(url)
    api = API.format(slug=slug)
    body = search_body(url)
    postings: List[Posting] = []
    for page in range(MAX_PAGES):
        if page:
            time.sleep(PAGE_DELAY)
        data = post(api, json=body).json()
        postings.extend(
            Posting(f"workable:{j['shortcode']}", j["title"], location(j),
                    JOB_PAGE.format(slug=slug, shortcode=j["shortcode"]))
            for j in data.get("results", [])
        )
        if not data.get("nextPage") or not data.get("results"):
            break
        body = {**body, "token": data["nextPage"]}
    return postings
