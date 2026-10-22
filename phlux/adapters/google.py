"""Google Careers search results (``google.com/about/careers/applications/jobs/results``).

Used for Google and for DeepMind (``?company=DeepMind``). The results page is
server-rendered: an ``AF_initDataCallback`` call with key ``ds:1`` carries the
page's jobs as JSON, ``[[job, ...], null, total, page_size]``, where each job
starts ``[id, title, ...]``. Every filter in the link (``category``, ``location``,
``employment_type``, ``company``...) is the page's own, so the link is fetched
as is, adding ``page=N`` for each page of 20. A ``page`` already in the link is
ignored: every page is read.
"""
from __future__ import annotations

import json
import math
import re
from typing import List, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..models import Posting
from .base import adapter, get, unique

DATA = re.compile(r"AF_initDataCallback\(\{key: 'ds:1', hash: '\d+', data:")
# 50 pages of 20 is a thousand jobs; a scope that wide is not a filtered one.
MAX_PAGES = 50


def page_url(url: str, page: int) -> str:
    """Return *url* asking for results page *page* (1-based), other filters kept."""
    parts = urlsplit(url)
    params = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "page"]
    params.append(("page", str(page)))
    return urlunsplit(parts._replace(query=urlencode(params)))


def parse(html: str) -> Tuple[List[Posting], int, int]:
    """Return ``(postings, total, page_size)`` from a results page.

    Raises:
        ValueError: If the page carries no ``ds:1`` job data.
    """
    match = DATA.search(html)
    if not match:
        raise ValueError("No job data (ds:1) on the Google Careers page")
    data, _ = json.JSONDecoder().raw_decode(html, match.end())
    jobs, total, size = data[0] or [], data[-2] or 0, data[-1] or 20
    postings = [Posting(f"google:{job[0]}", " ".join(job[1].split())) for job in jobs]
    return postings, total, size


@adapter("google")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every posting the Google Careers search in *url* finds."""
    postings, total, size = parse(get(page_url(url, 1)).text)
    pages = math.ceil(total / size)
    if pages > MAX_PAGES:
        raise RuntimeError(f"Google Careers search finds {total} jobs ({pages} pages); narrow {url}")
    for page in range(2, pages + 1):
        postings += parse(get(page_url(url, page)).text)[0]
    return unique(postings)
