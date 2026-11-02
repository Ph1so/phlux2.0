"""D. E. Shaw internships (``deshaw.com/careers/internships``).

The page is a server-rendered Next.js page: its ``__NEXT_DATA__`` script holds
every listed internship under ``props.pageProps.internships`` (all of them,
including the ones the browser only shows after "more jobs" is clicked).
Postings are keyed by D. E. Shaw's job id, the number ending the job's URL.
That URL is ``/careers/<data.jobUrl>``, lowercased as the page links it.
An internship's ``office`` names where it is ("New York"); US offices get
their state (:data:`US_OFFICES`).
"""
from __future__ import annotations

import json
import re
from typing import List
from urllib.parse import quote, urljoin

from ..models import Posting
from .base import adapter, get, place

NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
# The firm's US offices, by the name the page gives them, as "City, ST".
US_OFFICES = {"New York": "New York, NY"}


def internships(html: str) -> List[dict]:
    """Return the internships listed in an internships page's ``__NEXT_DATA__``.

    Raises:
        RuntimeError: If the page has no internship data, or says its job
            feed failed (it then renders an empty list).
    """
    match = NEXT_DATA.search(html)
    if not match:
        raise RuntimeError("No __NEXT_DATA__ on the D. E. Shaw internships page")
    props = json.loads(match.group(1))["props"]["pageProps"]
    if props.get("jobsFetchingError") or "internships" not in props:
        raise RuntimeError("The D. E. Shaw internships page could not load its jobs")
    return props["internships"] or []


def job_url(url: str, job: dict) -> str:
    """Return an internship's page on the site of *url*, or "" if it names none."""
    slug = (job.get("data") or {}).get("jobUrl")
    return urljoin(url, "/careers/" + quote(slug.lower())) if slug else ""


def location(job: dict) -> str:
    """Return where an internship is, from its ``office`` (or its data's ``jobLocations``)."""
    offices = job.get("office") or ((job.get("data") or {}).get("jobMetadata") or {}).get("jobLocations") or []
    names = [" ".join(str(o.get("name") or "").split()) for o in offices if isinstance(o, dict)]
    return place(None, [US_OFFICES.get(n, n) for n in names])


@adapter("deshaw")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every internship on the D. E. Shaw internships page."""
    return [Posting(f"deshaw:{job['id']}", " ".join(job["displayName"].split()), location(job), job_url(url, job))
            for job in internships(get(url).text)]
