"""Entry point: scrape companies, persist results, and send internship email alerts."""
from __future__ import annotations

import json
import logging
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Callable, Dict, List

import gspread
import pytz
from gspread_formatting import CellFormat, format_cell_range
from oauth2client.service_account import ServiceAccountCredentials

from phlux.config import load_config
from phlux.scraping import ScrapeManager, load_company_data
from phlux.utils import is_full_time, is_internship, update_icons

logger = logging.getLogger(__name__)

# ── Email ─────────────────────────────────────────────────────────────────────

def _format_email_html(message: Dict[str, Any], filter_fn: Callable[[str], bool], heading: str) -> str:
    """Build an HTML email body, keeping only jobs that satisfy *filter_fn*."""
    try:
        with open("icons.json", "r", encoding="utf-8") as f:
            icons = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        icons = {}

    lines = [f'<h1 style="font-family: monospace;">{heading}</h1>']
    lines.append('<hr style="margin-top: 30px; margin-bottom: 20px;">')

    for company, jobs_data in message.get("companies", {}).items():
        filtered = [
            job["title"].strip().replace("\n", " ")
            for job in jobs_data["jobs"]
            if filter_fn(job["title"])
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


def format_message_html(message: Dict[str, Any]) -> str:
    """Return the HTML body for the internship-alert email."""
    return _format_email_html(message, is_internship, "Internships from Phi")


def format_message_html_fulltime(message: Dict[str, Any]) -> str:
    """Return the HTML body for the full-time-role alert email."""
    return _format_email_html(message, is_full_time, "Full-Time Roles from Phi")


def _send_email_impl(
    message: Dict[str, Any],
    subject: str,
    bcc: str,
    format_fn: Callable[[Dict[str, Any]], str],
    test: bool,
) -> None:
    """Build and send an email via Gmail SMTP."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "phiwe3296@gmail.com"
    msg["To"] = "phiwe3296@gmail.com"
    if not test:
        msg["Bcc"] = bcc

    msg.set_content("This email contains HTML. Please view it in an HTML-compatible client.")
    msg.add_alternative(format_fn(message), subtype="html")

    password = os.environ["GMAIL_APP_PASSWORD"]
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login("phiwe3296@gmail.com", password)
        smtp.send_message(msg)


def send_email(message: Dict[str, Any], test: bool = False) -> None:
    """Send the internship-alert email via Gmail SMTP."""
    _send_email_impl(
        message,
        subject="🚀 New Internship Alerts!",
        bcc="jameseyeh@gmail.com,,dustin.nguyen16@gmail.com, brian.hwanhee.cho@gmail.com, jack.lipengzhu@gmail.com",
        format_fn=format_message_html,
        test=test,
    )


def send_email_fulltime(message: Dict[str, Any], test: bool = False) -> None:
    """Send the full-time-role alert email via Gmail SMTP."""
    _send_email_impl(
        message,
        subject="💼 New Full-Time Role Alerts!",
        bcc="alex_yeh2@yahoo.com",
        format_fn=format_message_html_fulltime,
        test=test,
    )


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


def has_full_time_roles(message: dict) -> bool:
    """Return True if any job in *message* is a full-time (non-internship) role."""
    return any(
        is_full_time(job["title"])
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
    raw = os.environ.get("GOOGLE_KEY_JSON")
    if not raw:
        logger.error("GOOGLE_KEY_JSON not set; skipping tracker update.")
        return
    creds_dict = json.loads(raw)
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
    if new_jobs.get("companies"):
        update_icons(companies=companies)
        if has_internships(new_jobs):
            send_email(new_jobs, test=False)
        else:
            print("Scrape complete: no new internship/co-op positions found.")
        if has_full_time_roles(new_jobs):
            send_email_fulltime(new_jobs, test=False)
        else:
            print("Scrape complete: no new full-time positions found.")
    else:
        print("Scrape complete: no new positions found.")


if __name__ == "__main__":
    main()
