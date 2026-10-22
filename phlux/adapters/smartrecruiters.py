"""Read SmartRecruiters job boards from the public Posting API.

A row's Link is either

* the API URL itself,
  ``https://api.smartrecruiters.com/v1/companies/<company>/postings?<filters>``,
  which opens in a browser as JSON, so a person sees exactly the scope read; or
* the company's SmartRecruiters career page,
  ``https://careers.smartrecruiters.com/<company>[?search=…]`` (or
  ``jobs.smartrecruiters.com/<company>``), whose ``search`` is sent as ``q``.

Every other query parameter goes to the API unchanged. The API filters by
``q`` (full text), ``country`` (ISO code, e.g. ``us``), ``region``, ``city``,
``department`` (an id), ``locationType`` (``REMOTE``…), ``language``, and
``custom_field.<field id>=<value id>``: several values of one field (repeated
or comma-separated) match any of them, while different fields must all match.
A posting's ``customField`` list in the API output gives those ids, e.g.
Bosch's "Position type: Intern" is
``custom_field.5abe27936d8bc56863dd9745=f524b939-fe55-407b-a0b0-e8f4eec28997``.
Beware: the API ignores parameters it does not know (``customField.…``,
``typeOfEmployment``) rather than refusing them.

The API returns at most 100 postings per request; pages follow ``offset``
until ``totalFound``. A posting's ``id`` is the stable key.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple
from urllib.parse import unquote, urlsplit

from ..models import Posting
from .base import adapter, get, paged, query

logger = logging.getLogger(__name__)

NAME = "smartrecruiters"
API = "https://api.smartrecruiters.com/v1/companies/{company}/postings"
PAGE_SIZE = 100
# Requests per company per run (5,000 postings); a bigger scope is cut short.
MAX_PAGES = 50
# Paging is this module's job.
DROPPED = {"limit", "offset"}
# The career page's search box; the API calls it ``q``.
SEARCH_PARAM = "search"


def api_request(url: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Return the Posting API URL and query parameters for a board *url*.

    Raises:
        ValueError: If *url* names no SmartRecruiters company.
    """
    parts = urlsplit(url)
    host = parts.netloc.lower()
    segments = [unquote(s) for s in parts.path.split("/") if s]
    if host == "api.smartrecruiters.com":
        if len(segments) < 3 or segments[:2] != ["v1", "companies"]:
            raise ValueError(f"Not a SmartRecruiters postings URL: {url}")
        company = segments[2]
    elif host.endswith("smartrecruiters.com") and segments:
        company = segments[0]
    else:
        raise ValueError(f"Not a SmartRecruiters board URL: {url}")

    params: List[Tuple[str, str]] = []
    for key, values in query(url).items():
        if key in DROPPED:
            continue
        key = "q" if key == SEARCH_PARAM else key
        params.extend((key, v) for v in values if v)
    return API.format(company=company), params


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the postings a SmartRecruiters board or API URL selects, across all pages."""
    api, params = api_request(url)
    total: Dict[str, int] = {}

    def fetch_page(page: int) -> List[Posting]:
        offset = page * PAGE_SIZE
        if "found" in total and offset >= total["found"]:
            return []
        body = get(api, params=params + [("limit", str(PAGE_SIZE)), ("offset", str(offset))]).json()
        total["found"] = int(body.get("totalFound") or 0)
        return [
            Posting(f"{NAME}:{p['id']}", " ".join(p["name"].split()))
            for p in body.get("content") or []
        ]

    postings = paged(fetch_page, max_pages=MAX_PAGES)
    if total.get("found", 0) > len(postings):
        logger.warning("%s lists %d postings; read %d", url, total["found"], len(postings))
    return postings
