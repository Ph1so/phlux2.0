"""Atlassian's careers site (``atlassian.com/company/careers/all-jobs``).

Atlassian hires through several iCIMS portals whose own searches are switched
off (they send a visitor back to this page), so the page is the one list of
every job. It is rendered on the server with all jobs embedded as JSON (the
``careersGallery`` component's data, each with ``id``, ``title``, ``category``
and ``locations``), so one request reads the whole site.

The page's filters are read from the row's URL the same way the page applies
them: ``team`` must equal a job's ``category`` ("Interns", "Graduates"…),
``location`` must appear in one of its locations ("United States"), and
``search`` must appear in its title (all ignoring case). A job's page is
``atlassian.com/company/careers/details/<id>``.

A location such as "San Francisco - United States -   San Francisco,
California 94104 United States" is written "San Francisco, CA", "London -
United Kingdom -   London,  EC1V United Kingdom" "London, United Kingdom", and
"Remote - Remote" or "Remote - UK - Remote" "Remote"; a job with several is
"San Francisco, CA +1".
"""
from __future__ import annotations

import json
import re
from typing import List

from ..models import Posting
from .base import adapter, first, format_place, get, is_us, place, query, us_state

NAME = "atlassian"
JOB_PAGE = "https://www.atlassian.com/company/careers/details/{id}"
GALLERY = re.compile(r'"careersGallery"\s*,\s*"parameters"\s*:\s*\{\s*"data"\s*:\s*\{[^{}]*?"value"\s*:\s*(?=\[)')
# A US ZIP code after the state: "California 94104".
POSTCODE = re.compile(r"\s*\b\d{5}(?:-\d{4})?\s*$")


def gallery(html: str) -> List[dict]:
    """Return the jobs embedded in the careers page *html*.

    Raises:
        ValueError: If the page no longer holds the jobs gallery.
    """
    found = GALLERY.search(html)
    if not found:
        raise ValueError("No careersGallery data on the Atlassian careers page")
    jobs, _ = json.JSONDecoder().raw_decode(html, found.end())
    return [j.get("fields") or {} for j in jobs if isinstance(j, dict)]


def _one(text: str) -> str:
    """Return one of the site's location strings written the way a person would."""
    parts = [p for p in (" ".join(p.split()) for p in text.split(" - ")) if p]
    if not parts:
        return ""
    if parts[0].casefold() == "remote":
        return "Remote"
    label = parts[0]
    # "United States or Remote" names the country first.
    country = re.split(r"\s+or\s+", parts[1])[0] if len(parts) > 1 else ""
    region = ""
    if len(parts) > 2 and is_us(country):
        # "San Francisco, California 94104 United States": the state is after the town.
        rest = parts[2].partition(",")[2].strip()
        if rest.casefold().endswith(country.casefold()):
            rest = rest[: -len(country)]
        states = [us_state(POSTCODE.sub("", s).strip()) for s in rest.split(",")]
        region = next((s for s in reversed(states) if s), "")
        # "Washington DC" in DC is Washington.
        if region and label.upper().endswith(" " + region):
            label = label[: -len(region) - 1]
    if label.casefold() == country.casefold():
        label = ""
    return format_place(label, region, country)


def location(job: dict) -> str:
    """Return a job's location, plus a count of its other locations."""
    names = [_one(text) for text in job.get("locations") or [] if isinstance(text, str)]
    return place(names[0] if names else "", names[1:])


def matches(job: dict, team: str, where: str, search: str) -> bool:
    """Return True if *job* passes the page's filters, as the page applies them."""
    if team and (job.get("category") or "").casefold() != team.casefold():
        return False
    if where and not any(where.casefold() in (text or "").casefold() for text in job.get("locations") or []):
        return False
    return not search or search.casefold() in (job.get("title") or "").casefold()


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the jobs the Atlassian careers URL shows, filtered by its query."""
    params = query(url)
    team, where, search = first(params, "team"), first(params, "location"), first(params, "search")
    jobs = gallery(get(url).text)
    return [
        Posting(f"{NAME}:{j['id']}", " ".join(j["title"].split()), location(j), JOB_PAGE.format(id=j["id"]))
        for j in jobs
        if j.get("id") and j.get("title") and matches(j, team, where, search)
    ]
