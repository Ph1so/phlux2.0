"""JazzHR boards (``<slug>.applytojob.com``).

JazzHR has no public JSON without an API key, but its boards are
server-rendered: each job links to ``/apply/<code>/<title-slug>``, and the code
is the job's id; that link is the job's page. The row's URL is fetched as it
is, so a board URL carrying JazzHR's own filters is read with them. Under each
title, the line with a map marker (``i.fa-map-marker``) is the job's location.
"""
from __future__ import annotations

import re
from typing import List
from urllib.parse import urljoin

from ..models import Posting
from .base import adapter, bare_url, get, soup, text, tidy_place, unique

JOB_LINK = re.compile(r"/apply/([A-Za-z0-9]+)/[^/?#]+")


def location(link) -> str:
    """Return the location under a job link, from the line marked with a map marker."""
    item = link.find_parent("li")
    marker = item.select_one(".fa-map-marker") if item is not None else None
    line = marker.find_parent("li") if marker is not None else None
    return tidy_place(text(line)) if line is not None and line is not item else ""


@adapter("jazzhr")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the postings listed on a JazzHR board page."""
    postings = []
    for link in soup(get(url).text).select("a[href*='/apply/']"):
        job_url = urljoin(url, link["href"])
        match = JOB_LINK.search(job_url)
        title = text(link)
        if match and title:
            postings.append(Posting(f"jazzhr:{match.group(1)}", title, location(link), bare_url(job_url)))
    return unique(postings)
