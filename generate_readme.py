import json
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

    lines = ["# 🌀 Phlux: Job Tracker\n"]
    lines.append("Easily track jobs across top tech companies.\n")

    lines.append("## 🧩 Add Your Own Companies")
    lines.extend([
        "- Run `add_company.py`",
        "- Follow the CLI instructions (see below)",
        "- Add selector and example job title to `companies.csv`",
        "- Make a PR to contribute!",
        "![CLI Example](public/cli.png)",
    ])

    lines.append(f"\n---\n\n## 📌 Current Job Listings ({len(jobs)} companies)\n")

    grouped = defaultdict(list)
    for company in sorted(jobs):
        if not jobs[company]:
            continue
        first_letter = company[0].upper()
        grouped[first_letter].append(company)

    lines.append("### 🔎 Table of Contents\n")
    for letter in sorted(grouped):
        lines.append(f"#### {letter}")
        for company in grouped[letter]:
            anchor = company.lower().replace(" ", "-")
            lines.append(f"- [{company}](#{anchor})")
        lines.append("")

    lines.append("---\n")

    for letter in sorted(grouped):
        for company in grouped[letter]:
            postings = jobs[company]
            if not postings:
                continue

            icon_url = icons.get(company)
            icon_html = (
                f'<img src="{icon_url}" alt="{company} logo" height="20" style="vertical-align:middle; margin-right:6px;" />'
                if icon_url else ""
            )

            anchor_name = company.lower().replace(" ", "-")
            lines.append(f'<a style="font-family: Inconsolata, monospace;" name="{anchor_name}"></a>')
            name_html = f'<a style="font-family: Inconsolata, monospace;" href="{links[company]}" target="_blank"><strong>{company}</strong></a>'
            header_line = f'''
            <div style="text-align: center; margin-top: 30px;">
                {icon_html}
                <a href="{links[company]}" target="_blank" style="font-family: Inconsolata, monospace; font-size: 18px; text-decoration: none;">
                    <strong>{company}</strong>
                </a>
                <br>
                <sub style="font-family: Inconsolata, monospace;">({len(postings)} roles)</sub>
            </div>
            '''

            lines.append(header_line)

            for role in postings:
                cleaned = role.replace("\n", " ").strip()
                lines.append(f"- {cleaned}")

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

