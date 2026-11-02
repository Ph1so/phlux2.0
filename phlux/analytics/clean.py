"""Step 1: flag the rows that are scraper artifacts rather than real openings.

``process_jobs`` treats any title it has not stored before as a brand-new posting.
That assumption breaks in four ways, and each one shows up as a spike that would
otherwise read as a hiring wave:

* **Seed rows** — the backlog already on a careers page the first time the scraper
  looked at it. Real postings, but their open date is unknown.
* **Duplicate titles** — the same title stored twice for one company, either because
  a selector matches two elements per card or because the page was re-read.
* **Mass re-detection days** — a title format change (an added req ID, a new suffix)
  makes every posting look new at once. On 2026-03-19, 106 companies "posted"
  simultaneously against a median of 21.
* **Junk scrapes** — a selector that grabs nav labels and blog headlines instead of
  job titles.

Nothing is deleted. Every row keeps every flag, and ``keep`` is a convenience column
combining the flags that are safe to exclude by default. The judgement calls that
could throw away real data — a genuinely large single-day drop, a company whose
titles merely look unusual — land in ``is_suspect`` instead, for you to look at.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import cost only matters at runtime
    import pandas as pd

logger = logging.getLogger(__name__)

# A day is a mass re-detection when this many times more companies than usual post
# on it. The median active day sees ~20 companies; the real artifact days sit at
# 97-142 and the busiest honest day at 47, so 3x separates them cleanly.
BULK_DAY_FACTOR = 3.0

# ...but never flag a day that is small in absolute terms, however quiet the epoch.
BULK_DAY_MIN_COMPANIES = 10

# A single company-day batch is suspect when it is both large and most of that
# company's entire history — the shape of a whole page being re-read.
BULK_BATCH_MIN_ROWS = 50
BULK_BATCH_MIN_SHARE = 0.5

# A company whose titles are mostly free of job vocabulary is scraping the wrong
# elements. Applied Intuition sits at 0.60, the next real company well below.
JUNK_COMPANY_THRESHOLD = 0.5


def _as_bool(df: "pd.DataFrame", *columns: str) -> None:
    """Coerce flag columns to real booleans, in place.

    A frame assembled from dicts where some rows omit a flag arrives with dtype
    ``object``, and ``~`` on that does bitwise integer inversion instead of
    negation — silently turning every mask into nonsense.
    """
    for column in columns:
        if column in df and df[column].dtype != bool:
            df[column] = df[column].fillna(False).astype(bool)


def mark_duplicates(df: "pd.DataFrame") -> "pd.DataFrame":
    """Flag repeat appearances of a title within one company and epoch.

    The first appearance is kept; later ones get ``is_duplicate``.

    Args:
        df: Postings frame with ``source``, ``company`` and ``title`` columns.

    Returns:
        The frame with an ``is_duplicate`` column added.
    """
    df["is_duplicate"] = df.duplicated(subset=["source", "company", "title"], keep="first")
    return df


def mark_bulk_days(
    df: "pd.DataFrame",
    factor: float = BULK_DAY_FACTOR,
    min_companies: int = BULK_DAY_MIN_COMPANIES,
) -> "pd.DataFrame":
    """Flag days where far more companies posted at once than usual.

    The threshold is per epoch, so a quiet archive and a busy live file are each
    judged against their own baseline.

    Args:
        df: Postings frame with ``source``, ``date`` and ``company`` columns.
        factor: Multiple of the epoch's median companies-per-day that counts as
            a mass re-detection.
        min_companies: Floor below which a day is never flagged.

    Returns:
        The frame with ``companies_that_day`` and ``is_bulk_day`` columns added.
    """
    import pandas as pd

    _as_bool(df, "is_seed")
    per_day = (
        df[~df["is_seed"]]
        .groupby(["source", "date"])["company"]
        .nunique()
        .rename("companies_that_day")
    )
    thresholds = per_day.groupby("source").median() * factor
    thresholds = thresholds.clip(lower=min_companies)

    df = df.merge(per_day, on=["source", "date"], how="left")
    df["companies_that_day"] = df["companies_that_day"].fillna(0).astype(int)
    df["is_bulk_day"] = ~df["is_seed"] & (
        df["companies_that_day"] >= df["source"].map(thresholds)
    )

    for source, threshold in thresholds.items():
        flagged = sorted(
            df.loc[df["is_bulk_day"] & (df["source"] == source), "date"].unique()
        )
        shown = ", ".join(pd.Timestamp(d).date().isoformat() for d in flagged)
        logger.info(
            "%s: mass re-detection threshold %.0f companies/day, flagged %d day(s): %s",
            source, threshold, len(flagged), shown or "none",
        )
    return df


def mark_bulk_batches(
    df: "pd.DataFrame",
    min_rows: int = BULK_BATCH_MIN_ROWS,
    min_share: float = BULK_BATCH_MIN_SHARE,
) -> "pd.DataFrame":
    """Flag single company-days large enough to be a whole page re-read.

    This one is advisory only: a company really can drop 150 roles in a morning,
    so the flag feeds ``is_suspect`` rather than ``keep``.

    Args:
        df: Postings frame with ``source``, ``company`` and ``date`` columns.
        min_rows: Batch sizes below this are never flagged.
        min_share: Fraction of the company's history the batch must represent.

    Returns:
        The frame with ``batch_rows``, ``batch_share`` and ``is_bulk_batch`` added.
    """
    _as_bool(df, "is_seed")
    batch = df.groupby(["source", "company", "date"])["title"].transform("size")
    total = df.groupby(["source", "company"])["title"].transform("size")

    df["batch_rows"] = batch
    df["batch_share"] = (batch / total).round(3)
    df["is_bulk_batch"] = ~df["is_seed"] & (batch >= min_rows) & (df["batch_share"] >= min_share)
    return df


def mark_junk(df: "pd.DataFrame", threshold: float = JUNK_COMPANY_THRESHOLD) -> "pd.DataFrame":
    """Flag titles with no job vocabulary, and companies made mostly of them.

    Args:
        df: Postings frame with a ``has_role_word`` column from
            :func:`phlux.analytics.titles.parse_title`.
        threshold: Share of a company's titles lacking job vocabulary above which
            the whole company is treated as a bad scrape.

    Returns:
        The frame with ``is_junk_title``, ``company_junk_score`` and
        ``company_is_junk`` columns added.
    """
    _as_bool(df, "has_role_word")
    df["is_junk_title"] = ~df["has_role_word"]
    score = df.groupby(["source", "company"])["is_junk_title"].transform("mean")
    df["company_junk_score"] = score.round(3)
    df["company_is_junk"] = score > threshold
    return df


def apply_flags(df: "pd.DataFrame") -> "pd.DataFrame":
    """Run every flagging pass and derive ``keep`` and ``is_suspect``.

    ``keep`` excludes rows whose date is meaningless (seed), whose existence is
    double-counted (duplicate), or that are not really postings (junk title, mass
    re-detection day). ``is_suspect`` marks the rows worth eyeballing before
    trusting them, without removing them.

    Args:
        df: Postings frame carrying the raw and title-derived columns.

    Returns:
        The frame with all flag columns plus ``keep`` and ``is_suspect``.
    """
    df = mark_duplicates(df)
    df = mark_junk(df)
    df = mark_bulk_days(df)
    df = mark_bulk_batches(df)

    df["keep"] = ~(
        df["is_seed"] | df["is_duplicate"] | df["is_junk_title"] | df["is_bulk_day"]
    )
    df["is_suspect"] = df["is_bulk_batch"] | df["company_is_junk"]
    return df


def company_quality(df: "pd.DataFrame", known_companies: list[str] | None = None) -> "pd.DataFrame":
    """Summarise per-company data health, including companies that scraped nothing.

    Args:
        df: Flagged postings frame.
        known_companies: Every company name the scraper is configured for, so
            those with zero rows still appear. Usually the names in
            ``companies.csv``.

    Returns:
        One row per company and epoch, with row counts, flag rates, the date range
        covered, and ``scraped_nothing`` for configured companies that produced no
        postings at all.
    """
    import pandas as pd

    summary = (
        df.groupby(["source", "company"])
        .agg(
            rows=("title", "size"),
            kept=("keep", "sum"),
            duplicates=("is_duplicate", "sum"),
            seed_rows=("is_seed", "sum"),
            bulk_day_rows=("is_bulk_day", "sum"),
            junk_score=("company_junk_score", "first"),
            is_junk=("company_is_junk", "first"),
            suspect_rows=("is_suspect", "sum"),
            first_seen=("date", "min"),
            last_seen=("date", "max"),
            internships=("is_internship", "sum"),
        )
        .reset_index()
    )
    summary["kept_share"] = (summary["kept"] / summary["rows"]).round(3)
    summary["scraped_nothing"] = summary["rows"] == 0

    if known_companies:
        missing = []
        for source in summary["source"].unique():
            seen = set(summary.loc[summary["source"] == source, "company"])
            missing += [
                {"source": source, "company": name, "scraped_nothing": True}
                for name in known_companies
                if name not in seen
            ]
        if missing:
            summary = pd.concat([summary, pd.DataFrame(missing)], ignore_index=True)
            # Companies that scraped nothing have no rows to aggregate, so their
            # counts come back as NaN; they are genuine zeros.
            counts = ["rows", "kept", "duplicates", "seed_rows", "bulk_day_rows",
                      "suspect_rows", "internships"]
            summary[counts] = summary[counts].fillna(0).astype(int)
            summary["is_junk"] = summary["is_junk"].fillna(False).astype(bool)
            summary["scraped_nothing"] = summary["scraped_nothing"].fillna(False).astype(bool)

    return summary.sort_values(["source", "rows"], ascending=[True, False])
