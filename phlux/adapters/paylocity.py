"""Paylocity recruiting boards (``recruiting.paylocity.com/recruiting/jobs/All/<guid>/<name>``).

The board's public JSON feed is off for most companies, but the board page
itself is server-rendered with every job in a ``window.pageData = {...}``
script, which is read here.
"""
from __future__ import annotations

import json
import re
from typing import List

from ..models import Posting
from .base import adapter, get

PAGE_DATA = re.compile(r"window\.pageData\s*=\s*")


def page_data(html: str) -> dict:
    """Return the ``window.pageData`` object embedded in a board page."""
    match = PAGE_DATA.search(html)
    if not match:
        raise ValueError("No window.pageData in Paylocity page")
    data, _ = json.JSONDecoder().raw_decode(html, match.end())
    return data


@adapter("paylocity")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every posting on a Paylocity board page."""
    jobs = page_data(get(url).text).get("Jobs") or []
    return [Posting(f"paylocity:{j['JobId']}", j["JobTitle"]) for j in jobs]
