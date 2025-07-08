import json
from datetime import datetime
from pathlib import Path
from typing import List
from collections import defaultdict
from phlux.scrapers import CompanyScraper, JPMorganScraper

from phlux.scraping import load_company_data

def load_company_links(csv_path: str) -> dict:
    return {c.name: c.link for c in load_company_data(Path(csv_path))}


def load_jobs(json_path: str) -> dict:
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
        return data.get("companies", {})
    

def generate_readme(jobs: dict, links: dict) -> str:
    try:
        with open("icons.json", "r", encoding="utf-8") as f:
            icons = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        icons = {}

    lines = ["# 🌀 Phlux: Phi's Job Tracker\n"]
    lines.append("Easily track jobs across top tech companies.\n")

    lines.append("## 🧩 Add Your Own Companies")
    lines.extend([
        "- Run `add_company.py`",
        "- Follow the CLI instructions (see below)",
        "- Add selector and example job title to `companies.csv`",
        "- Make a PR to contribute!",
        "![CLI Example](public/cli.png)",
    ])

    total_jobs = sum(len(v) for v in jobs.values() if v)
    lines.append(f"\n---\n\n## 📌 Job Listings found by Phlux ({len(jobs)} companies, {total_jobs} roles)\n")


    # Header row for table
    lines.append("| Company | Role | Date Found |")
    lines.append("|---|---|---|")

    # Collect all jobs into a flat list with metadata
    all_jobs = []
    for company in jobs:
        postings = jobs[company]
        if not postings:
            continue

        icon_url = icons.get(company)
        company_display = f'<img src="{icon_url}" alt="{company}" height="20" style="vertical-align:middle; margin-right:6px;"> {company}' if icon_url else company
        company_link = links.get(company, "#")
        linked_company = f"[{company_display}]({company_link})"

        for role in postings:
            if isinstance(role, dict):
                title = role.get("title", "").replace("\n", " ").replace("|", "\\|").strip()
                date_str = role.get("date", "N/A")
            else:
                title = role.replace("\n", " ").replace("|", "\\|").strip()
                date_str = "N/A"

            # For sorting, convert to datetime (fallback to 1970-01-01 if unknown)
            try:
                sort_date = datetime.strptime(date_str, "%m/%d/%Y")
            except ValueError:
                sort_date = datetime(1970, 1, 1)

            all_jobs.append((linked_company, title, date_str, sort_date))

    # Sort by date descending (most recent first)
    all_jobs.sort(key=lambda x: x[3], reverse=True)

    for company, title, date_str, _ in all_jobs:
        lines.append(f"| {company} | {title} | {date_str} |")

    lines.append("\n---")

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

