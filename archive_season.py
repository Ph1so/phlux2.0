"""Move storage.json into prev_years/ and start a fresh season.

Usage::

    python archive_season.py 2026

writes ``prev_years/2026_internships.json`` and resets ``storage.json``. Any bare
``M/D`` dates are converted to ISO on the way out, using the epoch registered for
``storage.json`` in :mod:`phlux.analytics.sources` to recover the year.

The fresh storage file has seeding turned on, so the first scrape records every
posting already live as backlog (dated ``"N/A"``) instead of emailing all of them
as new. Afterwards, register the archive in ``phlux/analytics/sources.py`` and move
``STORAGE.epoch_start`` to today.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Dict

from phlux.analytics.dates import resolve_company_dates
from phlux.analytics.sources import PREV_YEARS_DIR, STORAGE
from phlux.scraping import NA_DATE, SEED_FLAG


def to_iso(companies: Dict[str, Any], epoch_start: date, epoch_end: date) -> Dict[str, Any]:
    """Return a copy of *companies* with every dated posting stamped ``YYYY-MM-DD``.

    ``"N/A"`` stays as-is, and legacy bare-string postings become ``{title, date}``.
    """
    out = {}
    for name, postings in companies.items():
        rows = [p if isinstance(p, dict) else {"title": p, "date": NA_DATE} for p in postings]
        resolved = resolve_company_dates([r.get("date", NA_DATE) for r in rows], epoch_start, epoch_end, name)
        out[name] = [
            {**row, "date": NA_DATE if res.raw == NA_DATE else res.value.isoformat()}
            for row, res in zip(rows, resolved)
        ]
    return out


def archive(
    label: str,
    storage_path: Path = STORAGE.path,
    epoch_start: date = STORAGE.epoch_start,
    today: date | None = None,
) -> Path:
    """Archive *storage_path* as ``prev_years/<label>_internships.json`` and reset it.

    *epoch_start* is the day the outgoing file began, used to date bare ``M/D`` rows.

    Raises:
        FileExistsError: If the archive file already exists.
    """
    today = today or date.today()
    target = PREV_YEARS_DIR / f"{label}_internships.json"
    if target.exists():
        raise FileExistsError(f"{target} already exists")

    data = json.loads(storage_path.read_text(encoding="utf-8"))
    companies = to_iso(data.get("companies", {}), epoch_start, today)

    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps({"companies": companies}, indent=2), encoding="utf-8")
    storage_path.write_text(json.dumps({SEED_FLAG: True, "companies": {}}, indent=2), encoding="utf-8")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("label", help='archive name prefix, e.g. "2026"')
    args = parser.parse_args()
    target = archive(args.label)
    print(f"Archived to {target}; storage.json reset with seeding on.")
    print("Next: register it in phlux/analytics/sources.py and move STORAGE.epoch_start to today.")


if __name__ == "__main__":
    main()
