"""Breezy HR career portals (``<slug>.breezy.hr``).

The portal lists every published position as JSON at ``<slug>.breezy.hr/json``
in one request: id, title (``name``), page ``url``, employment ``type`` and
``location``/``locations``. A position's page is
``<slug>.breezy.hr/p/<id>-<title-slug>``, the ``url`` it gives; a slug that has
no portal answers 404, which is reported as an error.

A location (city, state, country) is written "New York, NY", followed by a
count of the position's other ``locations``; a remote one naming no city is
"Remote". The JSON takes no filters, so a portal URL with a query is refused
rather than read as the whole portal.
"""
from __future__ import annotations

from typing import List
from urllib.parse import urlsplit

from ..models import Posting
from .base import adapter, format_place, get, place

NAME = "breezy"
API = "https://{slug}.breezy.hr/json"
JOB_PAGE = "https://{slug}.breezy.hr/p/{friendly_id}"


def portal_slug(url: str) -> str:
    """Return the company subdomain of a ``<slug>.breezy.hr`` URL."""
    parts = urlsplit(url)
    host = parts.netloc.lower()
    if not host.endswith(".breezy.hr"):
        raise ValueError(f"Not a Breezy HR portal: {url}")
    if parts.query:
        raise ValueError(f"Breezy HR portal filters are not supported: {url}")
    return host.split(".")[0]


def _place(loc) -> str:
    if not isinstance(loc, dict):
        return ""
    state = loc.get("state") or {}
    country = loc.get("country") or {}
    if loc.get("is_remote") and not loc.get("city"):
        return "Remote"
    return format_place(loc.get("city"), state.get("name") or state.get("id"),
                        country.get("id") or country.get("name"))


def location(job: dict) -> str:
    """Return a position's location, plus a count of its other locations."""
    primary = job.get("location")
    others = [_place(loc) for loc in job.get("locations") or [] if loc != primary]
    return place(_place(primary), others)


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every position on a Breezy HR portal."""
    slug = portal_slug(url)
    jobs = get(API.format(slug=slug)).json()
    return [
        Posting(f"{NAME}:{j['id']}", " ".join(j["name"].split()), location(j),
                j.get("url") or JOB_PAGE.format(slug=slug, friendly_id=j.get("friendly_id") or j["id"]))
        for j in jobs
    ]
