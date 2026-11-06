"""Build the Phlux Robotics site: one HTML page with its data inside.

The page lists every internship the bot is tracking at the active list's
companies, open or closed in the last :data:`RECENT_DAYS`, with when each
company is expected to open for the coming summer (:mod:`phlux.robotics.forecast`).
It is static, so GitHub Pages can serve it; the bot rebuilds it after each run.

Internships are the titles the bot itself starred (``⭐️``), so the site and the
alert emails agree on what counts. Season, degree and field come from the
analytics title parser.

The new-grad view lists unstarred titles that name an engineering, robotics or
AI/ML role (:func:`phlux.analytics.titles.is_engineering_role`) and either say new
grad or early career in the title, or carry the description line the scraper
found saying the role takes new grads (``early``, see :mod:`phlux.early_career`).
They never go in an email: only starred titles do.

``template.html`` is written as a page body (title, styles, markup, scripts,
no ``<html>`` or ``<head>``) so the same file can also be previewed as a
claude.ai artifact; :func:`render` wraps it in a document for the site.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pytz

from phlux.analytics.dataset import load_industries
from phlux.analytics.sources import STORAGE
from phlux.analytics.titles import is_engineering_role, is_senior_title, parse_title
from phlux.config import load_company_list_setting
from phlux.health import find_issues, status
from phlux.lists import REPO_ROOT, select_companies
from phlux.models import Company
from phlux.scraping import CHECKED_KEY, NA_DATE, load_company_data
from phlux.utils import board_link

from . import geo, logos
from .places import STATES, Gazetteer, parse
from .forecast import Forecast, SeasonRow, forecast, openings, season_rows

logger = logging.getLogger(__name__)

TEMPLATE = Path(__file__).with_name("template.html")
DATA_MARKER = "__DATA__"
STAR = "⭐️"
# Closed internships stay on the site this long, for the "recently closed" view.
RECENT_DAYS = 30
EASTERN = pytz.timezone("US/Eastern")
ROBOTICS_TIERS = {"core", "adjacent"}
# The day the scrapes were widened to read new-grad roles too. Roles already open
# at those companies were recorded undated, so an undated new-grad role was open by
# this day (or by the season's start, if that is later).
NEW_GRAD_SINCE = date(2026, 11, 6)
# A past season with fewer dated internships than this is too thin to show
# (Summer 2025: tracking began in June 2025, so it is nearly all backlog).
PAST_MIN_DATED = 200

# The document around template.html for the site; artifact previews get the
# same reset from claude.ai.
DOCUMENT = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>
:root {{ padding-top: env(safe-area-inset-top, 0px); padding-bottom: env(safe-area-inset-bottom, 0px); }}
body {{ margin: 0; }}
img {{ max-width: 100%; }}
[hidden] {{ display: none !important; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def _closed_recently(closed: str, today: date) -> bool:
    try:
        return date.fromisoformat(closed) >= today - timedelta(days=RECENT_DAYS)
    except ValueError:  # "N/A": closed before tracking began
        return False


def _listed(entry: Any, today: date) -> bool:
    """Return True for a stored posting that is open or closed in the last :data:`RECENT_DAYS`."""
    if not isinstance(entry, dict) or not entry.get("title"):
        return False
    closed = entry.get("closed", "")
    return not closed or _closed_recently(closed, today)


def _row(name: str, entry: Dict[str, Any], title: str) -> Dict[str, Any]:
    """Return a posting as the site's row: its title plus the fields the page filters on."""
    parsed = parse_title(title)
    found = entry.get("date", NA_DATE)
    return {
        "company": name,
        "title": title,
        "url": entry.get("url", ""),
        "location": entry.get("location", ""),
        "found": "" if found == NA_DATE else found,
        "closed": entry.get("closed", ""),
        "season": parsed.season or "",
        "year": parsed.target_year or 0,
        "degree": parsed.degree or "",
        "field": parsed.domain,
        "early": "",
    }


def internship_rows(name: str, entries: Iterable[Any], today: date) -> List[Dict[str, Any]]:
    """Return the site's rows for one company's stored internships.

    Open ones and those closed in the last :data:`RECENT_DAYS`; titles lose
    their star and gain the fields the page filters on.
    """
    return [_row(name, e, e["title"][len(STAR):].strip())
            for e in entries if _listed(e, today) and e["title"].startswith(STAR)]


def new_grad_rows(name: str, entries: Iterable[Any], today: date) -> List[Dict[str, Any]]:
    """Return the site's rows for one company's new-grad engineering roles.

    Unstarred titles, open or closed lately like internships, that name an
    engineering, robotics or AI/ML role and either read as new grad, or (below
    senior level) carry a description line saying the role takes new grads,
    which the row keeps as ``early`` to show why it is listed.
    """
    rows = []
    for entry in entries:
        if not _listed(entry, today) or entry["title"].startswith(STAR):
            continue
        title = entry["title"].strip()
        if not is_engineering_role(title):
            continue
        if parse_title(title).level == "new_grad":
            rows.append(_row(name, entry, title))
        elif entry.get("early") and not is_senior_title(title):
            rows.append({**_row(name, entry, title), "early": entry["early"]})
    return rows


def season_window(cycle: int) -> tuple[date, date]:
    """Return the days a season's timeline spans: June before last through June.

    July starts most hiring for the next summer; the June before it holds the
    early birds and whatever was already open when tracking began.
    """
    return date(cycle - 1, 6, 1), date(cycle, 6, 30)


def past_seasons(rows: Iterable[SeasonRow], index: Dict[str, int], current_cycle: int) -> List[Dict[str, Any]]:
    """Return each finished season's internships for the site's past seasons view, newest first.

    Only companies in *index* (name → position in the payload's companies)
    count. A title appears once per company and season, at its first sighting.
    Postings are columns like the live ones; ``day`` counts from the season's start.
    """
    by_cycle: Dict[int, Dict[tuple, SeasonRow]] = defaultdict(dict)
    for row in sorted(rows, key=lambda r: r.day):
        start, end = season_window(row.cycle)
        if row.company in index and row.cycle < current_cycle and start <= row.day <= end:
            by_cycle[row.cycle].setdefault((row.company, row.title), row)
    fields = ["company", "title", "day", "backlog", "season", "year", "degree", "field"]
    seasons = []
    for cycle in sorted(by_cycle, reverse=True):
        found = list(by_cycle[cycle].values())
        if sum(not r.backlog for r in found) < PAST_MIN_DATED:
            continue
        start, end = season_window(cycle)
        seasons.append({
            "cycle": cycle,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "fields": fields,
            "rows": [[index[r.company], r.title, (r.day - start).days, int(r.backlog), r.season,
                      r.target_year, r.degree, r.domain] for r in found],
        })
    return seasons


class Mapper:
    """Turns location text into the site's map references, numbering towns as they appear.

    A posting's ``where`` is a list of: town indexes into :attr:`towns`
    (``[name, state, x, y]``), bare state codes where no town is known, and
    ``"remote"``, ``"abroad"`` or ``"vague"``; it is empty when the board gave no
    location at all.
    """

    def __init__(self, gazetteer: Gazetteer):
        self.gazetteer = gazetteer
        self.towns: List[list] = []
        self._index: Dict[tuple, int] = {}
        self._cache: Dict[str, list] = {}

    def where(self, location: str) -> list:
        if location in self._cache:
            return self._cache[location]
        found = parse(location, self.gazetteer)
        refs: list = []
        for state, town in found.places:
            point = self.gazetteer.point(state, town) if town else None
            if point is None:
                refs.append(state)
                continue
            key = (state, town.casefold())
            if key not in self._index:
                self._index[key] = len(self.towns)
                self.towns.append([town, state, *point])
            refs.append(self._index[key])
        refs += [flag for flag in ("remote", "abroad", "vague") if getattr(found, flag)]
        if location and not refs:
            refs.append("vague")
        self._cache[location] = list(dict.fromkeys(refs))
        return self._cache[location]


def build_payload(
    storage: Dict[str, Any],
    companies: List[Company],
    forecasts: Dict[str, Forecast],
    industries: Dict[str, Dict[str, str]],
    icons: Dict[str, str],
    now: datetime,
    history: Iterable[SeasonRow] = (),
    gazetteer: Optional[Gazetteer] = None,
    state_paths: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Assemble everything the page shows.

    Args:
        storage: ``storage.json`` contents.
        companies: The active list's companies, in list order.
        forecasts: Each company's opening forecast, by name.
        industries: ``industries.csv`` tagging, by name.
        icons: Each company's logo, as a URL or ``data:`` URI, by name.
        now: The build time.
        history: Past internships (:func:`phlux.robotics.forecast.season_rows`)
            for the past seasons view.
        gazetteer: Town lookup for placing postings on the map; without it
            (or *state_paths*) the page has no map.
        state_paths: Each state's outline, from :func:`phlux.robotics.geo.load_states`.
    """
    today = now.date()
    stored = storage.get("companies", {})
    checked = storage.get(CHECKED_KEY, {})
    issues = {i.company: i for i in find_issues(storage, [c.name for c in companies], today)}
    company_rows, postings, new_grad = [], [], []
    for company in companies:
        tags = industries.get(company.name, {})
        tier = tags.get("robotics_tier", "core")
        fc = forecasts.get(company.name)
        company_rows.append({
            "name": company.name,
            "segment": tags.get("robotics_segment", ""),
            "robotics": tier in ROBOTICS_TIERS,
            "careers": board_link(company.link),
            "icon": icons.get(company.name, ""),
            "checked": checked.get(company.name, ""),
            "health": status(issues.get(company.name)),
            "forecast": fc.as_dict() if fc else None,
        })
        postings += internship_rows(company.name, stored.get(company.name, []), today)
        new_grad += new_grad_rows(company.name, stored.get(company.name, []), today)

    index = {c["name"]: i for i, c in enumerate(company_rows)}
    mapper = Mapper(gazetteer) if gazetteer and state_paths else None
    for p in postings + new_grad:
        p["where"] = mapper.where(p["location"]) if mapper else []
    fields = ["company", "title", "url", "location", "found", "closed", "season", "year", "degree", "field", "where",
              "early"]

    # Columns rather than one object per posting: the page embeds this.
    def columns(rows: List[Dict[str, Any]]) -> List[list]:
        return [[index[p["company"]] if f == "company" else p[f] for f in fields] for p in rows]

    cycle = next(iter(forecasts.values())).cycle if forecasts else today.year + 1
    return {
        "generated": now.isoformat(timespec="minutes"),
        "today": today.isoformat(),
        "cycle": cycle,
        "recentDays": RECENT_DAYS,
        # Undated postings were already open on the season's first scrape.
        "seasonStart": STORAGE.epoch_start.isoformat(),
        "companies": company_rows,
        "fields": fields,
        "postings": columns(postings),
        # Same fields as postings.
        "newGrad": {
            "since": max(STORAGE.epoch_start, NEW_GRAD_SINCE).isoformat(),
            "postings": columns(new_grad),
        },
        "past": past_seasons(history, index, cycle),
        "map": {"width": geo.WIDTH, "height": geo.HEIGHT, "states": state_paths, "names": STATES,
                "towns": mapper.towns} if mapper else None,
    }


def render(payload: Dict[str, Any], template: str, document: bool = True) -> str:
    """Return the page with *payload* inside, as a full document or a bare body.

    Raises:
        ValueError: If the template has no :data:`DATA_MARKER`.
    """
    if DATA_MARKER not in template:
        raise ValueError(f"template has no {DATA_MARKER} marker")
    # A literal "</script>" in a title would close the data block early, and
    # NaN (pandas' missing value) isn't JSON: the page would fail to load.
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    body = template.replace(DATA_MARKER, data)
    return DOCUMENT.format(body=body) if document else body


def load_history(names: List[str], today: date) -> tuple[Dict[str, Forecast], List[SeasonRow]]:
    """Return *names*' forecasts and every past internship, from the full scrape history.

    Forecasts follow summer internships only; the past seasons view shows
    every season's.
    """
    from phlux.analytics import build_dataset

    df = build_dataset(today=today)
    forecasts = {f.company: f for f in forecast(names, openings(df), today)}
    return forecasts, season_rows(df, summer_only=False, keep_uncertain=True)


def build_site(out_dir: Path, now: Optional[datetime] = None, document: bool = True,
               storage_path: Path = REPO_ROOT / "storage.json") -> Path:
    """Write ``index.html`` for the active list into *out_dir* and return its path."""
    now = now or datetime.now(EASTERN)
    storage = json.loads(storage_path.read_text(encoding="utf-8"))
    companies = list({c.name: c for c in select_companies(
        load_company_data(REPO_ROOT / "companies.csv"), load_company_list_setting())}.values())
    icons = {c.name: logos.data_uri(c.name) for c in companies}
    forecasts, history = load_history([c.name for c in companies], now.date())
    payload = build_payload(storage, companies, forecasts, load_industries(), icons, now, history,
                            Gazetteer(geo.load_places()), geo.load_states())
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "index.html"
    path.write_text(render(payload, TEMPLATE.read_text(encoding="utf-8"), document), encoding="utf-8")
    logger.info("wrote %s: %d companies, %d internships, %d new-grad roles", path, len(payload["companies"]),
                len(payload["postings"]), len(payload["newGrad"]["postings"]))
    return path
