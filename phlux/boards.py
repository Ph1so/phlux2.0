"""Read whole job boards from the public APIs of Greenhouse, Lever and Ashby.

Other job systems and company sites live in :mod:`phlux.adapters`; their
fetchers join the same registry, :data:`FETCHERS`.

These boards publish every posting as JSON, so no browser is needed and a board
of thousands of jobs comes back in one request. Each posting carries the board's
own job id, which survives title edits, so storage can tell a renamed posting
from a new one.

A company's ``companies.csv`` link still says which board to read and how to
narrow it: the URL's query parameters (``keyword``, ``departments[]``,
``offices[]``, Lever's ``commitment``, Ashby's ``locationId``…) become filters
applied here, so the results match what that URL shows a person. One difference:
Greenhouse's ``keyword`` search also matches job descriptions, but here it only
matches the start of a word in the title (see :func:`keyword_in`).
"""
from __future__ import annotations

import functools
import logging
import re
from typing import Callable, Dict, Iterable, List, Set, Tuple
from urllib.parse import urlsplit

import requests

from .adapters import ADAPTERS
from .adapters.base import path_slug as _path_slug
from .adapters.base import query as _query
from .models import Posting

logger = logging.getLogger(__name__)

TIMEOUT = 30


def _get(url: str, **kwargs) -> requests.Response:
    response = requests.get(url, timeout=TIMEOUT, **kwargs)
    response.raise_for_status()
    return response


# Words that merely start with "intern" and so would match a keyword search for it.
_NOT_INTERN = re.compile(r"\bintern(?:al|ally|als|ation|ational|ationally|et)\b", re.IGNORECASE)


def keyword_in(title: str, keyword: str) -> bool:
    """Return True if *keyword* starts a word in *title* (case-insensitive).

    "intern" must not just be the start of Internal, International or Internet:
    those are removed before matching, so "Internal Tools Intern" still matches.
    """
    if keyword.lower().startswith("intern"):
        title = _NOT_INTERN.sub(" ", title)
    return re.search(r"\b" + re.escape(keyword), title, re.IGNORECASE) is not None


def _title_has(postings: Iterable[Tuple[Posting, dict]], keywords: List[str]) -> List[Tuple[Posting, dict]]:
    return [(p, raw) for p, raw in postings if any(keyword_in(p.title, k) for k in keywords)]


# ── Greenhouse ────────────────────────────────────────────────────────────────

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/{path}"


def greenhouse_slug(url: str) -> str:
    """Return the board token from a Greenhouse board or embed URL."""
    params = _query(url)
    if "for" in params:
        return params["for"][0]
    return _path_slug(url)


def _greenhouse_job_ids(slug: str, kind: str, wanted: Set[str]) -> Set[int]:
    """Return ids of jobs under the *wanted* departments or offices, children included.

    The board's own filter includes sub-departments and sub-offices, so this does too.
    """
    groups = _get(GREENHOUSE_API.format(slug=slug, path=kind)).json()[kind]
    by_id = {str(g["id"]): g for g in groups}
    pending, seen = [g for g in wanted if g in by_id], set()
    jobs: Set[int] = set()
    while pending:
        group = by_id[pending.pop()]
        if str(group["id"]) in seen:
            continue
        seen.add(str(group["id"]))
        jobs.update(j["id"] for j in group.get("jobs", []))
        # An office lists its jobs under its departments rather than directly.
        for dept in group.get("departments", []):
            jobs.update(j["id"] for j in dept.get("jobs", []))
        pending.extend(str(c) for c in group.get("child_ids", []) if str(c) in by_id)
    return jobs


def greenhouse_postings(url: str) -> List[Posting]:
    """Return the postings a Greenhouse board URL shows, filtered by its query."""
    slug = greenhouse_slug(url)
    params = _query(url)
    jobs = _get(GREENHOUSE_API.format(slug=slug, path="jobs")).json()["jobs"]
    pairs = [(Posting(f"greenhouse:{j['id']}", j["title"]), j) for j in jobs]
    if params.get("keyword"):
        pairs = _title_has(pairs, params["keyword"])
    for kind in ("departments", "offices"):
        if params.get(kind):
            ids = _greenhouse_job_ids(slug, kind, set(params[kind]))
            pairs = [(p, j) for p, j in pairs if j["id"] in ids]
    return [p for p, _ in pairs]


# ── Lever ─────────────────────────────────────────────────────────────────────

# Query parameters on a jobs.lever.co URL that filter by a posting category.
LEVER_CATEGORIES = ("commitment", "team", "department", "location")


def lever_postings(url: str) -> List[Posting]:
    """Return the postings a Lever board URL shows, filtered by its query."""
    parts = urlsplit(url)
    host = "api.eu.lever.co" if ".eu." in parts.netloc else "api.lever.co"
    slug = _path_slug(url)
    jobs = _get(f"https://{host}/v0/postings/{slug}", params={"mode": "json"}).json()
    params = _query(url)
    for key in LEVER_CATEGORIES:
        if params.get(key):
            wanted = {v.lower() for v in params[key]}
            jobs = [j for j in jobs if str(j.get("categories", {}).get(key, "")).lower() in wanted]
    return [Posting(f"lever:{j['id']}", j["text"]) for j in jobs]


# ── Ashby ─────────────────────────────────────────────────────────────────────

ASHBY_API = "https://api.ashbyhq.com/posting-api/job-board/{slug}"
ASHBY_GRAPHQL = "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams"
_ASHBY_LOCATIONS_QUERY = """
query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {
  jobBoard: jobBoardWithTeams(organizationHostedJobsPageName: $organizationHostedJobsPageName) {
    jobPostings { id locationId secondaryLocations { locationId } }
  }
}"""


def _ashby_ids_at(slug: str, location_ids: Set[str]) -> Set[str]:
    """Return ids of postings at any of *location_ids*, primary or secondary.

    The public API gives location names but not the ids a board URL filters by,
    so this asks the GraphQL endpoint the board page itself uses.
    """
    response = requests.post(
        ASHBY_GRAPHQL,
        json={
            "operationName": "ApiJobBoardWithTeams",
            "variables": {"organizationHostedJobsPageName": slug},
            "query": _ASHBY_LOCATIONS_QUERY,
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    postings = response.json()["data"]["jobBoard"]["jobPostings"]
    return {
        p["id"]
        for p in postings
        if p["locationId"] in location_ids
        or any(s["locationId"] in location_ids for s in p.get("secondaryLocations") or [])
    }


def ashby_postings(url: str) -> List[Posting]:
    """Return the listed postings an Ashby board URL shows, filtered by its query."""
    slug = _path_slug(url)
    jobs = [j for j in _get(ASHBY_API.format(slug=slug)).json()["jobs"] if j.get("isListed", True)]
    params = _query(url)
    if params.get("locationId"):
        ids = _ashby_ids_at(slug, set(params["locationId"]))
        jobs = [j for j in jobs if j["id"] in ids]
    return [Posting(f"ashby:{j['id']}", j["title"]) for j in jobs]


# ── Entry point ───────────────────────────────────────────────────────────────

FETCHERS: Dict[str, Callable[[str], List[Posting]]] = {
    "greenhouse": greenhouse_postings,
    "lever": lever_postings,
    "ashby": ashby_postings,
    **ADAPTERS,
}
# Every ``@name`` read without a browser (see phlux.scraping.board_of).
BOARDS = tuple(FETCHERS)


def board_postings(board: str, urls: str, arg: str = "") -> List[Posting]:
    """Return the postings for every ``->``-separated board URL, without duplicates.

    Several URLs act like several searches of the board (e.g. ``keyword=intern``
    and ``keyword=co-op``): a posting shown by any of them is kept once. *arg*
    (from ``@board:arg``) is passed to adapters that take one.
    """
    fetch = FETCHERS[board]
    if arg:
        fetch = functools.partial(fetch, arg=arg)
    seen: Set[str] = set()
    postings: List[Posting] = []
    for url in urls.split("->"):
        url = url.strip()
        if not url:
            continue
        for posting in fetch(url):
            if posting.id not in seen:
                seen.add(posting.id)
                postings.append(posting)
    return postings
