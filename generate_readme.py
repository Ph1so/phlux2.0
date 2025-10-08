import json
from datetime import datetime
from pathlib import Path
from typing import List
from collections import defaultdict
from phlux.scrapers import CompanyScraper, JPMorganScraper

from phlux.scraping import load_company_data
from utils import update_icons

def load_company_links(csv_path: str) -> dict:
    return {c.name: c.link for c in load_company_data(Path(csv_path))}


def load_jobs(json_path: str) -> dict:
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
        return data.get("companies", {})
    

def generate_readme(jobs: dict, links: dict) -> str:
    update_icons(companies=load_company_data())
    try:
        with open("icons.json", "r", encoding="utf-8") as f:
            icons = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        icons = {}

    lines = ["# 🌀 Phlux: Phi's Job Tracker\n"]
    lines.append("Easily track jobs across top tech companies.\n")

    # lines.append("## 🧩 Add Your Own Companies")
    # lines.extend([
    #     "- Run `add_company.py`",
    #     "- Follow the CLI instructions (see below)",
    #     "- Add selector and example job title to `companies.csv`",
    #     "- Make a PR to contribute!",
    #     "![CLI Example](public/cli.png)",
    # ])

    total_jobs = sum(len(v) for v in jobs.values() if v)
    lines.append(f"\n---\n\n## 🔍 2025 Phlux Job Listings\n*Found {total_jobs} roles across {len(jobs)} companies*\n")

    # Begin HTML table
    lines.append("""
<table>
  <thead>
    <tr>
      <th style="white-space: nowrap;">Company</th>
      <th style="width: 100%;">Role</th>
      <th style="width: 100px;">Date Found</th>
    </tr>
  </thead>
  <tbody>
""")

    # Collect and sort jobs
    all_jobs = []
    for company in jobs:
        postings = jobs[company]
        if not postings:
            continue

        icon_url = icons.get(company, {})
        if not isinstance(icon_url, str):
            icon_url = icon_url.get("readme", "")

        company_display = f'<img src="{icon_url}" alt="{company}" height="20" style="vertical-align:middle; margin-right:6px;"> {company}' if icon_url else company
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
                sort_date = datetime.strptime(date_str, "%m/%d")
            except ValueError:
                sort_date = datetime.min

            all_jobs.append((linked_company, title, date_str, sort_date))

    # Sort descending by date
    all_jobs.sort(key=lambda x: x[3], reverse=True)

    for company, title, date_str, _ in all_jobs:
        role_cell = f'<div style="max-height:4.5em; overflow:auto; white-space:normal;">{title}</div>'
        lines.append(f"""  <tr>
  <td>
  <div style="display: inline-flex; align-items: center; white-space: nowrap;">{company}</div>
</td>

  <td>{role_cell}</td>
  <td>{date_str}</td>
</tr>""")

    lines.append("""
  </tbody>
</table>
\n---
""")

    return "\n".join(lines)

if __name__ == "__main__":
    # custom_scrapers: List[CompanyScraper] = [JPMorganScraper()]
    # for scraper in custom_scrapers:
    #     links[scraper.name] = scraper.base_link
    links = load_company_links("companies.csv")
    jobs = load_jobs("storage.json")
    readme = generate_readme(jobs, links)

    Path("README.md").write_text(readme, encoding='utf-8')
    print("README.md updated successfully.")