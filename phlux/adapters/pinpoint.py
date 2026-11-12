"""Pinpoint career sites (``<slug>.pinpointhq.com``).

The site lists every open posting as JSON at ``/postings.json`` on its host, in
one request: the posting's numeric ``id`` (the stable key), ``title``, page
``url`` (``/en/postings/<uuid>``), ``employment_type``, ``workplace_type`` and
``location``.

A location gives a city and a ``province`` but no country. A province that is a
US state makes it "Redondo Beach, CA"; any other is kept as written, "London,
England". A remote posting naming no city is "Remote". The JSON takes no
filters, so a site URL with a query is refused rather than read as the whole
site.
"""
from __future__ import annotations

from typing import List
from urllib.parse import urlsplit, urljoin, urlunsplit

from ..early_career import html_text
from ..models import Posting
from .base import adapter, format_place, get, us_state

NAME = "pinpoint"
API_PATH = "/postings.json"
# Description sections a posting sends with the list.
SECTIONS = ("description", "key_responsibilities", "skills_knowledge_expertise", "benefits")


def api_url(url: str) -> str:
    """Return the postings JSON of the Pinpoint site *url* is on."""
    parts = urlsplit(url)
    if not parts.netloc.lower().endswith(".pinpointhq.com"):
        raise ValueError(f"Not a Pinpoint site: {url}")
    if parts.query:
        raise ValueError(f"Pinpoint site filters are not supported: {url}")
    return urlunsplit(("https", parts.netloc, API_PATH, "", ""))


def location(job: dict) -> str:
    """Return a posting's location: "City, ST" in the US, else its city and province."""
    loc = job.get("location") or {}
    city = " ".join(str(loc.get("city") or "").split())
    province = " ".join(str(loc.get("province") or "").split())
    country = loc.get("country") or loc.get("country_code") or ""
    if country or us_state(province):
        found = format_place(city, province, country or "US")
    else:
        found = ", ".join(part for part in (city, province) if part) or " ".join(str(loc.get("name") or "").split())
    if job.get("workplace_type") == "remote" and not city:
        return "Remote"
    return found


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every posting on a Pinpoint career site."""
    api = api_url(url)
    jobs = get(api).json().get("data") or []
    return [
        Posting(
            f"{NAME}:{j['id']}",
            " ".join(j["title"].split()),
            location(j),
            j.get("url") or (urljoin(api, j["path"]) if j.get("path") else ""),
            "\n".join(html_text(j.get(section)) for section in SECTIONS if j.get(section)),
        )
        for j in jobs
    ]
