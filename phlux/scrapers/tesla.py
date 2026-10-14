"""Tesla careers: read listings from the site's JSON API instead of the page.

The search page renders only the rows in view (about 9 of several hundred), but
it loads every listing from ``/cua-api/apps/careers/state``. Akamai rejects
direct requests to that endpoint, so it is fetched from inside the browser
after the page has passed the bot check.
"""
from __future__ import annotations

import json
import time
from typing import Dict, Iterable, List, Set
from urllib.parse import parse_qs, urlparse

STATE_PATH = "/cua-api/apps/careers/state"
FETCH_ATTEMPTS = 5
FETCH_RETRY_SECONDS = 3

_FETCH_JS = """
const done = arguments[arguments.length - 1];
fetch(arguments[0]).then(r => r.ok ? r.text() : 'HTTP ' + r.status).then(done, e => done('ERR ' + e));
"""


def location_ids(geo: Iterable[dict], site: str) -> Set[str]:
    """Return every location id under the country code *site* (e.g. ``US``)."""
    ids: Set[str] = set()
    for region in geo:
        for s in region["sites"]:
            if s["id"] == site:
                for state in s.get("states", []):
                    for city_ids in state["cities"].values():
                        ids.update(city_ids)
    return ids


def filter_listings(state: Dict, job_type: str, site: str, departments: List[str]) -> List[str]:
    """Return titles from the careers *state* matching the type, site and departments.

    Args:
        state: Parsed JSON from :data:`STATE_PATH`.
        job_type: Type name from the search URL, e.g. ``intern``.
        site: Country code from the search URL, e.g. ``US``.
        departments: Department names as Tesla labels them (e.g. ``Tesla AI``);
            empty keeps all departments.
    """
    lookup = state["lookup"]
    type_ids = {k for k, v in lookup["types"].items() if v == job_type}
    dept_ids = {k for k, v in lookup["departments"].items() if v.lower() in {d.lower() for d in departments}}
    locations = location_ids(state["geo"], site)
    return [
        listing["t"].strip()
        for listing in state["listings"]
        if str(listing["y"]) in type_ids
        and listing["l"] in locations
        and (not departments or listing["dp"] in dept_ids)
    ]


def tesla_jobs(driver, arg: str = "") -> List[str]:
    """Scrape Tesla listings using filters from the currently loaded search URL.

    ``type`` and ``site`` come from the page URL (default ``intern`` / ``US``).
    *arg* optionally restricts departments, separated by ``|``.
    """
    query = parse_qs(urlparse(driver.current_url).query)
    job_type = query.get("type", ["intern"])[0]
    site = query.get("site", ["US"])[0]
    departments = [d.strip() for d in arg.split("|") if d.strip()]

    # Akamai answers 429 until its in-page challenge finishes, so give it a moment.
    for _ in range(FETCH_ATTEMPTS):
        raw = driver.execute_async_script(_FETCH_JS, STATE_PATH)
        if raw.startswith("{"):
            return filter_listings(json.loads(raw), job_type, site, departments)
        time.sleep(FETCH_RETRY_SECONDS)
    raise RuntimeError(f"Tesla careers API failed: {raw[:100]}")
