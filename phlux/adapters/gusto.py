"""Gusto recruiting boards (``jobs.gusto.com/boards/<company>-<uuid>``).

The board is server-rendered; each job links to ``/postings/<title-slug>-<uuid>``,
and that uuid is the job's id. The site sits behind Cloudflare, which has at
times answered scripted requests with a challenge page (a 403, raised here).
"""
from __future__ import annotations

import re
from typing import List
from urllib.parse import urljoin, urlsplit

from ..models import Posting
from .base import adapter, get, soup, text, unique

POSTING_ID = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/?$", re.I)
HTML = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}


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
            postings.append(Posting(f"gusto:{match.group(1) if match else job_url}", title))
    return unique(postings)
