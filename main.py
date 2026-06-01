"""Entry point: scrape companies, persist results, and send internship email alerts."""
from __future__ import annotations

import json
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import List

import gspread
import pytz
from gspread_formatting import CellFormat, format_cell_range
from oauth2client.service_account import ServiceAccountCredentials

from phlux.config import load_config
from phlux.scraping import ScrapeManager, load_company_data
from phlux.utils import is_internship, update_icons

GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]

# ── Email ─────────────────────────────────────────────────────────────────────

def format_message_html(message: dict) -> str:
    """Return the HTML body for the internship-alert email.

    Iterates over companies in *message*, filters each company's job list to
    internship / co-op titles only, and builds a styled HTML section for each.

    Args:
        message: Dict with a ``"companies"`` key mapping company name →
                 ``{"jobs": [...], "link": "..."}``.

    Returns:
        HTML string ready to embed in an ``EmailMessage``.
    """
    try:
        with open("icons.json", "r", encoding="utf-8") as f:
            icons = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        icons = {}

    lines = ['<h1 style="font-family: monospace;">Internships from Phi</h1>']
    lines.append('<hr style="margin-top: 30px; margin-bottom: 20px;">')

    for company, jobs_data in message.get("companies", {}).items():
        filtered = [
            job["title"].strip().replace("\n", " ")
            for job in jobs_data["jobs"]
            if is_internship(job["title"])
        ]
        if not filtered:
            continue

        icon_url = icons.get(company, "")
        if not isinstance(icon_url, str):
            icon_url = icon_url.get("email", "")

        icon_html = (
            f'<img src="{icon_url}" alt="{company} logo" height="24" '
            f'style="vertical-align:middle; margin-right:6px;">'
            if icon_url
            else ""
        )

        lines.append('<div style="margin-bottom: 30px;">')
        lines.append(
            f'<h2 style="margin-bottom: 5px; font-family: monospace;">'
            f'{icon_html} {company}</h2>'
        )
        lines.append("<ul style='margin-top: 5px;'>")
        for title in filtered:
            lines.append(f"<li style='margin-bottom: 4px; font-family: monospace;'>{title}</li>")
        lines.append("</ul>")
        lines.append(
            f'<p><strong>🔗 <a style="font-family: monospace;" '
            f'href="{jobs_data["link"]}" target="_blank">Apply Here</a></strong></p>'
        )
        lines.append("</div>")
        lines.append('<hr style="margin-top: 20px; margin-bottom: 20px;">')

    lines.append(
        '<p style="font-family: monospace;">💻 View all companies at '
        '<a href="https://github.com/Ph1so/phlux2.0" target="_blank">'
        "github.com/Ph1so/phlux2.0</a></p>"
    )
    return "\n".join(lines)


def send_email(message: dict, test: bool = False) -> None:
    """Send the internship-alert email via Gmail SMTP.

    Args:
        message: Structured job data passed to :func:`format_message_html`.
        test: If True, omit BCC recipients (useful for local testing).
    """
    msg = EmailMessage()
    msg["Subject"] = "🚀 New Internship Alerts!"
    msg["From"] = "phiwe3296@gmail.com"
    msg["To"] = "phiwe3296@gmail.com"
    if not test:
        msg["Bcc"] = "jameseyeh@gmail.com,alex_yeh2@yahoo.com,dustin.nguyen16@gmail.com, brian.hwanhee.cho@gmail.com, jack.lipengzhu@gmail.com"

    msg.set_content("This email contains HTML. Please view it in an HTML-compatible client.")
    msg.add_alternative(format_message_html(message), subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login("phiwe3296@gmail.com", GMAIL_APP_PASSWORD)
        smtp.send_message(msg)


def has_internships(message: dict) -> bool:
    """Return True if any job in *message* matches internship / co-op keywords.

    Args:
        message: Same structured dict as accepted by :func:`send_email`.
    """
    return any(
        is_internship(job["title"])
        for company_data in message.get("companies", {}).values()
        for job in company_data.get("jobs", [])
    )


# ── Google Sheets ─────────────────────────────────────────────────────────────

def update_internship_tracker(jobs: List[str]) -> None:
    """Append newly found Susquehanna internship titles to the tracking sheet.

    Writes each job as a row of ``[company – title, date, "Applied"]`` and
    right-aligns the date column.

    Args:
        jobs: List of job title strings to record.
    """
    creds_dict = json.loads(os.environ["GOOGLE_KEY_JSON"])
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    worksheet = client.open_by_key("1pZMYgV4GJZJIwyTSG4-ufWeUnJNE7ZQzcFk35qJj7QI").worksheet("Phi26")
    start_row = len(worksheet.col_values(1)) + 1

    eastern = pytz.timezone("US/Eastern")
    now = datetime.now(eastern)
    today = f"{now.month}/{now.day}/{now.year}"

    rows = [["Susquehanna - " + job, today, "Applied"] for job in jobs]
    end_row = start_row + len(rows) - 1
    worksheet.update(values=rows, range_name=f"A{start_row}:C{end_row}")
    format_cell_range(worksheet, f"B{start_row}:B{end_row}", CellFormat(horizontalAlignment="RIGHT"))


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """Run the full scrape → store → alert pipeline."""
    load_config()
    manager = ScrapeManager()
    companies = load_company_data()
    result = manager.scrape_companies(companies=companies)

    Path("storage.json").write_text(json.dumps(result["data"], indent=2), encoding="utf-8")

    new_jobs = result["new_jobs"]
    if new_jobs.get("companies") and has_internships(new_jobs):
        update_icons(companies=companies)
        send_email(new_jobs, test=False)
    else:
        print("Scrape complete: no new internship/co-op positions found.")


if __name__ == "__main__":
    main()
