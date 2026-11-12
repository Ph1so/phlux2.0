"""US map geometry for the site: state outlines and where each town sits on them.

Both come from public data and are committed under ``phlux/site/geo/`` so a
site build needs no network:

* ``us_states.json``: each state's outline as an SVG path, from the ``us-atlas``
  package's ``states-albers-10m`` (Census boundaries already projected with
  d3's ``geoAlbersUsa``, scale 1300, into a 975 × 610 box).
* ``us_places.json``: every Census place (town, city, CDP) as ``x, y`` in that
  same box, from the Census Gazetteer, projected here with the same
  ``geoAlbersUsa`` so a town's dot lands on its state.

``python -m phlux.site geo`` downloads both and rewrites the files; they only
change when the Census does.
"""
from __future__ import annotations

import io
import json
import math
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from phlux.adapters.base import get

GEO_DIR = Path(__file__).with_name("geo")
STATES_FILE = GEO_DIR / "us_states.json"
PLACES_FILE = GEO_DIR / "us_places.json"
ATLAS_URL = "https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-albers-10m.json"
GAZETTEER_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_place_national.zip"
WIDTH, HEIGHT = 975, 610

# Census FIPS codes of the states and DC, with their postal codes.
FIPS = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE",
    "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA",
    "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM",
    "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY",
}
# The legal-area word the Gazetteer appends to each place name ("Austin city").
_LSAD = re.compile(r"\s+(city and borough|consolidated government.*|metro(politan)? government.*|"
                   r"unified government.*|urban county|city|town|township|village|borough|CDP|municipality|"
                   r"comunidad|zona urbana)$", re.IGNORECASE)


# ── Projection: d3.geoAlbersUsa().scale(1300).translate([487.5, 305]) ──────

class _ConicEqualArea:
    """d3's ``geoConicEqualArea`` with its rotate, center, parallels, scale and translate."""

    def __init__(self, rotate: float, center: Tuple[float, float], parallels: Tuple[float, float],
                 scale: float, translate: Tuple[float, float]):
        y0, y1 = (math.radians(p) for p in parallels)
        sy0 = math.sin(y0)
        self.n = (sy0 + math.sin(y1)) / 2
        self.c = 1 + sy0 * (2 * self.n - sy0)
        self.r0 = math.sqrt(self.c) / self.n
        self.rotate = math.radians(rotate)
        self.k = scale
        cx, cy = self._raw(math.radians(center[0]), math.radians(center[1]))
        self.dx = translate[0] - scale * cx
        self.dy = translate[1] + scale * cy

    def _raw(self, lam: float, phi: float) -> Tuple[float, float]:
        r = math.sqrt(max(0.0, self.c - 2 * self.n * math.sin(phi))) / self.n
        return r * math.sin(lam * self.n), self.r0 - r * math.cos(lam * self.n)

    def __call__(self, lon: float, lat: float) -> Tuple[float, float]:
        lam = math.radians(lon) + self.rotate
        lam = (lam + math.pi) % (2 * math.pi) - math.pi
        x, y = self._raw(lam, math.radians(lat))
        return self.dx + self.k * x, self.dy - self.k * y


def albers_usa(lon: float, lat: float, scale: float = 1300, translate=(487.5, 305)) -> Optional[Tuple[float, float]]:
    """Project a point as ``d3.geoAlbersUsa`` does, Alaska and Hawaii in their insets; None outside them."""
    tx, ty = translate
    if 51 <= lat <= 72 and (lon <= -129 or lon >= 172):
        p = _ConicEqualArea(154, (-2, 58.5), (55, 65), 0.35 * scale, (tx - 0.307 * scale, ty + 0.201 * scale))
    elif 18 <= lat <= 23 and -162 <= lon <= -154:
        p = _ConicEqualArea(157, (-3, 19.9), (8, 18), scale, (tx - 0.205 * scale, ty + 0.212 * scale))
    elif 23 <= lat <= 50 and -125 <= lon <= -66:
        p = _ConicEqualArea(96, (-0.6, 38.7), (29.5, 45.5), scale, translate)
    else:
        return None
    return p(lon, lat)


# ── State outlines from TopoJSON ──────────────────────────────────────────

def _arcs(topology: dict) -> List[List[Tuple[float, float]]]:
    """Decode a quantized TopoJSON's delta-encoded arcs into absolute points."""
    (sx, sy), (tx, ty) = topology["transform"]["scale"], topology["transform"]["translate"]
    out = []
    for arc in topology["arcs"]:
        x = y = 0
        points = []
        for dx, dy in arc:
            x, y = x + dx, y + dy
            points.append((x * sx + tx, y * sy + ty))
        out.append(points)
    return out


def _ring(arcs: List[List[Tuple[float, float]]], indexes: List[int]) -> List[Tuple[float, float]]:
    points: List[Tuple[float, float]] = []
    for i in indexes:
        arc = arcs[i] if i >= 0 else arcs[~i][::-1]
        points.extend(arc if not points else arc[1:])
    return points


def _path(rings: List[List[Tuple[float, float]]]) -> str:
    """Return an SVG path for *rings*, at whole pixels, dropping repeated points."""
    parts = []
    for ring in rings:
        pts: List[Tuple[int, int]] = []
        for x, y in ring:
            p = (round(x), round(y))
            if not pts or p != pts[-1]:
                pts.append(p)
        if len(pts) >= 3:
            parts.append("M" + "L".join(f"{x},{y}" for x, y in pts) + "Z")
    return "".join(parts)


def state_paths(topology: dict) -> Dict[str, str]:
    """Return each state's outline as an SVG path, keyed by postal code."""
    arcs = _arcs(topology)
    paths = {}
    for geometry in topology["objects"]["states"]["geometries"]:
        code = FIPS.get(geometry.get("id"))
        if not code:
            continue
        polygons = geometry["arcs"] if geometry["type"] == "MultiPolygon" else [geometry["arcs"]]
        paths[code] = _path([_ring(arcs, ring) for polygon in polygons for ring in polygon])
    return paths


# ── Places from the Census Gazetteer ──────────────────────────────────────

def place_name(name: str) -> str:
    """Return a Gazetteer place name as people write it: "Austin city" → "austin"."""
    return _LSAD.sub("", name).strip().casefold()


def gazetteer_places(text: str) -> Dict[str, Dict[str, List[int]]]:
    """Return ``{state: {place name: [x, y]}}`` from the Gazetteer's tab-separated text."""
    lines = text.splitlines()
    header = [h.strip() for h in lines[0].split("\t")]
    col = {h: i for i, h in enumerate(header)}
    out: Dict[str, Dict[str, List[int]]] = {}
    for line in lines[1:]:
        cells = line.split("\t")
        if len(cells) < len(header):
            continue
        state = cells[col["USPS"]].strip()
        if state not in FIPS.values():
            continue
        xy = albers_usa(float(cells[col["INTPTLONG"]]), float(cells[col["INTPTLAT"]]))
        if xy is None:
            continue
        # The first of several same-named places in a state wins (the Gazetteer lists cities before CDPs rarely).
        out.setdefault(state, {}).setdefault(place_name(cells[col["NAME"]]), [round(xy[0]), round(xy[1])])
    return out


def refresh() -> Tuple[int, int]:
    """Download both sources and rewrite the committed files; return (states, places)."""
    GEO_DIR.mkdir(parents=True, exist_ok=True)
    states = state_paths(get(ATLAS_URL).json())
    STATES_FILE.write_text(json.dumps(states, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    archive = zipfile.ZipFile(io.BytesIO(get(GAZETTEER_URL).content))
    text = archive.read(next(n for n in archive.namelist() if n.endswith(".txt"))).decode("utf-8", "replace")
    places = gazetteer_places(text)
    PLACES_FILE.write_text(json.dumps(places, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    return len(states), sum(len(v) for v in places.values())


def load_states() -> Dict[str, str]:
    return json.loads(STATES_FILE.read_text(encoding="utf-8"))


def load_places() -> Dict[str, Dict[str, List[int]]]:
    return json.loads(PLACES_FILE.read_text(encoding="utf-8"))
