"""Read Tencent's campus careers site (``join.qq.com``) from the JSON API behind it.

A row's Link is the site's job list a person opens, e.g.
``https://join.qq.com/post.html?query=p_2,w_407,w_401&c_t=2``. The page reads
its filters from the URL: ``query`` is a comma-separated list of codes, each
with a prefix saying what it filters (``p_`` the recruiting project, e.g. 2 for
graduating-year internships and 1 for new-grad hiring; ``w_`` the work city;
``r_`` the interview city; ``b_`` the business group; ``2_``…``7_`` a job
family), ``c_t`` says whether the ``w_`` cities are in China (1) or abroad (2),
``f_c=all`` picks every city abroad, and ``keyword`` is the search box. It then
asks ``POST /api/v1/position/searchPosition`` for the list, and so does this
module, so the Link shows a person what is scraped.

The page drops a ``p_`` project that ``GET /api/v1/position/getProjectMapping``
no longer lists, and searches every listed project when none is left; this
module does the same. ``w_`` cities count only with a ``c_t``.

A job's ``postId`` is the stable key. Jobs abroad come from Tencent's Workday
board and carry its page as ``positionUrl``; others open at
``post_detail.html?postid=<postId>``. ``workCities`` is "US-California-Palo
Alto" for a Workday job (written "Palo Alto, CA") and a space-separated list of
Chinese city names for the others.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Dict, List, Tuple

from ..models import Posting
from .base import adapter, first, format_place, get, is_us, place, post, query

logger = logging.getLogger(__name__)

NAME = "tencent"
SITE = "https://join.qq.com"
SEARCH = SITE + "/api/v1/position/searchPosition"
PROJECTS = SITE + "/api/v1/position/getProjectMapping"
CITIES = SITE + "/api/v1/position/getPositionWorkCities"
DETAIL = SITE + "/post_detail.html?postid={}"
# The API takes 1-1000.
PAGE_SIZE = 100
# Requests per company per run; a longer list is cut short.
MAX_PAGES = 20
DELAY = 1.0
# The ``c_t`` values, and the API's ``workCountryType`` for them.
CHINA, ABROAD = "1", "2"
JOB_FAMILY = re.compile(r"[2-7]_(\d+)")
HEADERS = {"Referer": SITE + "/post.html", "Origin": SITE}


def parse_query(url: str) -> Dict[str, List[str]]:
    """Return a list URL's ``query`` codes grouped by prefix: {"p": ["2"], "w": ["407"], "family": […]}."""
    groups: Dict[str, List[str]] = {"p": [], "w": [], "r": [], "b": [], "family": []}
    for value in query(url).get("query", []):
        for code in (c.strip() for c in value.split(",")):
            family = JOB_FAMILY.fullmatch(code)
            if family:
                groups["family"].append(family.group(1))
            elif len(code) > 2 and code[1] == "_" and code[0] in groups:
                groups[code[0]].append(code[2:])
    return groups


def _api(response) -> object:
    data = response.json()
    if data.get("status") != 0:
        raise ValueError(f"join.qq.com answered {data.get('status')} {data.get('message')!r}")
    return data.get("data")


def project_ids(wanted: List[str]) -> List[int]:
    """Return the project ids to search: the *wanted* ones still listed, else every listed one."""
    listed = [int(sub["mappingId"]) for group in _api(get(PROJECTS, headers=HEADERS)) or []
              for sub in group.get("subProjectList") or []]
    kept = [int(p) for p in wanted if p.isdigit() and int(p) in listed]
    if wanted and not kept:
        logger.warning("join.qq.com no longer lists project %s; searching all projects", ",".join(wanted))
    return kept or listed


def work_cities(url: str, cities: List[str]) -> Tuple[int, List[str]]:
    """Return the API's ``workCountryType`` and ``workCityList`` for a list URL."""
    params = query(url)
    if first(params, "f_c") == "all":
        abroad = (_api(get(CITIES, headers=HEADERS)) or {}).get(ABROAD) or []
        return int(ABROAD), [c["code"] for c in abroad]
    country = first(params, "c_t")
    if country in (CHINA, ABROAD) and cities:
        return int(country), cities
    return 0, []


def location(text: str) -> str:
    """Return where a job is from its ``workCities``: "Palo Alto, CA", "London, United Kingdom", "深圳总部 +2"."""
    text = " ".join((text or "").split())
    if "-" not in text:
        names = text.split()
        return place(names[0], names[1:]) if names else ""
    places = []
    for part in (p.strip() for p in text.split(",")):
        bits = [b.strip() for b in part.split("-", 2)]
        if is_us(bits[0]) and len(bits) == 3:
            places.append(format_place(bits[2], bits[1], bits[0]))
        elif len(bits) >= 2:
            places.append(format_place(bits[1], "", bits[0]))
        elif part:
            places.append(part)
    return place(places[0], places[1:]) if places else ""


def to_posting(job: dict) -> Posting:
    post_id = str(job["postId"])
    url = job.get("positionUrl") if job.get("positionSource") != "oa" else ""
    return Posting(f"{NAME}:{post_id}", job.get("positionTitle") or "", location(job.get("workCities")),
                   url or DETAIL.format(post_id))


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every job a join.qq.com list URL shows."""
    groups = parse_query(url)
    country, cities = work_cities(url, groups["w"])
    body = {
        "projectIdList": [],
        "projectMappingIdList": project_ids(groups["p"]),
        "keyword": first(query(url), "keyword").strip(),
        "bgList": groups["b"],
        "workCountryType": country,
        "workCityList": cities,
        "recruitCityList": groups["r"],
        "positionFidList": groups["family"],
        "pageSize": PAGE_SIZE,
    }
    postings: List[Posting] = []
    seen: set = set()
    for page in range(1, MAX_PAGES + 1):
        if page > 1:
            time.sleep(DELAY)
        data = _api(post(SEARCH, headers=HEADERS, json={**body, "pageIndex": page})) or {}
        jobs = data.get("positionList") or []
        fresh = [to_posting(j) for j in jobs if str(j["postId"]) not in seen]
        seen.update(str(j["postId"]) for j in jobs)
        postings.extend(fresh)
        if not fresh or len(postings) >= (data.get("count") or 0):
            break
    else:
        logger.warning("%s: stopped after %d pages", url, MAX_PAGES)
    return postings
