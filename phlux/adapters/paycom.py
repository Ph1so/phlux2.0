"""Paycom career portals (``www.paycomonline.net/v4/ats/web.php/portal/<key>/career-page``).

The portal page carries a short-lived session token (``configsFromHost.sessionJWT``)
and names its API host; the job list is then a POST to that host's
``/api/ats/job-posting-previews/search``, paged with ``skip``/``take``.
"""
from __future__ import annotations

import json
import re
from typing import List

from ..models import Posting
from .base import adapter, get, post

CONFIG = re.compile(r"configsFromHost\s*=\s*")
API_HOST = re.compile(r"https://portal-applicant-tracking\.[a-z0-9.-]+\.paycomonline\.net")
DEFAULT_API_HOST = "https://portal-applicant-tracking.us-cent.paycomonline.net"
SEARCH_PATH = "/api/ats/job-posting-previews/search"
PAGE_SIZE = 100
MAX_PAGES = 20
NO_FILTERS = {
    "distanceFrom": 0, "workEnvironments": [], "positionTypes": [], "educationLevels": [],
    "categories": [], "travelTypes": [], "shiftTypes": [], "otherFilters": [],
    "keywordSearchText": "", "location": "", "sortOption": "",
}


def session(html: str) -> tuple:
    """Return ``(jwt, api_host)`` from a career portal page."""
    match = CONFIG.search(html)
    if not match:
        raise ValueError("No configsFromHost in Paycom portal page")
    config, _ = json.JSONDecoder().raw_decode(html, match.end())
    host = API_HOST.search(html)
    return config["sessionJWT"], host.group(0) if host else DEFAULT_API_HOST


@adapter("paycom")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every posting on a Paycom career portal."""
    jwt, host = session(get(url).text)
    headers = {"Authorization": jwt, "Portal-Host-Referrer": url}
    postings: List[Posting] = []
    for page in range(MAX_PAGES):
        data = post(host + SEARCH_PATH, headers=headers, json={
            "skip": page * PAGE_SIZE, "take": PAGE_SIZE, "filtersForQuery": NO_FILTERS,
        }).json()
        jobs = data.get("jobPostingPreviews") or []
        postings.extend(Posting(f"paycom:{j['jobId']}", j["jobTitle"]) for j in jobs)
        if not jobs or len(postings) >= (data.get("jobPostingPreviewsCount") or 0):
            break
    return postings
