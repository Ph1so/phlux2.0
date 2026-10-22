"""Dover career pages (``app.dover.com/jobs/<slug>``).

A board slug first resolves to Dover's client id, whose published jobs then
come back in pages (``count``/``next``). A URL that already carries the client
id (``app.dover.com/<name>/careers/<client id>``) skips the first call.
"""
from __future__ import annotations

import re
from typing import List
from urllib.parse import urlsplit

from ..models import Posting
from .base import adapter, get

SLUG_API = "https://app.dover.com/api/v1/careers-page-slug/{slug}"
JOBS_API = "https://app.dover.com/api/v1/careers-page/{client}/jobs"
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
MAX_PAGES = 50


def client_id(url: str) -> str:
    """Return the Dover client id for a career page URL."""
    parts = [p for p in urlsplit(url).path.split("/") if p]
    for part in parts:
        if UUID.match(part):
            return part
    if len(parts) >= 2 and parts[0] == "jobs":
        return get(SLUG_API.format(slug=parts[1])).json()["id"]
    raise ValueError(f"No Dover career page in {url}")


@adapter("dover")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the published postings on a Dover career page."""
    page_url = JOBS_API.format(client=client_id(url))
    postings: List[Posting] = []
    for _ in range(MAX_PAGES):
        if not page_url:
            break
        data = get(page_url).json()
        postings.extend(
            Posting(f"dover:{j['id']}", j["title"])
            for j in data.get("results", [])
            if j.get("is_published", True) and not j.get("is_sample")
        )
        page_url = data.get("next")
    return postings
