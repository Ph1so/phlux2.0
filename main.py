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
import pytz

import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, WebDriverException

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread_formatting import CellFormat, format_cell_range

from phlux.config import load_config
from phlux.scraping import ScrapeManager, load_company_data, autoApply
from utils import get_driver, update_icons

GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]

def format_message_html(message: dict) -> str:
    """Return HTML body for the notification email."""
    try:
        with open("icons.json", "r", encoding="utf-8") as f:
            icons = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        icons = {}

    lines = [
        '<h1 style="font-family: sans-serif;">🚀 phi\'s little minion has found new internships</h1>',
    ]

    # Add a friendly duck image
    try:
        response = requests.get("https://random-d.uk/api/random")
        if response.status_code == 200:
            duck_url = response.json().get("url")
            lines.append(f'<img src="{duck_url}" alt="Random Duck" width="250"><br>')
            lines.append('<p style="font-size: small; font-style: italic;">A duck a day keeps the internship blues away 🦆</p>')
    except Exception as exc:
        lines.append(f"<p><em>Could not fetch duck: {exc}</em></p>")

    lines.append('<hr style="margin-top: 30px; margin-bottom: 20px;">')

    # Company listings
    for company, jobs in message.get("companies", {}).items():
        icon_url = icons.get(company, {})
        if not isinstance(icon_url, str):
            icon_url = icon_url.get("email", "")
        icon_html = (
            f'<img src="{icon_url}" alt="{company} logo" height="24" style="vertical-align:middle; margin-right:6px;">'
            if icon_url else ""
        )

        lines.append(f'<div style="margin-bottom: 30px;">')
        lines.append(f'<h2 style="margin-bottom: 5px; font-family: monospace;">{icon_html} {company}</h2>')
        lines.append("<ul style='margin-top: 5px;'>")
        for job in jobs["jobs"]:
            cleaned = job["title"].strip().replace("\n", " ")
            lines.append(f"<li style='margin-bottom: 4px; font-family: monospace;'>{cleaned}</li>")
        lines.append("</ul>")
        lines.append(f'<p><strong>🔗 <a style="font-family: monospace;" href="{jobs["link"]}" target="_blank">Apply Here</a></strong></p>')
        lines.append('</div>')
        lines.append('<hr style="margin-top: 20px; margin-bottom: 20px;">')

    # Footer
    lines.append('<p style="font-family: monospace;">💻 View all companies at <a href="https://github.com/Ph1so/phlux2.0" target="_blank">github.com/Ph1so/phlux2.0</a></p>')

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
    Update the Google Sheet with new internship job titles, the current date (no leading 0s), and "Applied".
    Right-aligns the date column.
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

    col_values = worksheet.col_values(1)
    start_row = len(col_values) + 1
    eastern_timezone = pytz.timezone('US/Eastern')
    now = f"{datetime.now(eastern_timezone).month}/{datetime.now(eastern_timezone).day}/{datetime.now(eastern_timezone).year}"

    rows = [["Susquehanna - "+job, now, "Applied"] for job in jobs]
    end_row = start_row + len(rows) - 1
    worksheet.update(values=rows, range_name=f"A{start_row}:C{end_row}")

    right_align = CellFormat(horizontalAlignment='RIGHT')
    format_cell_range(worksheet, f"B{start_row}:B{end_row}", right_align)
    

def main() -> None:
    config = load_config()
    manager = ScrapeManager()
    companies = load_company_data()
    result = manager.scrape_companies(companies=companies)
    data = result["data"]
    new_jobs = result["new_jobs"]

    # Special case: run autoApply only after all scraping
    # susquehanna_jobs = new_jobs.get("companies", {}).get("Susquehanna", {}).get("jobs", [])
    # susquehanna_jobs_titles = []
    # for job in susquehanna_jobs:
    #     if "Summer 2026" in job["title"]:
    #         susquehanna_jobs_titles.append(job["title"])
    
    # print(json.dumps(new_jobs, indent=2))
    # if susquehanna_jobs_titles:
    #     print(f"Auto applying to : {susquehanna_jobs_titles}")
    #     autoApply(susquehanna_jobs_titles, new_jobs["companies"].get("Susquehanna").get("link"))
    #     update_internship_tracker(susquehanna_jobs_titles)

    Path("storage.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    if new_jobs.get("companies"):
        update_icons(companies=companies)
        send_email(new_jobs, test = False)

if __name__ == "__main__":
    main()

