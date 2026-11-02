"""BambooHR career boards (``<slug>.bamboohr.com/careers``).

The board page lists every opening from ``/careers/list`` as JSON in one
request. A company that leaves BambooHR keeps its subdomain, but it redirects
to BambooHR's marketing site; that is reported as an error rather than read as
an empty board. An opening's page is ``<slug>.bamboohr.com/careers/<id>``.

An opening's ``location`` (city and state) is written "San Antonio, TX"; its
``atsLocation`` adds a country, and an opening with neither is "Remote" when
``isRemote`` says so.
"""
from __future__ import annotations

from typing import List
from urllib.parse import urlsplit

from ..models import Posting
from .base import adapter, format_place, get

API = "https://{slug}.bamboohr.com/careers/list"
JOB_PAGE = "https://{slug}.bamboohr.com/careers/{id}"


def board_slug(url: str) -> str:
    """Return the company subdomain of a ``<slug>.bamboohr.com`` URL."""
    host = urlsplit(url).netloc.lower()
    if not host.endswith(".bamboohr.com"):
        raise ValueError(f"Not a BambooHR board: {url}")
    return host.split(".")[0]


def location(job: dict) -> str:
    """Return an opening's location: its city and state, or "Remote" for a remote one with neither."""
    for fields in (job.get("location"), job.get("atsLocation")):
        fields = fields or {}
        found = format_place(fields.get("city"), fields.get("state") or fields.get("province"), fields.get("country"))
        if found:
            return found
    return "Remote" if job.get("isRemote") else ""


@adapter("bamboohr")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every posting on a BambooHR board."""
    slug = board_slug(url)
    response = get(API.format(slug=slug), allow_redirects=False)
    if response.is_redirect:
        raise RuntimeError(
            f"BambooHR board {slug!r} is gone (redirects to {response.headers.get('location')})"
        )
    jobs = response.json().get("result", [])
    return [Posting(f"bamboohr:{j['id']}", j["jobOpeningName"], location(j), JOB_PAGE.format(slug=slug, id=j["id"]))
            for j in jobs]
