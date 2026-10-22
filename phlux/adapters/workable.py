"""Workable boards (``apply.workable.com/<slug>/``).

Jobs come from the v3 jobs endpoint the board page itself calls, which pages
with a ``nextPage`` token and takes the board's filters in its request body.
The board URL's ``query`` (search text, which Workable matches against
descriptions too), ``department`` (ids), ``worktype`` and ``workplace`` are
passed on. Its ``location`` filter is not understood here, so a URL with one
is refused rather than read as the whole board.
"""
from __future__ import annotations

from typing import List

from ..models import Posting
from .base import adapter, first, path_slug, post, query

API = "https://apply.workable.com/api/v3/accounts/{slug}/jobs"
MAX_PAGES = 50


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


@adapter("workable")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the postings a Workable board URL shows, filtered by its query."""
    api = API.format(slug=path_slug(url))
    body = search_body(url)
    postings: List[Posting] = []
    for _ in range(MAX_PAGES):
        data = post(api, json=body).json()
        postings.extend(Posting(f"workable:{j['shortcode']}", j["title"]) for j in data.get("results", []))
        if not data.get("nextPage") or not data.get("results"):
            break
        body = {**body, "token": data["nextPage"]}
    return postings
