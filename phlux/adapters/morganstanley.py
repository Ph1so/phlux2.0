"""Read Morgan Stanley's career search (``morganstanley.com/careers``) from the JSON behind it.

A row's Link is the search page a person opens, e.g.
``https://www.morganstanley.com/careers/career-opportunities-search?opportunity=sg``
(``sg`` for students & graduates, ``ep`` for experienced professionals).
That page asks
``GET /web/career_services/webapp/service/careerservice/resultset.json?opportunity=sg&lang=en``
for the whole list at once (``resultSet``, with ``totalResults``); this module
sends the URL's ``opportunity`` and ``lang`` the same way.

A job's ``jobNumber`` is the stable key, and its ``url`` (the posting on
Morgan Stanley's recruiting system, ``morganstanley.tal.net/…/opp/<number>``) is
the job's page. Its ``city``, ``allState`` and ``country`` are where it is
("New York, NY", "Budapest, Hungary").
"""
from __future__ import annotations

import logging
from typing import List

from ..models import Posting
from .base import adapter, first, format_place, get, query, title_id, unique

logger = logging.getLogger(__name__)

NAME = "morganstanley"
API = "https://www.morganstanley.com/web/career_services/webapp/service/careerservice/resultset.json"


def location(job: dict) -> str:
    """Return where *job* is; ``allState`` names its state when it has one location."""
    state = str(job.get("allState") or "")
    if any(sep in state for sep in (",", ";", "|")):
        state = ""
    return format_place(job.get("city") or job.get("level3"), state, job.get("country"))


def to_posting(job: dict) -> Posting:
    title = " ".join(str(job.get("jobTitle") or "").split())
    key = str(job.get("jobNumber") or "").strip()
    url = str(job.get("url") or "").strip()
    return Posting(f"{NAME}:{key}" if key else title_id(NAME, title), title, location(job),
                   url if url.startswith("http") else "")


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every opportunity a Morgan Stanley search URL shows."""
    params = query(url)
    sent = {"opportunity": first(params, "opportunity", "sg"), "lang": first(params, "lang", "en")}
    answer = get(API, params=sent, headers={"Accept": "application/json", "Referer": url}).json()
    if not isinstance(answer, dict) or not isinstance(answer.get("resultSet"), list):
        raise ValueError(f"Unexpected answer from {API}: {str(answer)[:200]}")
    jobs = answer["resultSet"]
    total = answer.get("totalResults")
    if isinstance(total, int) and total != len(jobs):
        logger.warning("%s lists %d opportunities but sent %d", url, total, len(jobs))
    return unique(to_posting(j) for j in jobs if isinstance(j, dict) and j.get("jobTitle"))
