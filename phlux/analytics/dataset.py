"""Assemble the raw job-history files into one tidy, analysis-ready table.

Runs the three steps in order — load, resolve dates, parse titles, flag artifacts —
and emits a row per posting plus a per-company data-health summary.

Usage:
    python -m phlux.analytics [--out-dir analysis] [--format csv|parquet]
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from phlux.analytics import clean, titles
from phlux.analytics.dates import resolve_company_dates
from phlux.analytics.sources import REPO_ROOT, Source, iter_sources

logger = logging.getLogger(__name__)

COMPANIES_CSV = REPO_ROOT / "companies.csv"
INDUSTRIES_CSV = REPO_ROOT / "industries.csv"
DEFAULT_OUT_DIR = REPO_ROOT / "analysis"
DASHBOARD_TEMPLATE = REPO_ROOT / "dashboard" / "template.html"

# The template carries this marker where the JSON payload belongs. It sits inside
# a <script type="application/json"> block, so the payload is inert markup rather
# than executable code.
DATA_MARKER = "__DATA__"


def load_known_companies(path: Path = COMPANIES_CSV) -> List[str]:
    """Return every company name the scraper is configured for.

    Args:
        path: Location of ``companies.csv``.

    Returns:
        Company names, or an empty list if the file is missing.
    """
    if not path.exists():
        logger.warning("companies.csv not found at %s", path)
        return []
    with path.open("r", encoding="utf-8") as f:
        return [row["Name"].strip() for row in csv.DictReader(f) if row.get("Name")]


def load_industries(path: Path = INDUSTRIES_CSV) -> Dict[str, Dict[str, str]]:
    """Return the sector and robotics tagging for each company.

    ``robotics_tier`` is ``"core"`` for companies that build or operate robots,
    ``"adjacent"`` for the ones that enable them — simulation, sensors, silicon,
    automation software, research labs — and ``"none"`` otherwise.

    Args:
        path: Location of ``industries.csv``.

    Returns:
        Mapping of company name to its tagging fields. Empty if the file is
        missing, in which case every company falls back to ``"unknown"``.
    """
    if not path.exists():
        logger.warning("industries.csv not found at %s; sectors will be unknown", path)
        return {}
    with path.open("r", encoding="utf-8") as f:
        return {
            row["Name"].strip(): {
                "sector": row["Sector"].strip() or "unknown",
                "robotics_tier": row["RoboticsTier"].strip() or "none",
                "robotics_segment": row["RoboticsSegment"].strip(),
            }
            for row in csv.DictReader(f)
            if row.get("Name")
        }


UNTAGGED = {"sector": "unknown", "robotics_tier": "none", "robotics_segment": ""}


def load_source_rows(source: Source, today: date | None = None) -> List[Dict[str, Any]]:
    """Read one JSON file into flat rows with resolved dates and parsed titles.

    Args:
        source: The file to read and the epoch it covers.
        today: Stand-in for the current date, used to bound the live file.

    Returns:
        One dict per posting, in scrape order within each company.
    """
    with source.path.open("r", encoding="utf-8") as f:
        companies = json.load(f).get("companies", {})

    industries = load_industries()
    epoch_end = source.resolved_end(today)
    rows: List[Dict[str, Any]] = []

    for company, postings in companies.items():
        if not postings:
            continue
        tagging = industries.get(company, UNTAGGED)
        if company not in industries and industries:
            logger.warning("%s has no row in industries.csv", company)
        resolved = resolve_company_dates(
            [p["date"] for p in postings], source.epoch_start, epoch_end, company
        )
        for order, (posting, stamp) in enumerate(zip(postings, resolved)):
            title = posting["title"].strip()
            row: Dict[str, Any] = {
                "source": source.label,
                "company": company,
                "title": title,
                "raw_date": stamp.raw,
                "date": stamp.value,
                "is_seed": stamp.is_seed,
                "scrape_order": order,
            }
            row.update(tagging)
            row.update(titles.parse_title(title).as_dict())
            rows.append(row)

    logger.info("%s: %d rows from %d companies", source.label, len(rows), len(companies))
    return rows


def build_dataset(sources: List[Source] | None = None, today: date | None = None):
    """Build the flagged postings table across every available source.

    Args:
        sources: Sources to include. Defaults to everything registered and present.
        today: Stand-in for the current date, used to bound the live file.

    Returns:
        A pandas DataFrame with one row per posting, carrying the resolved date,
        the fields parsed out of the title, and every artifact flag.
    """
    import pandas as pd

    rows: List[Dict[str, Any]] = []
    for source in iter_sources(sources):
        rows.extend(load_source_rows(source, today))

    df = pd.DataFrame(rows)
    if df.empty:
        logger.warning("No postings loaded")
        return df

    df["date"] = pd.to_datetime(df["date"])
    df["week"] = df["date"].dt.to_period("W").dt.start_time
    df["month"] = df["date"].dt.to_period("M").dt.start_time
    df["weekday"] = df["date"].dt.day_name()

    df = clean.apply_flags(df)
    return df.sort_values(["source", "date", "company", "scrape_order"]).reset_index(drop=True)


# Columns whose text must survive a CSV round-trip verbatim. ``raw_date`` holds the
# literal "N/A" sentinel, which pandas would otherwise read back as a missing value.
_LITERAL_COLUMNS = ["raw_date", "seasons", "degrees"]


def read_dataset(path: Path):
    """Read a postings file written by :func:`main` back into a DataFrame.

    Restores the date columns and stops pandas from turning the literal ``"N/A"``
    in ``raw_date`` into a missing value.

    Args:
        path: Path to ``postings.csv`` or ``postings.parquet``.

    Returns:
        The postings DataFrame.
    """
    import pandas as pd

    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(
        path,
        parse_dates=["date", "week", "month"],
        converters={column: str for column in _LITERAL_COLUMNS},
    )


def export_json(df, companies, path: Path) -> None:
    """Write the dataset as a compact JSON payload for the dashboard.

    Columns are written as parallel arrays with string values interned into
    lookup tables, and dates as day offsets from the earliest posting. On this
    data that is roughly a third the size of a row-per-object dump, which matters
    because the payload is embedded directly in the page.

    Args:
        df: The flagged postings frame.
        companies: The per-company quality summary.
        path: Destination ``.json`` file.
    """
    import pandas as pd

    kept = df[df["keep"]].reset_index(drop=True)
    origin = kept["date"].min()

    def intern(series):
        """Return (lookup table, integer codes) for a column of strings."""
        codes = series.fillna("").astype("category")
        return list(codes.cat.categories), codes.cat.codes.tolist()

    company_names, company_codes = intern(kept["company"])
    domains, domain_codes = intern(kept["domain"])
    levels, level_codes = intern(kept["level"])
    seasons, season_codes = intern(kept["season"])
    sources, source_codes = intern(kept["source"].astype(str))

    # Company metadata, indexed to match `company_codes`.
    meta_by_name = {}
    for name in company_names:
        rows = df[df["company"] == name]
        health = companies[companies["company"] == name]
        meta_by_name[name] = {
            "name": name,
            "sector": rows["sector"].iloc[0],
            "tier": rows["robotics_tier"].iloc[0],
            "segment": rows["robotics_segment"].iloc[0],
            "rows": int(len(rows)),
            "kept": int(rows["keep"].sum()),
            "suspect": bool(rows["is_suspect"].any()),
            "junk": bool(rows["company_is_junk"].any()),
            "keptShare": round(float(rows["keep"].mean()), 3),
        }

    # Companies configured but scraping nothing never reach the postings table.
    silent = sorted(
        companies.loc[companies["scraped_nothing"], "company"].unique()
    )

    # A company added to companies.csv mid-epoch has its whole backlog stamped
    # with the first day the scraper looked at it. That day is not the epoch
    # start, so the seed rule never caught it, and it would read as the company
    # opening dozens of roles at once. Mark those days so "first opening" charts
    # can skip them: the company's earliest day, when it carries a batch rather
    # than a single posting.
    BACKLOG_MIN_BATCH = 5
    company_index = {name: i for i, name in enumerate(company_names)}
    backlog = []
    for (name, src), group in df.groupby(["company", "source"], observed=True):
        if name not in company_index:
            continue
        first_day = group["date"].min()
        if (group["date"] == first_day).sum() < BACKLOG_MIN_BATCH:
            continue
        backlog.append([company_index[name], int((first_day - origin).days)])

    payload = {
        "origin": origin.strftime("%Y-%m-%d"),
        "lookups": {
            "companies": [meta_by_name[n] for n in company_names],
            "domains": domains,
            "levels": levels,
            "seasons": seasons,
            "sources": sources,
        },
        "silentCompanies": [s for s in silent if s not in set(company_names)],
        "backlogDays": backlog,
        "postings": {
            "company": company_codes,
            "day": ((kept["date"] - origin).dt.days).tolist(),
            "domain": domain_codes,
            "level": level_codes,
            "season": season_codes,
            "source": source_codes,
            "year": kept["target_year"].fillna(0).astype(int).tolist(),
            "intern": kept["is_internship"].astype(int).tolist(),
            "title": kept["title"].tolist(),
        },
    }

    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))
    logger.info("wrote %s (%.1f MB)", path, path.stat().st_size / 1e6)


def build_dashboard(payload_path: Path, out_path: Path,
                    template_path: Path = DASHBOARD_TEMPLATE) -> None:
    """Splice the JSON payload into the dashboard template.

    Args:
        payload_path: The ``dashboard.json`` written by :func:`export_json`.
        out_path: Destination ``.html`` file.
        template_path: The template carrying :data:`DATA_MARKER`.

    Raises:
        ValueError: If the template does not contain the marker.
    """
    template = template_path.read_text(encoding="utf-8")
    if DATA_MARKER not in template:
        raise ValueError(f"{template_path} has no {DATA_MARKER} marker")

    payload = payload_path.read_text(encoding="utf-8")
    # A literal "</script>" inside the JSON would close the host block early.
    payload = payload.replace("</", "<\\/")
    out_path.write_text(template.replace(DATA_MARKER, payload), encoding="utf-8")
    logger.info("wrote %s (%.1f MB)", out_path, out_path.stat().st_size / 1e6)


def _summarise(df, companies) -> str:
    """Return a short human-readable report on what the pipeline produced."""
    lines = ["", "=" * 68, "Dataset summary", "=" * 68]
    for source, group in df.groupby("source"):
        kept = group["keep"].sum()
        lines += [
            "",
            f"{source}  {group['date'].min():%Y-%m-%d} to {group['date'].max():%Y-%m-%d}",
            f"  rows              {len(group):>6}",
            f"  kept              {kept:>6}  ({kept / len(group):.0%})",
            f"  seed              {group['is_seed'].sum():>6}",
            f"  duplicate         {group['is_duplicate'].sum():>6}",
            f"  mass re-detect    {group['is_bulk_day'].sum():>6}",
            f"  junk title        {group['is_junk_title'].sum():>6}",
            f"  suspect (kept)    {(group['is_suspect'] & group['keep']).sum():>6}",
            f"  internships kept  {(group['is_internship'] & group['keep']).sum():>6}",
        ]
    silent = companies[companies["rows"] == 0]["company"].nunique()
    lines += ["", f"Companies configured but scraping nothing: {silent}", ""]
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    """CLI entry point: build the dataset and write it to disk."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                        help="Directory for the output files (default: analysis/)")
    parser.add_argument("--format", choices=("csv", "parquet"), default="csv",
                        help="Output format (default: csv)")
    parser.add_argument("--json", action="store_true",
                        help="Also write dashboard.json, the payload for the dashboard")
    parser.add_argument("--dashboard", action="store_true",
                        help="Also render dashboard.html from dashboard/template.html")
    parser.add_argument("--quiet", action="store_true", help="Only log warnings")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    df = build_dataset()
    if df.empty:
        return 1

    known = load_known_companies()
    companies = clean.company_quality(df, known)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    postings_path = args.out_dir / f"postings.{args.format}"
    companies_path = args.out_dir / f"company_quality.{args.format}"

    if args.format == "parquet":
        df.to_parquet(postings_path, index=False)
        companies.to_parquet(companies_path, index=False)
    else:
        df.to_csv(postings_path, index=False)
        companies.to_csv(companies_path, index=False)

    if args.json or args.dashboard:
        export_json(df, companies, args.out_dir / "dashboard.json")
    if args.dashboard:
        build_dashboard(args.out_dir / "dashboard.json", args.out_dir / "dashboard.html")

    print(_summarise(df, companies))
    print(f"wrote {postings_path}")
    print(f"wrote {companies_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
