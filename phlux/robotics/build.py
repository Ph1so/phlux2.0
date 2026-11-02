"""Build the Phlux Robotics site: one HTML page with its data inside.

The page lists every internship the bot is tracking at the active list's
companies, open or closed in the last :data:`RECENT_DAYS`, with when each
company is expected to open for the coming summer (:mod:`phlux.robotics.forecast`).
It is static, so GitHub Pages can serve it; the bot rebuilds it after each run.

Internships are the titles the bot itself starred (``⭐️``), so the site and the
alert emails agree on what counts. Season, degree and field come from the
analytics title parser.

``template.html`` is written as a page body (title, styles, markup, scripts,
no ``<html>`` or ``<head>``) so the same file can also be previewed as a
claude.ai artifact; :func:`render` wraps it in a document for the site.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pytz

from phlux.analytics.dataset import load_industries
from phlux.analytics.sources import STORAGE
from phlux.analytics.titles import parse_title
from phlux.config import load_company_list_setting
from phlux.health import find_issues, status
from phlux.lists import REPO_ROOT, select_companies
from phlux.models import Company
from phlux.scraping import CHECKED_KEY, NA_DATE, load_company_data
from phlux.utils import board_link

from . import logos
from .forecast import Forecast, forecast, openings

logger = logging.getLogger(__name__)

TEMPLATE = Path(__file__).with_name("template.html")
DATA_MARKER = "__DATA__"
STAR = "⭐️"
# Closed internships stay on the site this long, for the "recently closed" view.
RECENT_DAYS = 30
EASTERN = pytz.timezone("US/Eastern")
ROBOTICS_TIERS = {"core", "adjacent"}

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


def internship_rows(name: str, entries: Iterable[Any], today: date) -> List[Dict[str, Any]]:
    """Return the site's rows for one company's stored internships.

    Open ones and those closed in the last :data:`RECENT_DAYS`; titles lose
    their star and gain the fields the page filters on.
    """
    rows = []
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("title", "").startswith(STAR):
            continue
        closed = entry.get("closed", "")
        if closed and not _closed_recently(closed, today):
            continue
        title = entry["title"][len(STAR):].strip()
        parsed = parse_title(title)
        found = entry.get("date", NA_DATE)
        rows.append({
            "company": name,
            "title": title,
            "url": entry.get("url", ""),
            "location": entry.get("location", ""),
            "found": "" if found == NA_DATE else found,
            "closed": closed,
            "season": parsed.season or "",
            "year": parsed.target_year or 0,
            "degree": parsed.degree or "",
            "field": parsed.domain,
        })
    return rows


def build_payload(
    storage: Dict[str, Any],
    companies: List[Company],
    forecasts: Dict[str, Forecast],
    industries: Dict[str, Dict[str, str]],
    icons: Dict[str, str],
    now: datetime,
) -> Dict[str, Any]:
    """Assemble everything the page shows.

    Args:
        storage: ``storage.json`` contents.
        companies: The active list's companies, in list order.
        forecasts: Each company's opening forecast, by name.
        industries: ``industries.csv`` tagging, by name.
        icons: Each company's logo, as a URL or ``data:`` URI, by name.
        now: The build time.
    """
    today = now.date()
    stored = storage.get("companies", {})
    checked = storage.get(CHECKED_KEY, {})
    issues = {i.company: i for i in find_issues(storage, [c.name for c in companies], today)}
    company_rows, postings = [], []
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

    # Columns rather than one object per posting: the page embeds this.
    index = {c["name"]: i for i, c in enumerate(company_rows)}
    fields = ["company", "title", "url", "location", "found", "closed", "season", "year", "degree", "field"]
    return {
        "generated": now.isoformat(timespec="minutes"),
        "today": today.isoformat(),
        "cycle": next(iter(forecasts.values())).cycle if forecasts else today.year + 1,
        "recentDays": RECENT_DAYS,
        # Undated postings were already open on the season's first scrape.
        "seasonStart": STORAGE.epoch_start.isoformat(),
        "companies": company_rows,
        "fields": fields,
        "postings": [[index[p["company"]] if f == "company" else p[f] for f in fields] for p in postings],
    }


def render(payload: Dict[str, Any], template: str, document: bool = True) -> str:
    """Return the page with *payload* inside, as a full document or a bare body.

    Raises:
        ValueError: If the template has no :data:`DATA_MARKER`.
    """
    if DATA_MARKER not in template:
        raise ValueError(f"template has no {DATA_MARKER} marker")
    # A literal "</script>" in a title would close the data block early.
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    body = template.replace(DATA_MARKER, data)
    return DOCUMENT.format(body=body) if document else body


def load_forecasts(names: List[str], today: date) -> Dict[str, Forecast]:
    """Forecast *names* from the full scrape history."""
    from phlux.analytics import build_dataset

    history = openings(build_dataset(today=today))
    return {f.company: f for f in forecast(names, history, today)}


def build_site(out_dir: Path, now: Optional[datetime] = None, document: bool = True,
               storage_path: Path = REPO_ROOT / "storage.json") -> Path:
    """Write ``index.html`` for the active list into *out_dir* and return its path."""
    now = now or datetime.now(EASTERN)
    storage = json.loads(storage_path.read_text(encoding="utf-8"))
    companies = list({c.name: c for c in select_companies(
        load_company_data(REPO_ROOT / "companies.csv"), load_company_list_setting())}.values())
    icons = {c.name: logos.data_uri(c.name) for c in companies}
    payload = build_payload(
        storage, companies, load_forecasts([c.name for c in companies], now.date()),
        load_industries(), icons, now,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "index.html"
    path.write_text(render(payload, TEMPLATE.read_text(encoding="utf-8"), document), encoding="utf-8")
    logger.info("wrote %s: %d companies, %d internships", path, len(payload["companies"]), len(payload["postings"]))
    return path
