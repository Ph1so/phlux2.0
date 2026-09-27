"""Generate README.md and the listings/ pages from the job storage files.

GitHub stops rendering a Markdown file past 512 KB, so the README only shows the
most recent postings, trimmed to a byte budget. The full history goes into
``listings/``, one compact page per month, split further when a month is too big.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from phlux.scraping import load_company_data
from phlux.utils import update_icons

# GitHub renders up to 512 KiB; stay well clear of it.
MAX_PAGE_BYTES = 450_000
README_MAX_ROWS = 1000
LISTINGS_DIR = Path("listings")
PREV_YEARS_DIR = Path("prev_years")


@dataclass(frozen=True)
class Row:
    """One posting, flattened out of a storage file."""

    company: str
    title: str
    found: Optional[date]


def load_company_links(csv_path: str = "companies.csv") -> Dict[str, str]:
    """Return a mapping of company name → careers URL from the CSV."""
    return {c.name: c.link for c in load_company_data(Path(csv_path))}


def load_jobs(json_path: str = "storage.json") -> Dict[str, List[Any]]:
    """Load the ``companies`` section from the storage JSON file."""
    with open(json_path, encoding="utf-8") as f:
        return json.load(f).get("companies", {})


def load_archives(archive_dir: Path = PREV_YEARS_DIR) -> List[Dict[str, List[Any]]]:
    """Load the ``companies`` section of every archived season, newest file first."""
    if not archive_dir.is_dir():
        return []
    return [load_jobs(str(p)) for p in sorted(archive_dir.glob("*.json"), reverse=True)]


def parse_found_date(raw: str, today: Optional[date] = None, legacy_md: bool = True) -> Optional[date]:
    """Parse a stored ``date`` field.

    ISO ``YYYY-MM-DD`` is exact. With *legacy_md*, a bare ``M/D`` is taken as its
    most recent occurrence on or before *today* — only safe for the live file, since
    an archive's ``M/D`` rows can be years old. Anything else (``"N/A"``) is undated.
    """
    try:
        return date.fromisoformat(raw)
    except (TypeError, ValueError):
        pass
    if not legacy_md:
        return None
    today = today or date.today()
    try:
        month, day = (int(x) for x in raw.split("/"))
        found = date(today.year, month, day)
    except (AttributeError, ValueError):
        return None
    return found if found <= today else found.replace(year=today.year - 1)


def flatten(jobs: Dict[str, List[Any]], today: Optional[date] = None, legacy_md: bool = True) -> List[Row]:
    """Flatten a ``companies`` mapping into rows, cleaning titles for table cells."""
    rows = []
    for company, postings in jobs.items():
        for role in postings or []:
            if isinstance(role, dict):
                title, raw = role.get("title", ""), role.get("date", "N/A")
            else:
                title, raw = role, "N/A"
            title = title.replace("\n", " ").replace("|", "\\|").strip()
            rows.append(Row(company, title, parse_found_date(raw, today, legacy_md)))
    return rows


def newest_first(rows: List[Row]) -> List[Row]:
    """Dated rows only, most recent first (stable within a day)."""
    return sorted((r for r in rows if r.found), key=lambda r: r.found, reverse=True)


def _load_icons() -> Dict[str, Any]:
    try:
        from phlux.utils import _ICONS_PATH
        with open(_ICONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def generate_readme(
    jobs: Dict[str, List[Any]],
    links: Dict[str, str],
    archives: Optional[List[Dict[str, List[Any]]]] = None,
    max_bytes: int = MAX_PAGE_BYTES,
    max_rows: int = README_MAX_ROWS,
) -> str:
    """Build the README Markdown string.

    Renders an HTML table of the most recent postings (newest first), stopping at
    *max_rows* or when the page would pass *max_bytes*. Archived seasons are
    included so the table stays full right after a season rollover.

    Args:
        jobs: Current season: company name → list of job dicts (``title``/``date``).
        links: Company name → careers page URL.
        archives: Earlier seasons, same shape as *jobs*.
        max_bytes: Size budget for the whole page.
        max_rows: Upper bound on table rows.

    Returns:
        Complete README Markdown string.
    """
    icons = _load_icons()
    company_cells: Dict[str, str] = {}

    def company_cell(company: str) -> str:
        if company not in company_cells:
            icon_url = icons.get(company, "")
            if not isinstance(icon_url, str):
                icon_url = icon_url.get("readme", "")
            display = (
                f'<img src="{icon_url}" alt="{company}" height="20" '
                f'style="vertical-align:middle; margin-right:6px;"> {company}'
                if icon_url
                else company
            )
            company_cells[company] = f'<a href="{links.get(company, "#")}">{display}</a>'
        return company_cells[company]

    rows = flatten(jobs)
    for archived in archives or []:
        rows += flatten(archived, legacy_md=False)
    recent = newest_first(rows)

    total_jobs = sum(len(v) for v in jobs.values() if v)
    table_rows: List[str] = []
    for row in recent[:max_rows]:
        table_rows.append(
            f"""  <tr>
  <td>
  <div style="display: inline-flex; align-items: center; white-space: nowrap;">{company_cell(row.company)}</div>
</td>
  <td><div style="max-height:4.5em; overflow:auto; white-space:normal;">{row.title}</div></td>
  <td>{row.found.isoformat()}</td>
</tr>"""
        )

    def render(n: int) -> str:
        lines = [
            "# 🌀 Phlux: Phi's Job Tracker\n",
            "Easily track jobs across top tech companies.\n",
            f"\n---\n\n## 🔍 Phlux Job Listings\n"
            f"*Found {total_jobs} roles across {len(jobs)} companies this season. "
            f"Showing the {n} most recent — see [all listings](listings/README.md) for the full history.*\n",
            """
<table>
  <thead>
    <tr>
      <th style="white-space: nowrap;">Company</th>
      <th style="width: 100%;">Role</th>
      <th style="width: 100px;">Date Found</th>
    </tr>
  </thead>
  <tbody>
""",
            *table_rows[:n],
            """
  </tbody>
</table>
\n---
""",
        ]
        return "\n".join(lines)

    # Drop rows off the bottom until the page fits the budget.
    n = len(table_rows)
    page = render(n)
    while n and len(page.encode("utf-8")) > max_bytes:
        overshoot = len(page.encode("utf-8")) - max_bytes
        n = max(0, n - max(1, overshoot // 400))
        page = render(n)
    return page


def _listing_page(heading: str, rows: List[Row], links: Dict[str, str]) -> str:
    """Render *rows* as a compact Markdown table with reference-style company links."""
    refs: Dict[str, str] = {}
    lines = [f"# {heading}\n", f"[← All listings](README.md) · {len(rows)} roles\n",
             "| Company | Role | Date Found |", "| --- | --- | --- |"]
    for row in rows:
        ref = refs.setdefault(row.company, f"c{len(refs)}")
        company = f"[{row.company}][{ref}]" if row.company in links else row.company
        title = row.title.replace("<", "&lt;")
        lines.append(f"| {company} | {title} | {row.found.isoformat() if row.found else 'N/A'} |")
    lines.append("")
    lines += [f"[{ref}]: {links[c]}" for c, ref in refs.items() if c in links]
    return "\n".join(lines) + "\n"


def _paginate(stem: str, heading: str, rows: List[Row], links: Dict[str, str],
              max_bytes: int) -> Dict[str, str]:
    """Render *rows* as one page, or as ``stem-1.md``, ``stem-2.md``… if too big."""
    page = _listing_page(heading, rows, links)
    size = len(page.encode("utf-8"))
    if size <= max_bytes:
        return {f"{stem}.md": page}
    parts = -(-size // max_bytes) + 1  # one spare part for the per-page link footers
    per_part = -(-len(rows) // parts)
    return {
        f"{stem}-{i + 1}.md": _listing_page(f"{heading} (part {i + 1})", rows[start:start + per_part], links)
        for i, start in enumerate(range(0, len(rows), per_part))
    }


def generate_listings(
    jobs: Dict[str, List[Any]],
    links: Dict[str, str],
    archives: Optional[List[Dict[str, List[Any]]]] = None,
    max_bytes: int = MAX_PAGE_BYTES,
) -> Dict[str, str]:
    """Build the ``listings/`` pages: file name → Markdown content.

    One page per month across every season, plus an index. Postings the current
    season recorded as backlog (``"N/A"``) get their own page, minus any that an
    earlier season already dated.
    """
    current = flatten(jobs)
    everything = current + [r for archived in archives or [] for r in flatten(archived, legacy_md=False)]
    dated = newest_first(everything)

    by_month: Dict[str, List[Row]] = {}
    for row in dated:
        by_month.setdefault(row.found.strftime("%Y-%m"), []).append(row)

    pages: Dict[str, str] = {}
    index = ["# 📚 All Phlux Listings\n", "[← Back to recent listings](../README.md)\n",
             "| Month | Roles |", "| --- | --- |"]
    for month, rows in by_month.items():
        month_pages = _paginate(month, f"{month} listings", rows, links, max_bytes)
        pages.update(month_pages)
        parts = " · ".join(f"[{Path(name).stem}]({name})" for name in month_pages)
        index.append(f"| {parts} | {len(rows)} |")

    seen = {(r.company, r.title) for r in dated}
    backlog = [r for r in current if not r.found and (r.company, r.title) not in seen]
    if backlog:
        backlog_pages = _paginate("backlog", "Already open when this season began", backlog, links, max_bytes)
        pages.update(backlog_pages)
        parts = " · ".join(f"[{Path(name).stem}]({name})" for name in backlog_pages)
        index.append(f"| {parts} (undated) | {len(backlog)} |")

    pages["README.md"] = "\n".join(index) + "\n"
    return pages


def write_listings(pages: Dict[str, str], out_dir: Path = LISTINGS_DIR) -> None:
    """Replace *out_dir* with *pages* so stale months and parts don't linger."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    for name, content in pages.items():
        (out_dir / name).write_text(content, encoding="utf-8")


if __name__ == "__main__":
    _links = load_company_links()
    _jobs = load_jobs()
    _archives = load_archives()
    update_icons(companies=load_company_data())
    Path("README.md").write_text(generate_readme(_jobs, _links, _archives), encoding="utf-8")
    write_listings(generate_listings(_jobs, _links, _archives))
    print("README.md and listings/ updated successfully.")
