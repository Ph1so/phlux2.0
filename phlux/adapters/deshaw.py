"""D. E. Shaw internships (``deshaw.com/careers/internships``).

The page is a server-rendered Next.js page: its ``__NEXT_DATA__`` script holds
every listed internship under ``props.pageProps.internships`` (all of them,
including the ones the browser only shows after "more jobs" is clicked).
Postings are keyed by D. E. Shaw's job id, the number ending the job's URL.
"""
from __future__ import annotations

import json
import re
from typing import List

from ..models import Posting
from .base import adapter, get

NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)


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


@adapter("deshaw")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every internship on the D. E. Shaw internships page."""
    return [Posting(f"deshaw:{job['id']}", " ".join(job["displayName"].split()))
            for job in internships(get(url).text)]
