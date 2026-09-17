"""Company lists: named JSON subsets of ``companies.csv`` to scrape.

``companies.csv`` is the single source of truth for *how* to scrape a company
(its URL and action string).  A company list only names the companies to
include, so different people can run the same scraper over different subsets.

A list file looks like::

    {
      "name": "Robotics",
      "description": "Hardware + robotics companies only",
      "created": "2026-09-17",
      "companies": ["Nvidia", "Tesla", "Figure"]
    }

A bare JSON array of names is also accepted.
"""
from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, List, Sequence

from .models import Company

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LISTS_DIR = REPO_ROOT / "lists"


def load_companies(csv_path: Path | str = Path("companies.csv")) -> List[Company]:
    """Parse ``companies.csv`` and return every company it defines.

    Args:
        csv_path: Path to the CSV file (default: ``companies.csv``).

    Returns:
        List of Company objects with ``name``, ``link``, and ``selector`` fields.
    """
    with open(csv_path, newline="", encoding="utf-8") as f:
        return [
            Company(
                row["Name"].strip(),
                row["Link"].strip().strip("'\""),
                row["ClassName"].strip(),
            )
            for row in csv.DictReader(f)
        ]


@dataclass
class CompanyList:
    """A named subset of the companies defined in ``companies.csv``."""

    name: str
    companies: List[str]
    description: str = ""
    created: str = ""
    path: Path | None = field(default=None, compare=False)

    def to_dict(self) -> dict:
        """Return the JSON-serializable form written to disk."""
        return {
            "name": self.name,
            "description": self.description,
            "created": self.created or date.today().isoformat(),
            "companies": list(self.companies),
        }


def resolve_list_path(ref: str | Path, lists_dir: Path | str = DEFAULT_LISTS_DIR) -> Path:
    """Resolve a list reference to a file path.

    Accepts a bare stem (``"robotics"``), a file name (``"robotics.json"``), or
    a path relative to the repo root (``"lists/robotics.json"``). Absolute paths
    are returned unchanged.

    Args:
        ref: The list reference, typically from ``config.json``.
        lists_dir: Directory holding list files.

    Returns:
        Path to the list file (which may not exist).
    """
    ref = Path(ref)
    if ref.is_absolute():
        return ref
    if ref.suffix != ".json":
        ref = ref.with_suffix(".json")
    # A bare file name lives in lists_dir; anything with a directory component
    # is taken as-is (relative to the caller's working directory).
    if len(ref.parts) == 1:
        return Path(lists_dir) / ref
    return ref


def load_company_list(ref: str | Path, lists_dir: Path | str = DEFAULT_LISTS_DIR) -> CompanyList:
    """Load the company list identified by *ref*.

    Args:
        ref: List reference accepted by :func:`resolve_list_path`.
        lists_dir: Directory holding list files.

    Returns:
        The parsed :class:`CompanyList`.

    Raises:
        FileNotFoundError: If no such list file exists.
        ValueError: If the file is not a valid list document.
    """
    path = resolve_list_path(ref, lists_dir)
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    if isinstance(raw, list):
        raw = {"companies": raw}
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object or array of names")

    names = raw.get("companies", [])
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise ValueError(f"{path}: 'companies' must be a list of company names")

    return CompanyList(
        name=raw.get("name") or path.stem,
        companies=[n.strip() for n in names if n.strip()],
        description=raw.get("description", ""),
        created=raw.get("created", ""),
        path=path,
    )


def save_company_list(
    company_list: CompanyList,
    ref: str | Path | None = None,
    lists_dir: Path | str = DEFAULT_LISTS_DIR,
) -> Path:
    """Write *company_list* to disk and return the path written.

    Args:
        company_list: The list to save.
        ref: Where to save it; defaults to the list's own ``path``, else its
            name slugified into *lists_dir*.
        lists_dir: Directory holding list files.

    Returns:
        The path that was written.
    """
    if ref is None:
        ref = company_list.path or slugify(company_list.name)
    path = resolve_list_path(ref, lists_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(company_list.to_dict(), indent=2) + "\n", encoding="utf-8")
    company_list.path = path
    return path


def available_lists(lists_dir: Path | str = DEFAULT_LISTS_DIR) -> List[Path]:
    """Return every ``*.json`` list file in *lists_dir*, sorted by name."""
    lists_dir = Path(lists_dir)
    if not lists_dir.is_dir():
        return []
    return sorted(p for p in lists_dir.glob("*.json") if p.is_file())


def slugify(name: str) -> str:
    """Turn a display name into a safe lowercase file stem."""
    cleaned = "".join(c if c.isalnum() else "-" for c in name.lower())
    stem = "-".join(part for part in cleaned.split("-") if part)
    return stem or "untitled"


def filter_companies(companies: Sequence[Company], names: Iterable[str]) -> List[Company]:
    """Keep only the companies named in *names*, preserving CSV order.

    Matching is case-insensitive and ignores surrounding whitespace. Names with
    no matching CSV row are logged and skipped, so a stale list still runs.

    Args:
        companies: Companies parsed from ``companies.csv``.
        names: Company names to keep.

    Returns:
        The matching subset of *companies*, in their original CSV order.
    """
    wanted = {n.strip().casefold() for n in names if n.strip()}
    selected = [c for c in companies if c.name.strip().casefold() in wanted]

    missing = wanted - {c.name.strip().casefold() for c in companies}
    if missing:
        logger.warning(
            "%d name(s) in the company list are not in companies.csv: %s",
            len(missing),
            ", ".join(sorted(missing)),
        )
    return selected


def select_companies(
    companies: Sequence[Company],
    list_ref: str | Path | None,
    lists_dir: Path | str = DEFAULT_LISTS_DIR,
) -> List[Company]:
    """Apply the company list named by *list_ref*, or return everything.

    Args:
        companies: Companies parsed from ``companies.csv``.
        list_ref: A list reference, or ``None``/empty to scrape all companies.
        lists_dir: Directory holding list files.

    Returns:
        The companies to scrape.
    """
    if not list_ref:
        logger.info("No company list configured — scraping all %d companies.", len(companies))
        return list(companies)

    company_list = load_company_list(list_ref, lists_dir)
    selected = filter_companies(companies, company_list.companies)
    logger.info(
        "Company list '%s' selected %d of %d companies.",
        company_list.name, len(selected), len(companies),
    )
    return selected
