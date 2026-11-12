"""Teamtailor career sites (``<slug>.teamtailor.com/jobs`` or a company's own domain).

Every Teamtailor site publishes its open jobs as a JSON Feed at ``/jobs.json``
on the site's host, one request for the whole site. Each item carries the job's
page ``url`` (``/jobs/<id>-<title-slug>``) and a schema.org ``_jobposting`` whose
``identifier`` is the job's numeric id, the stable key here (the same number
starts the page's path).

A job's ``jobLocation`` addresses give city, region and country code; one is
written "Hamburg, Germany" or "Austin, TX", followed by a count of the job's
other locations, and a remote job naming no city is "Remote". The feed takes no
filters, so a site URL with a query (department, location…) is refused rather
than read as the whole site.
"""
from __future__ import annotations

import re
from typing import List
from urllib.parse import urlsplit, urlunsplit

from ..early_career import html_text
from ..models import Posting
from .base import adapter, country_name, format_place, get, is_us, place, us_state

NAME = "teamtailor"
FEED_PATH = "/jobs.json"
# A job page's path: /jobs/8447974-robot-technician (some sites add a locale first).
JOB_ID = re.compile(r"/jobs/(\d+)")


def feed_url(url: str) -> str:
    """Return the JSON Feed of the Teamtailor site *url* is on."""
    parts = urlsplit(url)
    if not parts.netloc:
        raise ValueError(f"Not a Teamtailor site URL: {url}")
    if parts.query:
        raise ValueError(f"Teamtailor site filters are not supported: {url}")
    return urlunsplit((parts.scheme or "https", parts.netloc, FEED_PATH, "", ""))


def job_id(item: dict) -> str:
    """Return a feed item's job id: its posting's identifier, else the number in its page's path."""
    identifier = (item.get("_jobposting") or {}).get("identifier") or {}
    value = str(identifier.get("value") or "").strip() if isinstance(identifier, dict) else ""
    if value:
        return value
    found = JOB_ID.search(urlsplit(item.get("url") or "").path)
    return found.group(1) if found else str(item["id"])


def _place(address) -> str:
    if not isinstance(address, dict):
        return ""
    city, region, country = address.get("addressLocality"), address.get("addressRegion"), address.get("addressCountry")
    code = " ".join(str(country or "").split())
    # Teamtailor often fills the region with the country's name ("Germany" for DE).
    if region and (is_us(region) or region.strip().casefold() == country_name(code).casefold()):
        region = ""
    # A country code base.COUNTRIES lacks ("EE") is named by that region ("Estonia").
    elif region and not us_state(region) and len(code) in (2, 3) and country_name(code) == code:
        country, region = region, ""
    return format_place(city, region, country)


def location(posting: dict) -> str:
    """Return a job's location, plus a count of its other locations."""
    where = posting.get("jobLocation") or []
    if isinstance(where, dict):
        where = [where]
    names = [_place(spot.get("address")) for spot in where if isinstance(spot, dict)]
    found = place(names[0] if names else "", names[1:])
    if posting.get("jobLocationType") == "TELECOMMUTE" and not any(
            isinstance(spot, dict) and (spot.get("address") or {}).get("addressLocality") for spot in where):
        return "Remote"
    return found


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every job on a Teamtailor career site."""
    items = get(feed_url(url)).json().get("items") or []
    postings = []
    for item in items:
        posting = item.get("_jobposting") or {}
        title = item.get("title") or posting.get("title") or ""
        postings.append(Posting(
            f"{NAME}:{job_id(item)}", " ".join(title.split()), location(posting), item.get("url") or "",
            html_text(item.get("content_html") or posting.get("description")),
        ))
    return postings
