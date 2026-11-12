"""Mundane's careers site (``mundane.co/careers``), which uses no job system.

The careers page is rendered on the server and links every open role as
``/careers/<slug>``, grouped by team in collapsed sections (a browser had to
open each). The list shows no location, so each role's own page is read too:
it carries a schema.org ``JobPosting`` (JSON-LD) with the role's title,
``employmentType`` and ``jobLocation``. A role has no id but its page, so that
URL is its key.

Mundane writes "Co‑op" with a non-breaking hyphen (U+2011); titles here use a
plain one, so "Co-op" roles are recognised as internships. A location is
written "Palo Alto, CA".
"""
from __future__ import annotations

import json
import time
from typing import List, Optional
from urllib.parse import urlsplit

from ..early_career import html_text
from ..models import Posting
from .base import adapter, bare_url, format_place, get, place, soup, text

NAME = "mundane"
# Between role pages: about 15 requests a run.
DELAY_SECONDS = 0.5
# Hyphens a title may use that a reader (and is_internship) takes as "-".
HYPHENS = str.maketrans({"‐": "-", "‑": "-", "‒": "-"})


def clean_title(title: str) -> str:
    return " ".join(title.translate(HYPHENS).split())


def role_links(html: str, base_url: str) -> List[tuple]:
    """Return ``(url, title)`` for each role the careers page links, in page order."""
    page = soup(html)
    roles = []
    for link in page.select("a[href^='/careers/']"):
        url = bare_url(link["href"], base_url)
        # /careers/<slug>, not /careers itself.
        if urlsplit(url).path.rstrip("/").count("/") != 2:
            continue
        heading = link.find("h3")
        if heading is None:
            continue
        chip = heading.find(class_="role-chip")
        if chip is not None:
            chip.extract()
        roles.append((url, clean_title(text(heading))))
    return roles


def job_posting(html: str) -> Optional[dict]:
    """Return the schema.org JobPosting a role page holds, or None."""
    for script in soup(html).select("script[type='application/ld+json']"):
        try:
            data = json.loads(script.string or "")
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return None


def location(posting: dict) -> str:
    """Return a JobPosting's location, plus a count of its others."""
    where = posting.get("jobLocation") or []
    if isinstance(where, dict):
        where = [where]
    names = []
    for spot in where:
        address = (spot or {}).get("address") or {}
        if isinstance(address, dict):
            names.append(format_place(address.get("addressLocality"), address.get("addressRegion"),
                                      address.get("addressCountry")))
    found = place(names[0] if names else "", names[1:])
    return found or ("Remote" if posting.get("jobLocationType") == "TELECOMMUTE" else "")


def unique_roles(roles: List[tuple]) -> List[tuple]:
    """Drop repeated role pages, keeping the first."""
    seen = set()
    out = []
    for role_url, title in roles:
        if role_url not in seen:
            seen.add(role_url)
            out.append((role_url, title))
    return out


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every open role on Mundane's careers page, with each role page's location."""
    postings = []
    for i, (role_url, title) in enumerate(unique_roles(role_links(get(url).text, url))):
        if i:
            time.sleep(DELAY_SECONDS)
        posting = job_posting(get(role_url).text) or {}
        postings.append(Posting(f"{NAME}:{role_url}", clean_title(posting.get("title") or title),
                                location(posting), role_url, html_text(posting.get("description"))))
    return postings

