"""Dover career pages (``app.dover.com/jobs/<slug>``).

A board slug first resolves to Dover's client id, whose published jobs then
come back in pages (``count``/``next``). A URL that already carries the client
id (``app.dover.com/<name>/careers/<client id>``) skips the first call.

The board links each job to ``app.dover.com/apply/<client name>/<job id>/``
(plus a ``rs`` source parameter, left out here). That page reads the job by
its id alone; the name only makes the link readable.

A job's ``locations`` each have the ``name`` the board shows ("San Francisco,
CA"); the one marked ``is_primary`` comes first.
"""
from __future__ import annotations

import re
from typing import List, Tuple
from urllib.parse import quote, unquote, urlsplit

from ..models import Posting
from .base import adapter, get, place, tidy_place

SLUG_API = "https://app.dover.com/api/v1/careers-page-slug/{slug}"
JOBS_API = "https://app.dover.com/api/v1/careers-page/{client}/jobs"
JOB_PAGE = "https://app.dover.com/apply/{name}/{id}/"
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
MAX_PAGES = 50


def client(url: str) -> Tuple[str, str]:
    """Return the Dover client id and name for a career page URL.

    The name is empty when the URL carries the id but not the name before it.
    """
    parts = [unquote(p) for p in urlsplit(url).path.split("/") if p]
    for i, part in enumerate(parts):
        if UUID.match(part):
            named = i >= 2 and parts[i - 1] == "careers"
            return part, parts[i - 2] if named else ""
    if len(parts) >= 2 and parts[0] == "jobs":
        data = get(SLUG_API.format(slug=parts[1])).json()
        return data["id"], data.get("name") or ""
    raise ValueError(f"No Dover career page in {url}")


def client_id(url: str) -> str:
    """Return the Dover client id for a career page URL."""
    return client(url)[0]


def job_url(name: str, job_id: str) -> str:
    """Return a job's application page, or "" without the client's name to put in it."""
    return JOB_PAGE.format(name=quote(name, safe=""), id=quote(str(job_id), safe="")) if name else ""


def location(job: dict) -> str:
    """Return a job's primary location and how many more it lists."""
    locations = [loc for loc in job.get("locations") or [] if isinstance(loc, dict)]
    locations.sort(key=lambda loc: not loc.get("is_primary"))
    names = [loc.get("name") or (loc.get("location_option") or {}).get("display_name") for loc in locations]
    return place(None, [tidy_place(n) for n in names])


@adapter("dover")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the published postings on a Dover career page."""
    client_key, name = client(url)
    page_url = JOBS_API.format(client=client_key)
    postings: List[Posting] = []
    for _ in range(MAX_PAGES):
        if not page_url:
            break
        data = get(page_url).json()
        postings.extend(
            Posting(f"dover:{j['id']}", j["title"], location(j), job_url(name, j["id"]))
            for j in data.get("results", [])
            if j.get("is_published", True) and not j.get("is_sample")
        )
        page_url = data.get("next")
    return postings
