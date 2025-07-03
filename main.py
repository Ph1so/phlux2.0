"""Command line interface for scraping job postings."""
from __future__ import annotations

import json
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import List
import os
from datetime import datetime

import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, WebDriverException

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from phlux.config import load_config
from phlux.scraping import ScrapeManager, load_company_data, autoApply
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


def update_internship_tracker(jobs: List[str]) -> None:
    """
    Update the Google Sheet with new internship job titles, the current date, and "Applied" status.
    - Sheet: https://docs.google.com/spreadsheets/d/1pZMYgV4GJZJIwyTSG4-ufWeUnJNE7ZQzcFk35qJj7QI/edit#gid=393882033
    - Tab: "Phi26"
    - Columns:
        A: Job title
        B: Date added (MM/DD/YYYY)
        C: Applied status
    """
    creds_dict = json.loads(os.environ["GOOGLE_KEY_JSON"])
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    spreadsheet = client.open_by_key("1pZMYgV4GJZJIwyTSG4-ufWeUnJNE7ZQzcFk35qJj7QI")
    worksheet = spreadsheet.worksheet("Phi26")

    # Find first empty row in Column A
    col_values = worksheet.col_values(1)
    start_row = len(col_values) + 1

    # Current date for all entries
    now = datetime.now().strftime("%m/%d/%Y")

    # Prepare rows: [[Job Title, Date, "Applied"]]
    rows = [[job, now, "Applied"] for job in jobs]

    # Update columns A–C (e.g., A12:C20)
    end_row = start_row + len(rows) - 1
    worksheet.update(f"A{start_row}:C{end_row}", rows)

def main() -> None:
    config = load_config()
    manager = ScrapeManager()
    companies = load_company_data()
    result = manager.scrape_companies(companies=companies)
    data = result["data"]
    new_jobs = result["new_jobs"]

    # Special case: run autoApply only after all scraping
    susquehanna_jobs = new_jobs["companies"].get("Susquehanna", []).get("jobs", [])
    print(new_jobs)
    if susquehanna_jobs:
        print(f"Auto apply: {susquehanna_jobs}")
        autoApply(susquehanna_jobs, new_jobs["companies"].get("Susquehanna").get("link"))
        update_internship_tracker(susquehanna_jobs)

    Path("storage.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    if new_jobs.get("companies"):
        send_email(new_jobs, test = True)

if __name__ == "__main__":
    main()

