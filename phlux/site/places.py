"""Read a posting's location text into places on the US map.

Job boards write locations every way: "Santa Clara, CA", "US, CA, Santa Clara",
"Warren, Michigan, United States of America", "Cambridge, MA USA", "USA
Wilmington, MA - HQ", "Austin, Texas, United States; South San Francisco,
California, United States", "Pittsburgh, PA +2", "Remote - US". :func:`parse`
turns one into the US places it names (state, and town when it gives one), and
says whether it is remote, outside the US, or too vague to place ("3
Locations", "Flexible - Any SpaceX Site").

A town is found in the Census places for its state (see :mod:`phlux.site.geo`).
Some hubs are often written without a state ("San Francisco", "Boston"), so
:data:`HUBS` names their state. Any other bare town isn't placed: too many
foreign cities share a name with some small US place (Munich, North Dakota).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
_BY_NAME = {name.casefold(): code for code, name in STATES.items()}
_BY_NAME["washington dc"] = _BY_NAME["washington d.c."] = _BY_NAME["d.c."] = "DC"

US_WORDS = {"us", "usa", "u.s.", "u.s.a.", "united states", "united states of america", "america"}
# Towns written without their state often enough to name it here. Where a name
# exists in several states, this is the one robotics postings mean.
HUBS = {
    "san francisco": "CA", "south san francisco": "CA", "bay area": "CA", "san francisco bay area": "CA",
    "silicon valley": "CA", "sunnyvale": "CA", "mountain view": "CA", "palo alto": "CA", "san jose": "CA",
    "santa clara": "CA", "menlo park": "CA", "redwood city": "CA", "san mateo": "CA", "foster city": "CA",
    "los angeles": "CA", "san diego": "CA", "irvine": "CA", "oakland": "CA", "berkeley": "CA", "fremont": "CA",
    "cupertino": "CA", "hawthorne": "CA", "torrance": "CA", "costa mesa": "CA", "long beach": "CA",
    "boston": "MA", "cambridge": "MA", "somerville": "MA", "waltham": "MA", "burlington": "MA", "woburn": "MA",
    "new york": "NY", "new york city": "NY", "nyc": "NY", "brooklyn": "NY", "manhattan": "NY",
    "seattle": "WA", "redmond": "WA", "bellevue": "WA", "kirkland": "WA",
    "austin": "TX", "houston": "TX", "dallas": "TX", "pittsburgh": "PA", "philadelphia": "PA",
    "detroit": "MI", "ann arbor": "MI", "chicago": "IL", "denver": "CO", "boulder": "CO", "atlanta": "GA",
    "washington": "DC", "arlington": "VA", "huntsville": "AL", "phoenix": "AZ", "salt lake city": "UT",
    "miami": "FL", "honolulu": "HI", "portland": "OR", "minneapolis": "MN", "raleigh": "NC",
    "el segundo": "CA", "culver city": "CA", "santa monica": "CA", "pasadena": "CA", "burbank": "CA",
    "carson": "CA", "san carlos": "CA", "milpitas": "CA", "san bruno": "CA", "emeryville": "CA",
}
# Regions written as places, and the town their dot sits on.
REGION_TOWNS = {"bay area": "San Francisco", "san francisco bay area": "San Francisco", "silicon valley": "San Jose"}
# Cities abroad that postings name on their own.
ABROAD = {
    "london", "paris", "munich", "berlin", "stuttgart", "hamburg", "dublin", "zurich", "geneva", "amsterdam",
    "toronto", "vancouver", "montreal", "waterloo", "tokyo", "seoul", "singapore", "shanghai", "beijing",
    "shenzhen", "hong kong", "taipei", "bangalore", "bengaluru", "hyderabad", "pune", "tel aviv", "haifa",
    "jerusalem", "sydney", "melbourne", "stockholm", "copenhagen", "oslo", "warsaw", "krakow", "madrid",
    "barcelona", "milan", "lisbon", "prague", "vienna", "brussels", "mexico city", "sao paulo",
}
# Census names that differ from how people write the town.
ALIASES = {("HI", "honolulu"): "urban honolulu", ("NY", "new york city"): "new york",
           ("NY", "nyc"): "new york", ("NY", "manhattan"): "new york", ("NY", "brooklyn"): "new york"}
# Words around a town name that aren't part of it: "Waltham Office (POST)", "Wilmington, MA - HQ".
_NOISE = re.compile(r"\(.*?\)|\b(?:hq|headquarters|office|campus|site|hybrid|on-?site|in-?office)\b",
                    re.IGNORECASE)
_US_TAIL = re.compile(r"\s+(?:usa|us|u\.s\.a?\.?|united states(?: of america)?)$", re.IGNORECASE)
_MORE = re.compile(r"\s*\+\s*(\d+)\s*$")
_COUNT_ONLY = re.compile(r"^\d+\s+locations?$", re.IGNORECASE)
_ZIP = re.compile(r"\b\d{5}(?:-\d{4})?\b")


@dataclass
class Located:
    """Where one location text points: US places, plus what couldn't be placed."""

    places: List[Tuple[str, str]] = field(default_factory=list)  # (state, town or "")
    remote: bool = False
    abroad: bool = False
    vague: bool = False
    more: int = 0  # further locations the text only counts ("+2")


def _clean(text: str) -> str:
    return " ".join(_NOISE.sub(" ", text).replace("–", "-").split()).strip(" ,-/")


def _state(token: str) -> Optional[str]:
    """Return the state a token names: "CA", "California", "CA 94043", "MA USA", "California USA"."""
    token = _US_TAIL.sub("", _ZIP.sub("", _clean(token)).strip(" ,-")).strip(" ,-")
    if token.casefold() in _BY_NAME:
        return _BY_NAME[token.casefold()]
    first = token.split(" ")[0] if token else ""
    if first.upper() in STATES and (first.isupper() or len(token) == 2):
        rest = token[len(first):].strip(" ,-").casefold()
        if not rest or rest in US_WORDS:
            return first.upper()
    return None


class Gazetteer:
    """Town lookup by state, from :func:`phlux.site.geo.load_places`."""

    def __init__(self, places: Dict[str, Dict[str, List[int]]]):
        self.places = places
        self.states_of: Dict[str, List[str]] = {}
        for state, towns in places.items():
            for town in towns:
                self.states_of.setdefault(town, []).append(state)

    def point(self, state: str, town: str) -> Optional[List[int]]:
        key = ALIASES.get((state, town.casefold()), town.casefold())
        return self.places.get(state, {}).get(key)

    def is_us_town(self, town: str) -> bool:
        return town.casefold() in self.states_of


def _one(part: str, gazetteer: Gazetteer, out: Located) -> None:
    """Add one location (no ";") to *out*."""
    match = _MORE.search(part)
    if match:
        out.more += int(match.group(1))
        part = part[:match.start()]
    part = part.strip()
    if not part:
        return
    if _COUNT_ONLY.match(part):
        out.vague = True
        out.more += int(part.split()[0])
        return
    low = part.casefold()
    if "remote" in low or "anywhere" in low:
        out.remote = True
        return
    # "United States - California - San Jose" reads like "United States, California, San Jose".
    if " - " in part and any(w in low for w in ("united states", "usa")):
        part = part.replace(" - ", ", ")
    tokens = [t.strip() for t in part.split(",") if t.strip()]
    # "USA Wilmington" → "Wilmington"; a country word on its own is dropped.
    tokens = [re.sub(r"^(?:usa|us|u\.s\.)\s+", "", t, flags=re.IGNORECASE) for t in tokens]
    us = any(t.casefold() in US_WORDS for t in tokens)
    tokens = [t for t in tokens if t.casefold() not in US_WORDS]
    found = [(i, s) for i, s in ((i, _state(t)) for i, t in enumerate(tokens)) if s]
    if found:
        # The state is usually written last: "Washington, DC", "New York, NY".
        i, state = found[-1]
        towns = [_clean(t) for j, t in enumerate(tokens) if j != i]
        town = next((t for t in towns if gazetteer.point(state, t)), "")
        out.places.append((state, town))
        return
    if len(tokens) == 1:
        raw = " ".join(tokens[0].split()).casefold()
        town = _clean(tokens[0])
        for name in (raw, town.casefold()):
            if name in HUBS:
                town = REGION_TOWNS.get(name, town)
                out.places.append((HUBS[name], town if gazetteer.point(HUBS[name], town) else ""))
                return
        # A bare name is abroad only when it surely is; "Flexible - Any Site" is just vague.
        if not us and (town.casefold() in ABROAD or not town.isascii()):
            out.abroad = True
        else:
            out.vague = True
        return
    if us:
        out.vague = True
    elif tokens:
        out.abroad = True


def parse(text: str, gazetteer: Gazetteer) -> Located:
    """Return the US places, remoteness and so on that a location *text* names."""
    out = Located()
    for part in re.split(r"[;|]|\s+or\s+", text or ""):
        _one(part, gazetteer, out)
    if not (out.places or out.remote or out.abroad or out.vague or out.more) and (text or "").strip():
        out.vague = True
    return out
