"""Read Dassault Systèmes' job search (``3ds.com/careers/jobs``) from the search API behind it.

A row's Link is the jobs page a person opens, filters included, e.g.
``https://www.3ds.com/careers/jobs?woc=%257B%2522type%2522%253A%255B%2522type%252FInternship%2522%255D%252C%2522country%2522%253A%255B%2522country%252FUnited%2520States%2522%255D%257D``.
Its ``woc`` parameter is the page's filters as JSON (URL-encoded twice):
``{"type": ["type/Internship"], "country": ["country/United States"]}``, and
``wockw`` its search words. The page's script turns them into one query for the
site's Exalead search, ``GET https://www.3ds.com/apisearch/card_search_api``:

    q=#all card_content_lang:en (card_content_type="career") (<words>)
      card_content_categories:(("type/Internship") AND ("country/United States"))

(values of one filter are ORed, filters ANDed), with ``b`` (the first hit) and
``hf`` (hits per page); the answer gives ``nhits`` and each hit's fields as
``metas``. This module builds the same query; the page's language comes from
the URL's path (``/de/careers/jobs`` → ``de``, English by default).

A job's ``card_id`` (its requisition number in Dassault's Taleo) is the stable
key, ``content_cta_1_url`` (``3ds.com/careers/jobs/<slug>-<id>``) its page, and
``content_info_2_value`` ("United States, MA, Waltham") where it is ("Waltham, MA").
"""
from __future__ import annotations

import json
import logging
import re
from typing import Dict, List
from urllib.parse import unquote, urlsplit

from ..models import Posting
from .base import adapter, first, format_place, get, paged, place, query, title_id

logger = logging.getLogger(__name__)

NAME = "dassault"
API = "https://www.3ds.com/apisearch/card_search_api"
# The jobs listing's own condition (its "special query"): career cards only.
SPECIAL = 'card_content_type="career"'
PAGE_SIZE = 100
# Requests per company per run; a bigger search is cut short.
MAX_PAGES = 20
LANG = re.compile(r"^[a-z]{2}$")


def filters(url: str) -> Dict[str, List[str]]:
    """Return the page filters in *url*'s ``woc`` parameter ({} without one).

    Raises:
        ValueError: If ``woc`` is not the JSON object the page writes.
    """
    raw = first(query(url), "woc")
    if not raw:
        return {}
    for _ in range(3):
        try:
            found = json.loads(raw)
            break
        except ValueError:
            raw = unquote(raw)
    else:
        raise ValueError(f"Unreadable woc filters in {url}")
    if not isinstance(found, dict):
        raise ValueError(f"Unreadable woc filters in {url}")
    return {k: [str(v) for v in values if v] for k, values in found.items()
            if isinstance(values, list) and any(values)}


def search_query(url: str) -> str:
    """Return the Exalead query the jobs page *url* sends (without its ``#all`` prefix)."""
    segment = next((s for s in urlsplit(url).path.split("/") if s), "")
    lang = segment if LANG.match(segment) else "en"
    words = first(query(url), "wockw").strip()
    parts = [f"card_content_lang:{lang}", f"({SPECIAL})"]
    if words:
        parts.append(f"({words})")
    groups = ["(" + " OR ".join(f'"{v}"' for v in values) + ")" for values in filters(url).values()]
    if groups:
        parts.append("card_content_categories:(" + " AND ".join(groups) + ")")
    return " ".join(parts)


def _metas(hit: dict) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for meta in hit.get("metas") or []:
        if isinstance(meta, dict) and meta.get("name"):
            fields.setdefault(meta["name"], str(meta.get("value") or ""))
    return fields


def _where(text: str) -> str:
    """Return "United States, MA, Waltham" (country, region, city) as "Waltham, MA"."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        return ""
    region = ", ".join(parts[1:-1])
    return format_place(parts[-1] if len(parts) > 1 else "", region, parts[0])


def to_posting(hit: dict) -> Posting:
    fields = _metas(hit)
    title = " ".join(fields.get("content_title", "").split())
    key = fields.get("card_id", "").strip()
    url = fields.get("content_cta_1_url", "").strip()
    places = [_where(p) for p in re.split(r"[;|]", fields.get("content_info_2_value", ""))]
    return Posting(f"{NAME}:{key}" if key else title_id(NAME, title), title,
                   place(places[0] if places else "", places[1:]), url if url.startswith("http") else "")


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every job a 3ds.com jobs URL shows."""
    q = "#all " + search_query(url)
    total = None

    def fetch_page(page: int) -> List[Posting]:
        nonlocal total
        if total is not None and page * PAGE_SIZE >= total:
            return []
        params = {"q": q, "b": page * PAGE_SIZE, "hf": PAGE_SIZE, "output_format": "json"}
        answer = get(API, params=params, headers={"Accept": "application/json", "Referer": url}).json()
        if not isinstance(answer, dict) or "nhits" not in answer:
            raise ValueError(f"Unexpected answer from {API}")
        total = int(answer.get("nhits") or 0)
        return [to_posting(h) for h in answer.get("hits") or [] if isinstance(h, dict)]

    return [p for p in paged(fetch_page, delay=1.0, max_pages=MAX_PAGES) if p.title]
