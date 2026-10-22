"""Gem job boards (``jobs.gem.com/<slug>``), read from Gem's public job board API."""
from __future__ import annotations

from typing import List

from ..models import Posting
from .base import adapter, get, path_slug

API = "https://api.gem.com/job_board/v0/{slug}/job_posts/"


@adapter("gem")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every posting on a Gem board."""
    jobs = get(API.format(slug=path_slug(url))).json()
    return [Posting(f"gem:{j['id']}", j["title"]) for j in jobs]
