"""Shared plumbing for adapters: HTTP with backoff, paging, HTML parsing, registry.

An adapter reads one kind of job system or company site without a browser. It
is a function ``fetch(url) -> List[Posting]`` registered under a name with
:func:`adapter`; a ``companies.csv`` row selects it with ``@name`` and gives the
URL. Adapters read their filters from that URL (as the board would), so a
person opening the link sees what the scraper reads.

Every posting needs a stable ``source:id`` key: storage uses it to tell an
edited title from a new posting, and to switch a company over from browser
scraping without alerting on its backlog (see phlux.scraping.switching_to_ids).
Use the site's own job id; only when a site exposes none, fall back to the job's
URL, and only when it has no URL either, to the title (:func:`title_id`).

A posting's ``location`` is written the way a person would: "Santa Clara, CA"
for a US town (:func:`format_place` from separate fields, :func:`tidy_place`
for a site's own text), "Munich, Germany" elsewhere, and "Austin, TX +2" when a
job has several (:func:`place`). It must come out the same on every run.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Callable, Dict, Iterable, List, Optional
from urllib.parse import parse_qs, unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from ..models import Posting

logger = logging.getLogger(__name__)

TIMEOUT = 30
# Some sites refuse requests' default user agent.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
# Rate-limited sites answer 429; wait this long, doubling, before each retry.
BACKOFF_SECONDS = 5
RETRIES_429 = 3
# A guard against a site whose paging never ends.
MAX_PAGES = 200

ADAPTERS: Dict[str, Callable[[str], List[Posting]]] = {}


def adapter(name: str):
    """Register the decorated ``fetch(url)`` as the ``@name`` adapter."""

    def register(fetch: Callable[[str], List[Posting]]):
        if name in ADAPTERS:
            raise ValueError(f"Adapter {name!r} registered twice")
        ADAPTERS[name] = fetch
        return fetch

    return register


def request(method: str, url: str, session: Optional[requests.Session] = None, **kwargs) -> requests.Response:
    """Send a request with browser-like headers, retrying 429s with backoff.

    Raises:
        requests.HTTPError: For any other error status, or a 429 that outlasts the retries.
    """
    kwargs.setdefault("timeout", TIMEOUT)
    kwargs["headers"] = {**HEADERS, **kwargs.get("headers", {})}
    send = (session or requests).request
    wait = BACKOFF_SECONDS
    for attempt in range(RETRIES_429 + 1):
        response = send(method, url, **kwargs)
        if response.status_code != 429 or attempt == RETRIES_429:
            break
        logger.info("429 from %s; retrying in %ss", urlsplit(url).netloc, wait)
        time.sleep(wait)
        wait *= 2
    response.raise_for_status()
    return response


def get(url: str, **kwargs) -> requests.Response:
    return request("GET", url, **kwargs)


def post(url: str, **kwargs) -> requests.Response:
    return request("POST", url, **kwargs)


def query(url: str) -> Dict[str, List[str]]:
    """Return *url*'s query parameters with ``name[]`` keys folded into ``name``."""
    params: Dict[str, List[str]] = {}
    for key, values in parse_qs(urlsplit(url).query, keep_blank_values=True).items():
        params.setdefault(key.removesuffix("[]"), []).extend(values)
    return params


def first(params: Dict[str, List[str]], key: str, default: str = "") -> str:
    """Return the first value of *key* in parsed query *params*, or *default*."""
    values = params.get(key)
    return values[0] if values else default


def path_slug(url: str, index: int = 0) -> str:
    """Return a path segment of *url* (the first by default), URL-decoded."""
    parts = [p for p in urlsplit(url).path.split("/") if p]
    if len(parts) <= index:
        raise ValueError(f"No path segment {index} in {url}")
    return unquote(parts[index])


def paged(fetch_page: Callable[[int], List[Posting]], delay: float = 0.0,
          max_pages: int = MAX_PAGES) -> List[Posting]:
    """Collect postings from ``fetch_page(0)``, ``fetch_page(1)``… until one comes back empty.

    Postings already seen (same id) are dropped, and a page made only of seen
    postings also ends the walk, which stops sites that repeat their last page.
    *delay* seconds are slept between pages, for rate-limited sites.
    """
    seen: set = set()
    postings: List[Posting] = []
    for page in range(max_pages):
        if page and delay:
            time.sleep(delay)
        fresh = [p for p in fetch_page(page) if p.id not in seen]
        if not fresh:
            break
        seen.update(p.id for p in fresh)
        postings.extend(fresh)
    else:
        logger.warning("Stopped after %d pages", max_pages)
    return postings


def bare_url(href: str, base_url: str = "") -> str:
    """Return *href*, made absolute against *base_url*, without its query or fragment.

    For a job link whose parameters only track the visit or steer the list page,
    so the same job gets the same URL on every run.
    """
    parts = urlsplit(urljoin(base_url, href))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def text(node) -> str:
    """Return *node*'s visible text with whitespace collapsed."""
    return " ".join(node.get_text(" ").split())


def place(primary: str | None, others: Iterable[str | None] = ()) -> str:
    """Return a posting's location for display: the first one, plus a count of the rest."""
    names: List[str] = []
    for name in [primary, *others]:
        name = " ".join((name or "").split())
        if name and name not in names:
            names.append(name)
    if not names:
        return ""
    return f"{names[0]} +{len(names) - 1}" if len(names) > 1 else names[0]


US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
}
_STATE_CODES = {name.casefold(): code for code, name in US_STATES.items()}
US_NAMES = {"us", "usa", "u.s.", "u.s.a.", "united states", "united states of america", "united states (usa)"}
# Country codes sites give (ISO 3166 alpha-2, and a few alpha-3), for the ones postings are found in.
COUNTRIES = {
    "AE": "United Arab Emirates", "AR": "Argentina", "AT": "Austria", "AU": "Australia", "BE": "Belgium",
    "BR": "Brazil", "CA": "Canada", "CH": "Switzerland", "CL": "Chile", "CN": "China", "CO": "Colombia",
    "CR": "Costa Rica", "CZ": "Czech Republic", "DE": "Germany", "DK": "Denmark", "EG": "Egypt", "ES": "Spain",
    "FI": "Finland", "FR": "France", "GB": "United Kingdom", "GR": "Greece", "HK": "Hong Kong", "HU": "Hungary",
    "ID": "Indonesia", "IE": "Ireland", "IL": "Israel", "IN": "India", "IT": "Italy", "JP": "Japan",
    "KR": "South Korea", "LU": "Luxembourg", "MX": "Mexico", "MY": "Malaysia", "NL": "Netherlands", "NO": "Norway",
    "NZ": "New Zealand", "PH": "Philippines", "PL": "Poland", "PT": "Portugal", "RO": "Romania", "SA": "Saudi Arabia",
    "SE": "Sweden", "SG": "Singapore", "SK": "Slovakia", "TH": "Thailand", "TR": "Turkey", "TW": "Taiwan",
    "UA": "Ukraine", "UK": "United Kingdom", "VN": "Vietnam", "ZA": "South Africa",
    "CAN": "Canada", "CHN": "China", "DEU": "Germany", "FRA": "France", "GBR": "United Kingdom", "IND": "India",
    "JPN": "Japan", "MEX": "Mexico",
}


# A state with its ZIP code: "PA 15201".
_STATE_ZIP = re.compile(r"([A-Za-z]{2})\s+\d{5}(?:-\d{4})?")


def _squash(value) -> str:
    return " ".join(str(value or "").split())


def is_us(country: str | None) -> bool:
    """Return True if *country* names the United States ("US", "USA", "United States of America"…)."""
    return _squash(country).casefold() in US_NAMES


def us_state(name: str | None) -> str:
    """Return the postal code of the US state *name* ("California" or "CA"), or ""."""
    name = _squash(name)
    if name.upper() in US_STATES:
        return name.upper()
    return _STATE_CODES.get(name.casefold(), "")


def country_name(country: str | None) -> str:
    """Return a country's name: *country* itself, or the name of its code ("DE", "CAN")."""
    country = _squash(country)
    return COUNTRIES.get(country.upper(), country) if len(country) in (2, 3) else country


def format_place(city: str | None = "", region: str | None = "", country: str | None = "") -> str:
    """Return a place given as separate fields the way a person writes it.

    A US town is "City, ST" ("Santa Clara", "California", "United States" →
    "Santa Clara, CA"); a place abroad is "City, Country" ("Munich, Germany").
    Without a country, a *region* that is a US state makes the place a US one.
    """
    city, region, country = _squash(city), _squash(region), _squash(country)
    state = us_state(region)
    if is_us(country) or (not country and state):
        if city:
            return f"{city}, {state or region}" if state or region else city
        if region:
            return US_STATES.get(state, region)
        return "United States"
    name = country_name(country)
    first = city or region
    if not first or first.casefold() == name.casefold():
        return name
    return f"{first}, {name}" if name else first


def tidy_place(text: str | None) -> str:
    """Return a site's location text with its US places written "City, ST".

    "Santa Clara, California, United States of America" and "Santa Clara, CA, US"
    become "Santa Clara, CA", "San Francisco, California" "San Francisco, CA",
    and "York, PA 17402" "York, PA"; a repeated part is dropped ("Tokyo, Tokyo").
    Anything else ("Remote, US", "Gurugram, Haryana, India") keeps the site's wording.
    """
    text = _squash(text)
    parts: List[str] = []
    for part in (p.strip() for p in text.split(",")):
        zipped = _STATE_ZIP.fullmatch(part)
        if zipped and us_state(zipped.group(1)):
            part = us_state(zipped.group(1))
        if part and not (parts and parts[-1].casefold() == part.casefold()):
            parts.append(part)
    if len(parts) >= 2 and is_us(parts[-1]):
        body = parts[:-1]
        if len(body) == 1 and us_state(body[0]):
            return US_STATES[us_state(body[0])]
        if len(body) >= 2 and us_state(body[-1]):
            return f"{', '.join(body[:-1])}, {us_state(body[-1])}"
    # "Tbilisi, Georgia" is no US town; with no country named, Georgia stays as written.
    elif len(parts) == 2 and us_state(parts[1]) and parts[1].casefold() != "georgia":
        return f"{parts[0]}, {us_state(parts[1])}"
    return ", ".join(parts)


def title_id(source: str, title: str) -> str:
    """Last-resort key for a site that gives a posting neither an id nor a URL."""
    return f"{source}:title:{' '.join(title.split())}"


def unique(postings: Iterable[Posting]) -> List[Posting]:
    """Drop repeated ids, keeping the first."""
    seen: set = set()
    out = []
    for p in postings:
        if p.id not in seen:
            seen.add(p.id)
            out.append(p)
    return out
