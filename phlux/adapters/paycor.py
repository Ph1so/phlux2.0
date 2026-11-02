"""Paycor recruiting boards (``recruitingbypaycor.com/career/CareerHome.action?clientId=...``).

The board is server-rendered: each job links to ``JobIntroduction.action``
with the job's ``id``. Its search form submits as a GET
(``CareerHomeSearch.action?clientId=...&keyword=...&departmentId=...``), so a
filtered board URL is fetched as it is and read with its filters. That link,
kept to its ``clientId`` and ``id`` (it also carries the board's display and
source parameters), is the job's page.
"""
from __future__ import annotations

from typing import List
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit

from ..models import Posting
from .base import adapter, first, get, query, soup, text, unique


# The parameters of a job link that pick the job; the rest only steer the display.
JOB_PARAMS = ("clientId", "id")


def job_page(job_url: str) -> str:
    """Return a job link with only the parameters that pick the job (as is without an ``id``)."""
    parts = urlsplit(job_url)
    params = query(job_url)
    if not first(params, "id"):
        return job_url
    kept = [(key, first(params, key)) for key in JOB_PARAMS if first(params, key)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), ""))


@adapter("paycor")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the postings listed on a Paycor board page."""
    postings = []
    for link in soup(get(url).text).select("a[href*='JobIntroduction.action']"):
        job_url = urljoin(url, link["href"])
        job_id = first(query(job_url), "id") or job_url
        title = text(link)
        if title:
            postings.append(Posting(f"paycor:{job_id}", title, url=job_page(job_url)))
    return unique(postings)
