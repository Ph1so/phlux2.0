"""Rippling ATS boards (``ats.rippling.com/<slug>/jobs``).

The board page reads its jobs from ``/api/v2/board/<slug>/jobs``. Like the
older ``api.rippling.com/.../v1/board/<slug>/jobs`` it repeats a job posted in
several locations once per location, under the same id; those collapse into
one posting here. That endpoint takes the board URL's own filters —
``searchQuery``, ``workplaceType``, ``country``, ``state``, ``city``,
``departments`` — so they are passed through as they are, and a person
opening the link sees the same jobs. Each job's ``url`` is its page,
``ats.rippling.com/<slug>/jobs/<id>``.

A job's location is the first of its items' location names ("Arlington, VA",
"Remote (United States)") in alphabetical order, with a count of the rest:
the items come in no set order.
"""
from __future__ import annotations

import re
from typing import Dict, List, Set
from urllib.parse import urlsplit

from ..models import Posting
from .base import adapter, format_place, get, paged, place, query, tidy_place, unique

API = "https://ats.rippling.com/api/v2/board/{slug}/jobs"
JOB_PAGE = "https://ats.rippling.com/{slug}/jobs/{id}"
PAGE_SIZE = 100
# The adapter pages through the board itself.
PAGING_PARAMS = {"page", "pageSize"}
# Boards may be served under a locale, e.g. ats.rippling.com/en-GB/acme/jobs.
LOCALE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


def board_slug(url: str) -> str:
    """Return the board slug from an ``ats.rippling.com`` board or job URL."""
    parts = [p for p in urlsplit(url).path.split("/") if p]
    if parts and LOCALE.match(parts[0]):
        parts = parts[1:]
    if not parts:
        raise ValueError(f"No Rippling board in {url}")
    return parts[0]


def board_filters(url: str) -> Dict[str, List[str]]:
    """Return the URL's non-empty filters, without its paging parameters."""
    filters = {}
    for key, values in query(url).items():
        values = [v for v in values if v]
        if key not in PAGING_PARAMS and values:
            filters[key] = values
    return filters


def location_names(job: dict) -> Set[str]:
    """Return the names of the locations one board item lists."""
    names = set()
    for loc in job.get("locations") or []:
        if isinstance(loc, dict):
            name = tidy_place(loc.get("name")) or format_place(loc.get("city"), loc.get("stateCode"),
                                                                loc.get("countryCode"))
            if name:
                names.add(name)
    return names


@adapter("rippling")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the postings a Rippling board URL shows, filtered by its query."""
    slug = board_slug(url)
    api = API.format(slug=slug)
    filters = board_filters(url)
    total_pages: List[int] = []
    # Every location of each job, from all the items that repeat it.
    locations: Dict[str, Set[str]] = {}

    def page(n: int) -> List[Posting]:
        if total_pages and n >= total_pages[0]:
            return []
        data = get(api, params={**filters, "page": n, "pageSize": PAGE_SIZE}).json()
        total_pages[:] = [data.get("totalPages") or 1]
        items = data.get("items", [])
        for j in items:
            locations.setdefault(f"rippling:{j['id']}", set()).update(location_names(j))
        return [
            Posting(f"rippling:{j['id']}", j["name"], url=j.get("url") or JOB_PAGE.format(slug=slug, id=j["id"]))
            for j in items
        ]

    postings = unique(paged(page))
    for posting in postings:
        # Sorted, so a job reads the same whichever of its items came first.
        posting.location = place(None, sorted(locations.get(posting.id, ())))
    return postings
