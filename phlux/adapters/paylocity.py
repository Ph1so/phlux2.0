"""Paylocity recruiting boards (``recruiting.paylocity.com/recruiting/jobs/All/<guid>/<name>``).

The board's public JSON feed is off for most companies, but the board page
itself is server-rendered with every job in a ``window.pageData = {...}``
script, which is read here. The page links each job to
``/Recruiting/Jobs/Details/<JobId>``. A job's ``JobLocation`` has its city,
state and country ("Philadelphia, PA"); a remote job without a city is
"Remote", and one whose board hides its location (``ShouldDisplayLocation``)
has none.
"""
from __future__ import annotations

import json
import re
from typing import List

from ..models import Posting
from .base import adapter, format_place, get

PAGE_DATA = re.compile(r"window\.pageData\s*=\s*")
JOB_PAGE = "https://recruiting.paylocity.com/Recruiting/Jobs/Details/{id}"


def page_data(html: str) -> dict:
    """Return the ``window.pageData`` object embedded in a board page."""
    match = PAGE_DATA.search(html)
    if not match:
        raise ValueError("No window.pageData in Paylocity page")
    data, _ = json.JSONDecoder().raw_decode(html, match.end())
    return data


def location(job: dict) -> str:
    """Return a job's location as its board shows it."""
    fields = job.get("JobLocation") or {}
    shown = job.get("ShouldDisplayLocation", True)
    found = format_place(fields.get("City"), fields.get("State"), fields.get("Country")) if shown else ""
    if job.get("IsRemote") and not (shown and fields.get("City")):
        return "Remote"
    return found


@adapter("paylocity")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every posting on a Paylocity board page."""
    jobs = page_data(get(url).text).get("Jobs") or []
    return [Posting(f"paylocity:{j['JobId']}", j["JobTitle"], location(j), JOB_PAGE.format(id=j["JobId"]))
            for j in jobs]
