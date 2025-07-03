"""Command line interface for scraping job postings."""
from __future__ import annotations

import json
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import List
import os

import requests
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, WebDriverException

from phlux.config import load_config
from phlux.scraping import ScrapeManager, load_company_data
from utils import get_driver

GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]


def format_message_html(message: dict) -> str:
    """Return HTML body for the notification email."""
    lines = ["<h2>phi's little minion has found new internships</h2><br>"]
    try:
        response = requests.get("https://random-d.uk/api/random")
        if response.status_code == 200:
            duck_url = response.json().get("url")
            lines.append(f'<img src="{duck_url}" alt="Random Duck" width="300"><br>')
    except Exception as exc:  # noqa: BLE001
        lines.append(f"<p><em>Error fetching duck: {exc}</em></p><br>")

    for company, info in message.get("companies", {}).items():
        lines.append(f"<h3>🔹 {company}</h3>")
        lines.append("<ul>")
        for job in info["jobs"]:
            lines.append(f"<li>{job}</li>")
        lines.append("</ul>")
        lines.append(f'<p>🔗 <a href="{info["link"]}">Apply Here</a></p><br>')

    lines.append('<a href="https://github.com/Ph1so/phlux2.0">All Jobs List</a>')
    return "\n".join(lines)


def send_email(message: dict, test: bool = False) -> None:
    """Send the notification email."""
    msg = EmailMessage()
    msg["Subject"] = "🚀 New Internship Alerts!"
    msg["From"] = "phiwe3296@gmail.com"
    msg["To"] = "phiwe3296@gmail.com"
    if not test:
        msg["Cc"] = "Nicolezcui@gmail.com, pham0579@umn.edu, ronak@ronakpjain.com"
    html_content = format_message_html(message)
    msg.set_content("This email contains HTML. Please view it in an HTML-compatible client.")
    msg.add_alternative(html_content, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login("phiwe3296@gmail.com", GMAIL_APP_PASSWORD)
        smtp.send_message(msg)

def autoApply(jobs: List[str], url: str):
    """
    Takes a list of job names and auto-applies to each job on SIG's careers site.
    """
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN not set in environment")

    repo = "Ph1so/phlux2.0"
    workflow_id = "auto-apply.yml"

    try:
        driver = get_driver()
        driver.get(url)

        for job in jobs:
            print(f"Auto Apply Job: {job}")
            if "Summer 2026" not in job:
                continue  # skip irrelevant jobs

            try:
                element = driver.find_element(By.XPATH, f"//*[contains(normalize-space(), '{job}')]")
                job_seqno = element.get_attribute("data-ph-at-job-seqno-text")
            except NoSuchElementException:
                print(f"⚠️ Element for job '{job}' not found on page.")
                continue

            if not job_seqno:
                print(f"⚠️ No job_seqno found for job '{job}'. Skipping.")
                continue

            apply_url = f"https://careers.sig.com/apply?jobSeqNo={job_seqno}"
            try:
                response = requests.post(
                    f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_id}/dispatches",
                    headers={
                        "Accept": "application/vnd.github+json",
                        "Authorization": f"Bearer {token}",
                    },
                    json={
                        "ref": "main",
                        "inputs": {
                            "url": apply_url
                        }
                    },
                    timeout=10  # prevent hanging
                )
                if response.status_code == 204:
                    print(f"✅ Successfully triggered workflow for: {job}")
                else:
                    print(f"❌ Failed to trigger workflow for: {job} | Status: {response.status_code} | Response: {response.text}")

            except requests.RequestException as e:
                print(f"❌ HTTP error while applying to job '{job}': {e}")

    except WebDriverException as e:
        print(f"❌ WebDriver error: {e}")

    finally:
        try:
            driver.quit()
        except Exception:
            pass

def main() -> None:
    config = load_config()
    manager = ScrapeManager()
    companies = load_company_data()
    result = manager.scrape_companies(companies=companies)
    data = result["data"]
    new_jobs = result["new_jobs"]

    # Special case: run autoApply only after all scraping
    susquehanna_jobs = new_jobs["companies"].get("Susquehanna").get("jobs")
    print(new_jobs)
    if susquehanna_jobs:
        print(f"Auto apply: {susquehanna_jobs}")
        autoApply(susquehanna_jobs, new_jobs["companies"].get("Susquehanna").get("link"))

    Path("storage.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    if new_jobs.get("companies"):
        send_email(new_jobs, test = True)

if __name__ == "__main__":
    main()

