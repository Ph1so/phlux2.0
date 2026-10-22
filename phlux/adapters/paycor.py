"""Paycor recruiting boards (``recruitingbypaycor.com/career/CareerHome.action?clientId=...``).

The board is server-rendered: each job links to ``JobIntroduction.action``
with the job's ``id``. Its search form submits as a GET
(``CareerHomeSearch.action?clientId=...&keyword=...&departmentId=...``), so a
filtered board URL is fetched as it is and read with its filters.
"""
from __future__ import annotations

from typing import List
from urllib.parse import urljoin

from ..models import Posting
from .base import adapter, first, get, query, soup, text, unique


@adapter("paycor")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the postings listed on a Paycor board page."""
    postings = []
    for link in soup(get(url).text).select("a[href*='JobIntroduction.action']"):
        job_url = urljoin(url, link["href"])
        job_id = first(query(job_url), "id") or job_url
        title = text(link)
        if title:
            postings.append(Posting(f"paycor:{job_id}", title))
    return unique(postings)
