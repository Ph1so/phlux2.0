import json
import csv
from pathlib import Path

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

    lines.append("| Company | Role |")
    lines.append("| :------ | :--- |")
    for company in sorted(jobs):
        postings = jobs[company]
        if not postings:
            continue

        name = f"[{company}]({links[company]})" if company in links else company
        lines.append(f"|{name}|{postings[0]}|")
        for role in postings[1:]:
            lines.append(f"| ↳ | {role.strip().replace("\n", " ")}|")

    return "\n".join(lines)

if __name__ == "__main__":
    links = load_company_links("companies.csv")
    jobs = load_jobs("storage.json")
    readme = generate_readme(jobs, links)

    Path("README.md").write_text(readme, encoding='utf-8')
    print("README.md updated successfully.")
