"""Read ByteDance's career sites, TikTok's and ByteDance's own, from the JSON API behind them.

TikTok (``lifeattiktok.com``) and ByteDance (``joinbytedance.com``) run one job
system. A row's Link is the site's search page a person opens, e.g.
``https://lifeattiktok.com/search?keyword=&recruitment_id_list=202&subject_id_list=…
&location_code_list=CT_157%2CCT_94&job_category_id_list=&limit=12&offset=0``.
The page asks ``POST <api>/search/job/posts`` for the results, sending the
URL's comma-separated filters as lists (``recruitment_id_list``: 202 is
interns, 201 new grads; ``subject_id_list``: the recruiting programme;
``location_code_list``: cities; ``job_category_id_list``; ``tag_id_list``) and
its ``keyword``. This module sends the same request, so the Link shows a person
what is scraped; its ``limit`` and ``offset`` only page the list and are
ignored. The API answers 400 unless the request names the site, with the
``website-path`` header (``tiktok`` for TikTok, ``en`` for ByteDance) and the
site's ``origin``. It gives the total in ``count`` and keeps one order, so the
list is read 100 at a time until that many have come.

A job's ``id`` is the stable key, and ``<site>/search/<id>`` is its page. Its
``city_info`` is a chain of places (city, then state, then country), written
"San Jose, CA". The job's ``description`` and ``requirement`` are kept as the
posting's text, for new-grad wording.
"""
from __future__ import annotations

import logging
import time
from typing import Dict, List, NamedTuple, Optional
from urllib.parse import urlsplit

from ..models import Posting
from .base import adapter, first, format_place, post, query

logger = logging.getLogger(__name__)

NAME = "bytedance"
PAGE_SIZE = 100
# Requests per company per run; a longer list is cut short.
MAX_PAGES = 20
# Seconds between pages.
DELAY = 1.0
# The URL's filters, comma-separated there and sent as lists.
LIST_PARAMS = ("recruitment_id_list", "subject_id_list", "location_code_list",
               "job_category_id_list", "tag_id_list")
# ``city_info.location_type`` of each level of a place.
CITY, STATE, COUNTRY = 3, 2, 1


class Site(NamedTuple):
    api: str
    website_path: str
    origin: str


SITES: Dict[str, Site] = {
    "lifeattiktok.com": Site("https://api.lifeattiktok.com/api/v1/public/supplier", "tiktok",
                             "https://lifeattiktok.com"),
    "joinbytedance.com": Site("https://jobs.bytedance.com/api/v1/public/supplier", "en",
                              "https://joinbytedance.com"),
}


def site_of(url: str) -> Site:
    """Return the site a search URL belongs to.

    Raises:
        ValueError: For a host that is neither TikTok's nor ByteDance's career site.
    """
    host = urlsplit(url).netloc.lower().removeprefix("www.")
    if host not in SITES:
        raise ValueError(f"Not a TikTok or ByteDance career site: {url}")
    return SITES[host]


def search_body(url: str) -> Dict[str, object]:
    """Return the search a URL shows, as the API's request body (without paging)."""
    params = query(url)
    body: Dict[str, object] = {"keyword": first(params, "keyword").strip()}
    for name in LIST_PARAMS:
        body[name] = [v.strip() for value in params.get(name, []) for v in value.split(",") if v.strip()]
    return body


def location(city_info: Optional[dict]) -> str:
    """Return where a job is from its ``city_info`` chain: "Seattle, WA", "London, United Kingdom"."""
    names = {CITY: "", STATE: "", COUNTRY: ""}
    node, depth = city_info, 0
    while isinstance(node, dict) and depth < 5:
        name = node.get("en_name") or node.get("i18n_name") or node.get("name") or ""
        if node.get("location_type") in names and not names[node["location_type"]]:
            names[node["location_type"]] = name
        node, depth = node.get("parent"), depth + 1
    return format_place(names[CITY], names[STATE], names[COUNTRY])


def to_posting(job: dict, site: Site) -> Posting:
    text = "\n\n".join(part for part in (job.get("description"), job.get("requirement")) if part)
    return Posting(f"{NAME}:{job['id']}", job.get("title") or "", location(job.get("city_info")),
                   f"{site.origin}/search/{job['id']}", text)


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every job a TikTok or ByteDance search URL shows."""
    site = site_of(url)
    body = search_body(url)
    headers = {"Content-Type": "application/json", "Accept": "application/json",
               "accept-language": "en-US", "website-path": site.website_path, "origin": site.origin}
    postings: List[Posting] = []
    seen: set = set()
    for page in range(MAX_PAGES):
        if page:
            time.sleep(DELAY)
        data = post(f"{site.api}/search/job/posts", headers=headers,
                    json={**body, "limit": PAGE_SIZE, "offset": page * PAGE_SIZE}).json()
        if data.get("code") != 0:
            raise ValueError(f"{url}: API answered {data.get('code')} {data.get('message')!r}")
        jobs = (data.get("data") or {}).get("job_post_list") or []
        fresh = [to_posting(j, site) for j in jobs if str(j["id"]) not in seen]
        seen.update(str(j["id"]) for j in jobs)
        postings.extend(fresh)
        total = (data.get("data") or {}).get("count") or 0
        if not fresh or len(postings) >= total:
            break
    else:
        logger.warning("%s: stopped after %d pages", url, MAX_PAGES)
    return postings
