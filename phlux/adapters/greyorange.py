"""GreyOrange careers (``greyorange.com/company/careers/``).

The careers page loads its openings ten at a time from WordPress's
``admin-ajax.php`` (``action=go_fetch_jobs&page=N``), which answers JSON with
the jobs, ``totalCount`` and ``pageSize``. Every page is read; the browser only
showed the first. Postings are keyed by the job id of GreyOrange's ATS.
"""
from __future__ import annotations

import math
from typing import List

from ..models import Posting
from .base import adapter, post, unique

API = "https://www.greyorange.com/wp-admin/admin-ajax.php"
MAX_PAGES = 30


def _page(page: int) -> dict:
    result = post(API, data={"action": "go_fetch_jobs", "page": page}).json()
    if not result.get("success"):
        raise RuntimeError(f"GreyOrange jobs request failed: {str(result)[:200]}")
    return result["data"]


def _postings(data: dict) -> List[Posting]:
    return [Posting(f"greyorange:{j['id']}", " ".join(j["jobTitle"].split())) for j in data.get("jobs") or []]


@adapter("greyorange")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every opening on GreyOrange's careers page."""
    first = _page(1)
    postings = _postings(first)
    size = int(first.get("pageSize") or 0) or len(postings) or 1
    pages = math.ceil(int(first.get("totalCount") or 0) / size)
    if pages > MAX_PAGES:
        raise RuntimeError(f"GreyOrange lists {first['totalCount']} jobs ({pages} pages); expected far fewer")
    for page in range(2, pages + 1):
        postings += _postings(_page(page))
    return unique(postings)
