"""Kula career boards (``careers.kula.ai/<account>``).

The board page is built from Kula's ``/api/internal/ats_job_posts`` endpoint,
which pages with ``meta.pages``. Unlisted and internal-only posts are skipped,
as the board does.
"""
from __future__ import annotations

from typing import List

from ..models import Posting
from .base import adapter, get, path_slug, unique

API = "https://careers.kula.ai/api/internal/ats_job_posts"
PAGE_SIZE = 99
MAX_PAGES = 50


@adapter("kula")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the listed postings on a Kula board."""
    account = path_slug(url)
    postings: List[Posting] = []
    page, pages = 1, 1
    while page <= min(pages, MAX_PAGES):
        data = get(API, params={
            "accountName": account,
            "type": "ats_job_post.index",
            "items": PAGE_SIZE,
            "page": page,
        }).json()
        pages = (data.get("meta") or {}).get("pages") or 1
        postings.extend(
            Posting(f"kula:{j['id']}", j["title"])
            for j in data.get("data") or []
            if j.get("listed", True) and j.get("kind") != "internal"
        )
        page += 1
    return unique(postings)
