"""Generate README.md from storage.json with a sorted HTML job table."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from phlux.scraping import load_company_data
from phlux.utils import update_icons


def load_company_links(csv_path: str = "companies.csv") -> Dict[str, str]:
    """Return a mapping of company name → careers URL from the CSV."""
    return {c.name: c.link for c in load_company_data(Path(csv_path))}


def load_jobs(json_path: str = "storage.json") -> Dict[str, List[Any]]:
    """Load the ``companies`` section from the storage JSON file."""
    with open(json_path, encoding="utf-8") as f:
        return json.load(f).get("companies", {})


def generate_readme(jobs: Dict[str, List[Any]], links: Dict[str, str]) -> str:
    """Build the full README Markdown string from job data.

    Renders an HTML table of all postings sorted by date (most recent first).

    Args:
        jobs: Dict mapping company name → list of job dicts (with ``title``
              and ``date`` keys) as stored in ``storage.json``.
        links: Dict mapping company name → careers page URL.

    Returns:
        Complete README Markdown string.
    """
    try:
        from phlux.utils import _ICONS_PATH
        with open(_ICONS_PATH, "r", encoding="utf-8") as f:
            icons = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        icons = {}

    total_jobs = sum(len(v) for v in jobs.values() if v)
    lines = [
        "# 🌀 Phlux: Phi's Job Tracker\n",
        "Easily track jobs across top tech companies.\n",
        f"\n---\n\n## 🔍 2025 Phlux Job Listings\n"
        f"*Found {total_jobs} roles across {len(jobs)} companies*\n",
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
    ]

    all_jobs = []
    for company, postings in jobs.items():
        if not postings:
            continue

        icon_url = icons.get(company, "")
        if not isinstance(icon_url, str):
            icon_url = icon_url.get("readme", "")

        company_display = (
            f'<img src="{icon_url}" alt="{company}" height="20" '
            f'style="vertical-align:middle; margin-right:6px;"> {company}'
            if icon_url
            else company
        )
        company_link = links.get(company, "#")
        linked_company = f'<a href="{company_link}">{company_display}</a>'

        for role in postings:
            if isinstance(role, dict):
                title = role.get("title", "").replace("\n", " ").replace("|", "\\|").strip()
                date_str = role.get("date", "N/A")
            else:
                title = role.replace("\n", " ").replace("|", "\\|").strip()
                date_str = "N/A"

            try:
                # Include a fixed year to avoid the Python 3.15 ambiguous-date deprecation.
                sort_date = datetime.strptime(f"2000/{date_str}", "%Y/%m/%d")
            except ValueError:
                sort_date = datetime.min

            all_jobs.append((linked_company, title, date_str, sort_date))

    all_jobs.sort(key=lambda x: x[3], reverse=True)

    for company, title, date_str, _ in all_jobs:
        role_cell = f'<div style="max-height:4.5em; overflow:auto; white-space:normal;">{title}</div>'
        lines.append(
            f"""  <tr>
  <td>
  <div style="display: inline-flex; align-items: center; white-space: nowrap;">{company}</div>
</td>
  <td>{role_cell}</td>
  <td>{date_str}</td>
</tr>"""
        )

    lines.append("""
  </tbody>
</table>
\n---
""")

    return "\n".join(lines)


if __name__ == "__main__":
    _links = load_company_links()
    _jobs = load_jobs()
    update_icons(companies=load_company_data())
    readme = generate_readme(_jobs, _links)
    Path("README.md").write_text(readme, encoding="utf-8")
    print("README.md updated successfully.")
