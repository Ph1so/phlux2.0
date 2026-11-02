"""Gusto recruiting boards (``jobs.gusto.com/boards/<company>-<uuid>``).

The board is server-rendered; each job links to ``/postings/<title-slug>-<uuid>``,
and that uuid is the job's id; the link is the job's page. The site sits
behind Cloudflare, which has at times answered scripted requests with a
challenge page (a 403, raised here).

Inside the link, the line marked with a map pin lists the job's locations,
one per line ("Fremont, CA", "Remote").
"""
from __future__ import annotations

import re
from typing import List
from urllib.parse import urljoin, urlsplit

from ..models import Posting
from .base import adapter, bare_url, get, place, soup, text, tidy_place, unique

POSTING_ID = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/?$", re.I)
HTML = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
# The map pin icon (Heroicons' location marker) drawn before a job's locations.
PIN = "path[d^='M17.657 16.657']"


def location(link) -> str:
    """Return the first location listed beside a job link's map pin, and how many more."""
    pin = link.select_one(PIN)
    line = pin.find_parent("p") if pin is not None else None
    if line is None:
        return ""
    return place(None, [tidy_place(name) for name in line.get_text("\n").split("\n")])


@adapter("gusto")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the postings listed on a Gusto board page."""
    postings = []
    for link in soup(get(url, headers=HTML).text).select("a[href*='/postings/']"):
        job_url = urljoin(url, link["href"])
        match = POSTING_ID.search(urlsplit(job_url).path)
        heading = link.select_one("h1, h2, h3, h4")
        title = text(heading or link)
        if title:
            postings.append(Posting(f"gusto:{match.group(1) if match else job_url}", title, location(link),
                                    bare_url(job_url)))
    return unique(postings)
