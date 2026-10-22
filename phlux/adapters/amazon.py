"""amazon.jobs: its search page and its team pages.

Each kind of link is read the way its own page reads it:

* ``www.amazon.jobs/<locale>/search?...``, the search page. Its URL filters are
  renamed the way the page's script renames them (``country[]`` becomes
  ``normalized_country_code[]``, ``job_type[]=Internship`` becomes
  ``is_intern[]=1``...) and sent to ``/<locale>/search.json``, 100 jobs a page.
* ``amazon.jobs/content/<locale>/teams/...``, a team page. The page's data
  names what it is scoped to (teams, job tags...) and the public search API
  key; its URL filters (``country[]``, ``employment-type[]``...) narrow that
  further. Both go to ``POST /api/jobs/search``, as the page sends them. The
  key is read from the page on every run, never stored here.

The search services ignore filter names they do not know and then answer with
the whole site (over 20,000 jobs), so a misspelled filter would silently widen
a company's scope. A search that finds more than :data:`MAX_HITS` jobs is
refused instead.

Postings are keyed by Amazon's iCIMS job id, the number in ``/jobs/<id>/...``.
"""
from __future__ import annotations

import json
import math
import re
from typing import Dict, Iterable, List, Set
from urllib.parse import parse_qsl, urljoin, urlsplit

from ..models import Posting
from .base import adapter, get, post

PAGE_SIZE = 100
# A filtered search never comes near this; the whole site is over 20,000.
MAX_HITS = 5000

# ── Search page (/<locale>/search) ────────────────────────────────────────────

# Page filters the search page renames on the way to search.json.
RENAMED = {
    "country[]": "normalized_country_code[]",
    "state[]": "normalized_state_name[]",
    "city[]": "normalized_city_name[]",
    "cities[]": "normalized_location[]",
    "industry_experience": "industry_experience[]",
}
# job_type[] values and the search.json filters the page sends for them.
JOB_TYPES = {
    "Full-Time": [("schedule_type_id[]", "Full-Time")],
    "Part-Time": [("schedule_type_id[]", t) for t in (
        "Flex-Time", "Part-Time", "Reduced-Time", "Flex-Time (<19 hours)",
        "Part-Time (20-29 hours)", "Reduced-Time (30-39 hours)",
        "Flex Time (<19 hours)", "Reduced Time (30-39 hours)",
    )],
    "Seasonal": [("employee_class[]", "Seasonal/short-term")],
    "Internship": [("is_intern[]", "1")],
}
# category_type / internal_category_type[] values and their search.json filters.
CATEGORY_TYPES = {
    "Corporate": [("job_function_id[]", "job_function_corporate_80rdb4")],
    "Fulfillment-center": [("job_function_id[]", "job_function_fulfillment_center_mn2kd4"),
                           ("job_function_id[]", "fulfillment-and-operations")],
    "Customer Service": [("job_function_id[]", "job_function_customer_service_fpzyxo"),
                         ("job_function_id[]", "amazon-customer-service")],
    "studentprograms": [("business_category[]", "studentprograms")],
    "Work from Home": [("location[]", "virtual-locations")],
}
REFINE = {
    "Tech Jobs": ("is_tech", "1"),
    "Non Tech Jobs": ("is_tech", "0"),
    "Referral-only Jobs": ("is_posted_externally", "1"),
}
# Paging belongs to this adapter, not to the link.
PAGING = {"offset", "result_limit"}


def search_json_params(url: str) -> List[tuple]:
    """Translate a search page URL's query into ``search.json`` parameters.

    Filters the page sends under another name are renamed; everything else
    (``base_query``, ``loc_query``, ``sort``, ``business_category[]``...) passes
    through unchanged, as the page passes it.

    Raises:
        ValueError: For a ``job_type[]``, category type or refinement value the
            page itself does not know.
    """
    params = []
    for key, value in parse_qsl(urlsplit(url).query, keep_blank_values=True):
        if key in PAGING:
            continue
        if key == "job_type[]":
            params.extend(_lookup(JOB_TYPES, key, value))
        elif key in ("category_type", "internal_category_type[]"):
            params.extend(_lookup(CATEGORY_TYPES, key, value))
        elif key == "refine_facet":
            params.append(_lookup(REFINE, key, value))
        else:
            params.append((RENAMED.get(key, key), value))
    return params


def _lookup(table: Dict, key: str, value: str):
    if value not in table:
        raise ValueError(f"Unknown amazon.jobs filter {key}={value!r}")
    return table[value]


def _search_page(url: str) -> List[Posting]:
    parts = urlsplit(url)
    endpoint = f"{parts.scheme}://{parts.netloc}{parts.path.rstrip('/')}.json"
    params = search_json_params(url)
    postings: List[Posting] = []
    offset = 0
    while True:
        page = get(endpoint, params=params + [("offset", offset), ("result_limit", PAGE_SIZE)]).json()
        if page.get("error"):
            raise RuntimeError(f"amazon.jobs search failed: {page['error']}")
        hits = page.get("hits") or 0
        _check_hits(hits, url)
        postings += [Posting(f"amazon:{j['id_icims']}", _title(j["title"])) for j in page.get("jobs") or []]
        offset += PAGE_SIZE
        if offset >= hits or not page.get("jobs"):
            return postings


# ── Team pages (/content/<locale>/teams/...) ──────────────────────────────────

# A team page's URL filters (``name[]=value``).
COUNTRY, REGION, CITY = "country[]", "region[]", "city[]"
# Employment types and the job-type facets the page sends for them.
EMPLOYMENT_TYPES = {
    "Intern": ("employeeClass", ["Intern"]),
    "Temporary/seasonal": ("employeeClass", ["Seasonal/short-term"]),
    "Full time": ("scheduleTypeId", ["Full-Time"]),
    "Part time": ("scheduleTypeId", [v for _, v in JOB_TYPES["Part-Time"]]),
}
# URL filters that become filter facets, and their facet names.
FILTER_FACETS = {
    "category[]": "category",
    "level[]": "jobLevel",
    "hiring-manager[]": "hiringManager",
    "role-type[]": "isManager",
    "location[]": "location",
}
TEAM_FILTERS = {COUNTRY, REGION, CITY, "employment-type[]", "team[]", "keyword[]", *FILTER_FACETS}
EXCLUDED = [
    {"name": "isConfidential", "values": [{"name": "1"}]},
    {"name": "businessCategory", "values": [{"name": "a-confidential-job"}]},
]


def _page_data(html: str) -> dict:
    match = re.search(r'<script id="jobs-cms-next-data" type="application/json">(.*?)</script>', html, re.S)
    if not match:
        raise RuntimeError("No page data on the amazon.jobs team page")
    return json.loads(match.group(1))


def _team_ids(teams: Iterable) -> Set[str]:
    """Return the identifiers of *teams* and all their sub-teams."""
    ids: Set[str] = set()
    pending = list(teams)
    while pending:
        team = pending.pop()
        if isinstance(team, str):
            ids.add(team)
            continue
        ids.add(team["identifier"])
        pending.extend(team.get("children") or [])
    return ids


def _facet(name: str, values: Iterable[str]) -> dict:
    return {"name": name, "requestedFacetCount": 9999, "values": [{"name": v} for v in sorted(values)]}


def team_search_body(url: str, search_filters: List[dict]) -> dict:
    """Build the ``/api/jobs/search`` request a team page sends for *url*.

    *search_filters* is the page's own scope (its ``searchFilters``); the URL's
    filters narrow it.

    Raises:
        ValueError: For a URL filter or employment type this adapter does not know.
    """
    params: Dict[str, List[str]] = {}
    for key, value in parse_qsl(urlsplit(url).query, keep_blank_values=True):
        if value:
            params.setdefault(key, []).append(value)
    unknown = set(params) - TEAM_FILTERS
    if unknown:
        raise ValueError(f"Unsupported amazon.jobs team page filter(s): {sorted(unknown)}")

    scope: Dict[str, list] = {}
    for group in search_filters:
        for key, values in group.items():
            scope.setdefault(key, []).extend(values or [])
    places = scope.get("locations", [])
    countries = set(params.get(COUNTRY, [])) | set(scope.get("countries", [])) | {p["country"] for p in places if p.get("country")}
    regions = set(params.get(REGION, [])) | set(scope.get("states", [])) | {p["state"] for p in places if p.get("state")}
    cities = set(params.get(CITY, [])) | set(scope.get("cities", [])) | {p["city"] for p in places if p.get("city")}
    teams = _team_ids(scope.get("teams", [])) | set(params.get("team[]", []))

    # Each selected country (or state, city) is one alternative; the page
    # sends every combination.
    location_facets = [[
        {"name": "country", "requestedFacetCount": 9999, **({"values": [{"name": c}]} if c else {})},
        {"name": "normalizedStateName", "requestedFacetCount": 9999, **({"values": [{"name": r}]} if r else {})},
        {"name": "normalizedCityName", "requestedFacetCount": 9999, **({"values": [{"name": t}]} if t else {})},
    ] for c in sorted(countries) or [None] for r in sorted(regions) or [None] for t in sorted(cities) or [None]]

    filter_facets = []
    tags = set(scope.get("jobTags", []))
    if tags:
        filter_facets.append(_facet("optionalSearchLabels", tags))
    categories = set(scope.get("jobCategories", [])) | set(params.get("category[]", []))
    if categories:
        filter_facets.append(_facet("category", categories))
    for key, name in FILTER_FACETS.items():
        if key != "category[]" and params.get(key):
            filter_facets.append(_facet(name, params[key]))

    job_types: Dict[str, Set[str]] = {}
    for value in params.get("employment-type[]", []):
        if value not in EMPLOYMENT_TYPES:
            raise ValueError(f"Unknown amazon.jobs employment type {value!r}")
        name, values = EMPLOYMENT_TYPES[value]
        job_types.setdefault(name, set()).update(values)

    content = {"name": "primarySearchLabel", "requestedFacetCount": 9999}
    if teams:
        content["values"] = [{"name": t} for t in sorted(teams)]
    job_ids = scope.get("jobIds", [])
    return {
        "accessLevel": "EXTERNAL",
        "contentFilterFacets": [content],
        "excludeFacets": EXCLUDED,
        "filterFacets": filter_facets,
        "includeFacets": [{"name": "icimsJobId", "values": [{"name": str(i)} for i in job_ids]}] if job_ids else [],
        "jobTypeFacets": [{"name": n, "values": [{"name": v} for v in sorted(vs)]} for n, vs in job_types.items()],
        "locationFacets": location_facets,
        "query": " ".join(params.get("keyword[]", [])),
        "size": PAGE_SIZE,
        "start": 0,
        "treatment": "OM",
        "sort": {"sortOrder": "DESCENDING", "sortType": "CREATED_DATE"},
    }


def _team_page(url: str) -> List[Posting]:
    page = get(url)
    data = _page_data(page.text)
    config = data.get("runtimeConfig") or data["props"]
    key, endpoint = config["searchKey"], config["searchEndpoint"]
    content = data["props"]["pageProps"].get("content") or {}
    body = team_search_body(url, content.get("searchFilters") or [])
    api = urljoin(page.url, endpoint) + "?is_als=true"
    headers = {"X-Api-Key": key, "Accept": "application/json"}
    postings: List[Posting] = []
    pages = 1
    for n in range(math.ceil(MAX_HITS / PAGE_SIZE)):
        if n >= pages:
            break
        result = post(api, json={**body, "start": n * PAGE_SIZE}, headers=headers).json()
        # A search with no hits answers with every field null.
        found = result.get("found") or 0
        _check_hits(found, url)
        pages = math.ceil(found / PAGE_SIZE)
        for hit in result.get("searchHits") or []:
            fields = hit["fields"]
            postings.append(Posting(f"amazon:{fields['icimsJobId'][0]}", _title(fields["title"][0])))
    return postings


# ── Shared ────────────────────────────────────────────────────────────────────

def _check_hits(hits: int, url: str) -> None:
    if hits > MAX_HITS:
        raise RuntimeError(
            f"amazon.jobs search found {hits} jobs (over {MAX_HITS}); a filter in {url} "
            "was probably ignored, so the whole site came back"
        )


def _title(title: str) -> str:
    return " ".join(title.split())


@adapter("amazon")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the postings an amazon.jobs search page or team page shows."""
    path = urlsplit(url).path
    if "/teams/" in path:
        return _team_page(url)
    if re.search(r"/search/?$", path):
        return _search_page(url)
    raise ValueError(f"Not an amazon.jobs search or team page: {url}")
