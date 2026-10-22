"""Jane Street open roles (``janestreet.com/join-jane-street/open-roles/?type=...``).

The open-roles page builds its list in the browser from two JSON files, and
this adapter does the same:

* ``/jobs/main.json``: every open position (``id``, ``position``, ``availability``,
  ``city``, ``category``, ``team``, ``duration``).
* ``/static/position-directories.json``: the ids the page actually lists; a
  position missing from it is not shown.

The link's filters are the page's own: ``type`` (``internship``, ``co-op``,
``full-time-new-grad``, ``students-and-new-grads``, ``experienced-candidates``...),
``location`` (``new-york``, ``london``...), ``department``, ``season-duration``,
``team`` and ``position``. A value the page would not recognise is refused
rather than read as "everything".

The page also lists last season's internships that are not open yet, marked
"not currently accepting applications" (from ``/jobs/internships.json``, which
has no ids). Those are not postings and are left out; when one opens, it shows
up in main.json with an id and is reported as new.
"""
from __future__ import annotations

import re
from typing import Dict, List
from urllib.parse import parse_qsl, urlsplit

from ..models import Posting
from .base import adapter, get

SITE = "https://www.janestreet.com"
MAIN = SITE + "/jobs/main.json"
DIRECTORY = SITE + "/static/position-directories.json"

CITY_NAMES = {
    "NYC": "New York", "LDN": "London", "HKG": "Hong Kong", "AMS": "Amsterdam",
    "CHI": "Chicago", "SGP": "Singapore", "MUM": "Mumbai", "SHA": "Shanghai",
    "PHL": "Philadelphia", "SF": "San Francisco", "ATX": "Austin", "NYC/HKG": "New York/Hong Kong",
}
EXPERIENCED = "Full-Time: Experienced"
NEW_GRAD = "Full-Time: New Grad"
EXPERIENCED_ALIASES = {"experienced-candidates", "full-time-experienced"}
STUDENT_ALIASES = {"students-and-new-grads"}


def simplify(value: str) -> str:
    """Normalize a field the way the page does before showing or matching it."""
    return re.sub(r"\s\s+", " ", value.strip().replace("&", "and"))


def paramify(value: str) -> str:
    """Return the URL form of a filter value (``New York`` -> ``new-york``)."""
    value = value.lower().strip().replace(":", "").replace(" - ", " ").replace("/", " ").replace(",", "")
    return "-".join(value.split(" "))


def paramify_strict(value: str) -> str:
    """Return the URL form of a position title, as the page's ``position`` filter writes it."""
    value = re.sub(r"[^a-zA-Z ]", "", value.replace("-", " ", 1))
    return re.sub(r"\s", "-", re.sub(r"\s\s+", " ", value)).lower()


def job_type(availability: str) -> str:
    """Map main.json's ``availability`` to the page's job type."""
    lowered = availability.lower()
    if "full-time" in lowered:
        return availability
    if "co-op" in lowered:
        return "Co-Op"
    if "industrial placement year" in lowered:
        return "Industrial Placement Year"
    return "Internship"


def _jobs() -> List[Dict[str, str]]:
    """Return the positions the page lists, with the page's field names and values."""
    listed = {str(i) for i in get(DIRECTORY).json()}
    jobs = []
    for raw in get(MAIN).json():
        if str(raw["id"]) not in listed:
            continue
        job = {key: simplify(value) if isinstance(value, str) else ("" if value is None else value)
               for key, value in raw.items()}
        job["location"] = job.pop("city", "")
        job["department"] = job.pop("category", "")
        job["type"] = job_type(job.pop("availability", ""))
        jobs.append(job)
    return jobs


def _choose(param: str, value: str, options: Dict[str, List[str]]) -> List[str]:
    value = value.strip().lower()
    if value not in options:
        raise ValueError(f"Unknown Jane Street {param} {value!r}; expected one of {sorted(options)}")
    return options[value]


def select(jobs: List[Dict[str, str]], url: str) -> List[Dict[str, str]]:
    """Return the *jobs* the open-roles page shows for *url*'s filters.

    Raises:
        ValueError: For a filter value the page does not offer.
    """
    params = dict(parse_qsl(urlsplit(url).query))
    wanted: Dict[str, List[str]] = {}

    kind = params.get("type", "").strip().lower()
    if kind and kind != "all-types":
        experienced = kind in EXPERIENCED_ALIASES or kind == paramify(EXPERIENCED)
        types = [EXPERIENCED] if experienced else [NEW_GRAD] + sorted(
            {j["type"] for j in jobs if "Full-Time" not in j["type"]})
        options = {paramify(t): [t] for t in types}
        options.update({alias: types for alias in (EXPERIENCED_ALIASES if experienced else STUDENT_ALIASES)})
        wanted["type"] = _choose("type", kind, options)

    locations = sorted({j["location"] for j in jobs if j["location"] in CITY_NAMES})
    if params.get("location", "all-locations") != "all-locations":
        options = {paramify(CITY_NAMES[loc]): [loc] for loc in locations}
        wanted["location"] = _choose("location", params["location"], options)

    if params.get("department", "all-departments") != "all-departments":
        department = params["department"].strip().lower()
        if department == "trading-and-research":
            department = "trading-research-and-machine-learning"
        options = {paramify(j["department"]): [j["department"]] for j in jobs if j["department"]}
        wanted["department"] = _choose("department", department, options)

    for param, field in (("season-duration", "duration"), ("team", "team")):
        if params.get(param, f"all-{field}s") != f"all-{field}s":
            options = {paramify(j[field]): [j[field]] for j in jobs if j.get(field)}
            wanted[field] = _choose(param, params[param], options)

    if params.get("position", "all-positions") != "all-positions":
        names = {p.strip().lower() for p in params["position"].split(",")}
        wanted["position"] = [j["position"] for j in jobs if paramify_strict(j["position"]) in names]

    return [j for j in jobs if all(j.get(field) in values for field, values in wanted.items())]


@adapter("janestreet")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the open positions the Jane Street open-roles link shows."""
    return [Posting(f"janestreet:{j['id']}", j["position"]) for j in select(_jobs(), url)]
