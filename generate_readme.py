import json
import csv
from pathlib import Path
from custom_scrapers import JPMorganScraper

def load_company_links(csv_path: str) -> dict:
    links = {}
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["Name"].strip()
            link = row["Link"].strip()
            if name and link:
                links[name] = link
    return links

def load_jobs(json_path: str) -> dict:
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
        return data.get("companies", {})

def generate_readme(jobs: dict, links: dict) -> str:
    lines = ["# Phlux\n"]
    lines.append("## Adding your own companies\n")
    lines.append("- Run add_company.py\n")
    lines.append("- Follow the instructions in the command line interface\n")
    lines.append("- For 'Example job title', when you open the link to the job page just copy and paste the exact title of a random job\n")
    lines.append("- Just select y or n if the selector is getting all the jobs correctly. Entering y will add the name, link, and selector to companies.csv, so you should make a pr if you want it to be included in the scraping\n")
    lines.append("Here's an example: ")
    lines.append("![Using add_company.py](public/cli.png)")
    lines.append(f"## Current job listings found by phlux ({len(jobs)} companies)\n")
    for company in sorted(jobs):
        postings = jobs[company]
        if not postings:
            continue

        name = f'<a href="{links[company]}"><strong>{company}</strong></a>'
        lines.append("<details>")
        lines.append(f"<summary>{name}</summary>\n")

        for role in postings:
            cleaned = role.replace("\n", " ").strip()
            lines.append(f"- {cleaned}")

        lines.append("</details>\n")

    return "\n".join(lines)

if __name__ == "__main__":
    links = load_company_links("companies.csv") + JPMorganScraper().base_url
    jobs = load_jobs("storage.json")
    readme = generate_readme(jobs, links)

    Path("README.md").write_text(readme, encoding='utf-8')
    print("README.md updated successfully.")
