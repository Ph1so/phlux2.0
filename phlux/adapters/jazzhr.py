"""JazzHR boards (``<slug>.applytojob.com``).

JazzHR has no public JSON without an API key, but its boards are
server-rendered: each job links to ``/apply/<code>/<title-slug>``, and the code
is the job's id. The row's URL is fetched as it is, so a board URL carrying
JazzHR's own filters is read with them.
"""
from __future__ import annotations

import re
from typing import List
from urllib.parse import urljoin

from ..models import Posting
from .base import adapter, get, soup, text, unique

JOB_LINK = re.compile(r"/apply/([A-Za-z0-9]+)/[^/?#]+")


@adapter("jazzhr")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the postings listed on a JazzHR board page."""
    postings = []
    for link in soup(get(url).text).select("a[href*='/apply/']"):
        match = JOB_LINK.search(urljoin(url, link["href"]))
        title = text(link)
        if match and title:
            postings.append(Posting(f"jazzhr:{match.group(1)}", title))
    return unique(postings)
