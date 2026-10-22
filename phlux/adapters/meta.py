"""Meta careers job search (``metacareers.com/jobsearch/``).

The search page asks Meta's GraphQL endpoint for its results with a persisted
query (``CareersJobSearchResultsDataQuery``) named by a ``doc_id``. Reading it
takes three steps, as the page does:

1. GET the search page for its cookies and LSD token (a per-session CSRF token).
2. POST ``/graphql`` with the LSD token, the ``doc_id`` and the search filters
   read from the page's URL (``roles[0]=Internship``, ``offices[]=...``, ``q``...).
   Without browser-like ``Sec-Fetch-*`` headers Meta answers 400.
3. If Meta no longer knows the ``doc_id`` (it changes when Meta redeploys), find
   the current one in the page's JavaScript and ask again.

The query returns every matching job at once (no paging). Postings are keyed
by Meta's job id, the one in ``/profile/job_details/<id>/``.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Dict, List, Optional
from urllib.parse import parse_qsl, urlsplit

import requests

from ..models import Posting
from .base import adapter, get, post

logger = logging.getLogger(__name__)

GRAPHQL = "https://www.metacareers.com/graphql"
QUERY = "CareersJobSearchResultsDataQuery"
# The doc_id when this was written; replaced from Meta's JavaScript once stale.
DOC_ID = "27506805582236862"
LSD = re.compile(r'"LSD",\[\],\{"token":"([^"]+)"')
SCRIPT = re.compile(r'<script[^>]+src="(https://static\.xx\.fbcdn\.net/rsrc\.php/[^"]+)"')
OPERATION = re.compile(
    r'__d\("' + QUERY + r'_\w*RelayOperation",\[\],\(function\([\w,]*\)\{\w+\.exports="(\d+)"'
)
# How many of the page's scripts to search for the doc_id before giving up.
MAX_SCRIPTS = 30

LIST_FILTERS = ("divisions", "offices", "roles", "leadership_levels", "saved_jobs",
                "saved_searches", "sub_teams", "teams")
PAGE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}
API_HEADERS = {
    "Accept": "*/*",
    "Origin": "https://www.metacareers.com",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

_doc_id = DOC_ID


def search_input(url: str) -> dict:
    """Return the GraphQL ``search_input`` the search page builds from *url*.

    Lists may be written ``roles[0]=...``, ``roles[]=...`` or ``roles=...``.
    """
    params: Dict[str, List[str]] = {}
    for key, value in parse_qsl(urlsplit(url).query, keep_blank_values=True):
        params.setdefault(re.sub(r"\[[^\]]*\]$", "", key), []).append(value)

    def one(key: str) -> str:
        return (params.get(key) or [""])[0]

    filters = {key: [v for v in params.get(key, []) if v.strip()] for key in LIST_FILTERS}
    return {
        "q": one("q") or None,
        **filters,
        "is_leadership": one("is_leadership") == "1",
        "is_remote_only": one("is_remote_only") == "true",
        "sort_by_new": one("sort_by_new") == "true",
        "results_per_page": None,
    }


def find_doc_id(html: str, session: requests.Session) -> str:
    """Return the current ``doc_id`` of the results query from the page's scripts.

    Raises:
        RuntimeError: If none of the first :data:`MAX_SCRIPTS` scripts defines it.
    """
    for src in SCRIPT.findall(html)[:MAX_SCRIPTS]:
        match = OPERATION.search(get(src.replace("&amp;", "&"), session=session).text)
        if match:
            return match.group(1)
    raise RuntimeError(f"No {QUERY} doc_id in the Meta careers page's scripts")


def _query(session: requests.Session, page_url: str, lsd: str, doc_id: str, variables: dict) -> Optional[dict]:
    """Run the results query; return its data, or None if Meta does not know *doc_id*."""
    response = post(
        GRAPHQL,
        session=session,
        data={
            "lsd": lsd,
            "doc_id": doc_id,
            "fb_api_req_friendly_name": QUERY,
            "variables": json.dumps(variables),
            "server_timestamps": "true",
        },
        headers={**API_HEADERS, "Referer": page_url, "X-FB-LSD": lsd, "X-FB-Friendly-Name": QUERY},
    )
    # Meta may stream more JSON objects after the first, one per line.
    result = json.loads(response.text.split("\n", 1)[0])
    if result.get("data"):
        return result["data"]
    errors = result.get("errors") or [{}]
    message = errors[0].get("message", response.text[:200])
    if "not found" in message.lower():
        return None
    raise RuntimeError(f"Meta careers search failed: {message}")


@adapter("meta")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every posting the Meta careers search in *url* finds."""
    global _doc_id
    session = requests.Session()
    page = get(url, session=session, headers=PAGE_HEADERS)
    match = LSD.search(page.text)
    if not match:
        raise RuntimeError("No LSD token on the Meta careers page")
    lsd = match.group(1)
    variables = {"search_input": search_input(url), "isLoggedIn": False, "viewasUserID": None}
    data = _query(session, page.url, lsd, _doc_id, variables)
    if data is None:
        stale, _doc_id = _doc_id, find_doc_id(page.text, session)
        logger.info("Meta %s doc_id %s is stale; now %s", QUERY, stale, _doc_id)
        data = _query(session, page.url, lsd, _doc_id, variables)
        if data is None:
            raise RuntimeError(f"Meta does not know the {QUERY} doc_id {_doc_id} from its own page")
    jobs = data["job_search_with_featured_jobs"]["all_jobs"] or []
    return [Posting(f"meta:{j['id']}", " ".join(j["title"].split())) for j in jobs]
