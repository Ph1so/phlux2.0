"""Gem job boards (``jobs.gem.com/<slug>``), read from Gem's public job board API.

Each job post's ``absolute_url`` is its page on the board. Its ``offices``
name where it is ("San Francisco, California", written "San Francisco, CA");
a post with none falls back to its ``location`` ("San Francisco, United States").
"""
from __future__ import annotations

from typing import List

from ..models import Posting
from .base import adapter, get, path_slug, place, tidy_place

API = "https://api.gem.com/job_board/v0/{slug}/job_posts/"


def location(job: dict) -> str:
    """Return a job post's first office and how many more it lists, else its own location."""
    offices = [tidy_place(o.get("name")) for o in job.get("offices") or [] if isinstance(o, dict)]
    return place(None, offices) or tidy_place((job.get("location") or {}).get("name"))


@adapter("gem")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every posting on a Gem board."""
    jobs = get(API.format(slug=path_slug(url))).json()
    return [Posting(f"gem:{j['id']}", j["title"], location(j), j.get("absolute_url") or "") for j in jobs]
