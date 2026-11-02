"""Kula career boards (``careers.kula.ai/<account>``).

The board page is built from Kula's ``/api/internal/ats_job_posts`` endpoint,
which pages with ``meta.pages``. Unlisted and internal-only posts are skipped,
as the board does. A post's page is ``careers.kula.ai/<account>/<id>-<title
slug>``; the id alone redirects there, and stays the same if the title changes.
Its job's ``offices`` (city, state, country) say where it is: "Austin, TX",
"Vancouver, Canada".
"""
from __future__ import annotations

from typing import List

from ..models import Posting
from .base import adapter, format_place, get, path_slug, place, unique

API = "https://careers.kula.ai/api/internal/ats_job_posts"
JOB_PAGE = "https://careers.kula.ai/{account}/{id}"
PAGE_SIZE = 99
MAX_PAGES = 50


def location(post: dict) -> str:
    """Return a post's first office and how many more it lists ("Remote" for a remote office with no city)."""
    names = []
    for office in (post.get("ats_job") or {}).get("offices") or []:
        if not isinstance(office, dict):
            continue
        country = office.get("country") or office.get("country_code")
        name = format_place(office.get("city"), office.get("state"), country)
        if office.get("remote") and not office.get("city"):
            name = f"Remote, {name}" if name else "Remote"
        names.append(name or office.get("location") or office.get("name"))
    return place(None, names)


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
            Posting(f"kula:{j['id']}", j["title"], location(j), JOB_PAGE.format(account=account, id=j["id"]))
            for j in data.get("data") or []
            if j.get("listed", True) and j.get("kind") != "internal"
        )
        page += 1
    return unique(postings)
