"""Citadel careers, read from the site's job sitemap.

Every page on citadel.com, the job search included, answers scripted requests
with a Cloudflare challenge; the WordPress sitemaps do not. Its
``/career-sitemap.xml`` lists every open job as ``/careers/details/<slug>/``,
and each slug ends in the job's region, e.g. ``software-engineer-intern-us``.

So the row's Link stays the job search a person would open, and its filters
are applied to the slugs: ``experience-filter=internships`` keeps slugs with
"intern" in them, and ``location-filter`` (regions or offices, comma-separated)
keeps the slugs whose region it covers. Titles are rebuilt from the slug, as
the job pages that hold the real titles are behind the challenge.
"""
from __future__ import annotations

import re
from typing import List, Optional, Set
from urllib.parse import urlsplit

from ..models import Posting
from .base import adapter, first, get, query

NAME = "citadel"
SITEMAP = "https://{host}/career-sitemap.xml"
JOB_URL = re.compile(r"<loc>\s*(https?://[^<]+/careers/details/([^/<]+)/?)\s*</loc>")

# The region a slug ends in, by the search page's location filter values.
REGIONS = {"us": "US", "americas": "US", "europe": "Europe", "emea": "EMEA", "asia": "Asia", "apac": "Asia"}
# Office filter values on the search page, by the region their slugs end in.
OFFICES = {
    "US": {"chicago", "greenwich", "houston", "miami", "new-york", "san-francisco", "boston", "washington"},
    "Europe": {"london", "paris", "dublin", "zurich", "geneva", "amsterdam"},
    "Asia": {"hong-kong", "singapore", "shanghai", "sydney", "tokyo", "gurugram"},
}
# Experience filter values, by the slug word that marks them.
EXPERIENCE = {"internships": "intern", "graduates": "graduate"}
# Slug words that are acronyms rather than capitalized words.
SPELLING = {w: w.upper() for w in ("us", "bs", "ms", "mba", "ml", "ai", "emea", "apac", "it", "hr")}
SPELLING["phd"] = "PhD"


def slug_region(slug: str) -> Optional[str]:
    """Return the region a job slug ends in (``US``, ``Europe``…), if any."""
    return REGIONS.get(slug.rsplit("-", 1)[-1])


def slug_title(slug: str) -> str:
    """Rebuild a readable title from a job slug: ``software-engineer-intern-us`` → ``Software Engineer Intern (US)``."""
    words = slug.split("-")
    region = slug_region(slug)
    if region:
        words = words[:-1]
    title = " ".join(SPELLING.get(w, w.capitalize()) for w in words if w)
    return f"{title} ({region})" if region else title


def wanted_regions(location_filter: str) -> Set[str]:
    """Return the regions a ``location-filter`` value covers; empty means every region."""
    regions: Set[str] = set()
    for value in filter(None, (v.strip().lower() for v in location_filter.split(","))):
        if value in REGIONS:
            regions.add(REGIONS[value])
        for region, offices in OFFICES.items():
            if value in offices:
                regions.add(region)
    return regions


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the jobs in Citadel's career sitemap that the search URL's filters select."""
    params = query(url)
    marker = EXPERIENCE.get(first(params, "experience-filter").lower())
    regions = wanted_regions(first(params, "location-filter"))
    sitemap = get(SITEMAP.format(host=urlsplit(url).netloc)).text

    postings: List[Posting] = []
    seen: Set[str] = set()
    for _, slug in JOB_URL.findall(sitemap):
        if slug in seen:
            continue
        seen.add(slug)
        if marker and marker not in slug:
            continue
        region = slug_region(slug)
        if regions and region and region not in regions:
            continue
        postings.append(Posting(f"{NAME}:{slug}", slug_title(slug)))
    return postings
