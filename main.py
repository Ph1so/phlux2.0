"""Entry point: scrape companies, persist results, and send internship email alerts."""
from __future__ import annotations

import html
import json
import logging
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

import pytz

from phlux.config import load_company_list_setting, load_config, load_email_config
from phlux.lists import scrape_scope
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
        filtered = [job for job in jobs_data["jobs"] if filter_fn(job["title"])]
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
        for job in filtered:
            title = job["title"].strip().replace("\n", " ")
            if job.get("url"):
                title = (
                    f'<a href="{html.escape(job["url"])}" target="_blank" '
                    f'style="color: inherit;">{title}</a>'
                )
            location = (
                f" <span style='color: #6b7280;'>· {html.escape(job['location'])}</span>"
                if job.get("location")
                else ""
            )
            lines.append(f"<li style='margin-bottom: 4px; font-family: monospace;'>{title}{location}</li>")
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


# Top-level storage.json key holding the day's first alert of each kind, which
# later alerts that day reply to (see _send_email_impl).
THREADS_KEY = "email_threads"
EASTERN = pytz.timezone("US/Eastern")


def _send_email_impl(
    message: Dict[str, Any],
    subject: str,
    bcc: List[str],
    format_fn: Callable[[Dict[str, Any]], str],
    test: bool,
    email_cfg: Dict[str, Any],
    threads: Optional[Dict[str, Any]] = None,
    kind: str = "",
    to: Optional[str] = None,
) -> None:
    """Build and send an email via Gmail SMTP.

    With *threads* (the ``email_threads`` entry of storage.json), the email
    replies to the first *kind* alert sent today, so Gmail keeps the day's
    alerts in one conversation; Gmail threads on a matching subject plus a
    References header naming a message already in the conversation. When it is
    the day's first, it is recorded in *threads* once sent.

    With *to*, the email goes there instead of to "to" (a test send still goes
    to "to").
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_cfg["from"]
    msg["To"] = email_cfg["to"] if test or not to else to
    if not test and bcc:
        msg["Bcc"] = ", ".join(bcc)

    today = datetime.now(EASTERN).date().isoformat()
    first = (threads or {}).get(kind)
    replying = bool(first) and first.get("date") == today
    msg["Message-ID"] = make_msgid(domain="phlux")
    if replying:
        msg["In-Reply-To"] = first["message_id"]
        msg["References"] = first["message_id"]

    msg.set_content("This email contains HTML. Please view it in an HTML-compatible client.")
    msg.add_alternative(format_fn(message), subtype="html")

    password = os.environ["GMAIL_APP_PASSWORD"]
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(email_cfg["login"], password)
        smtp.send_message(msg)

    if threads is not None and not replying:
        threads[kind] = {"date": today, "message_id": msg["Message-ID"]}


def send_email(message: Dict[str, Any], test: bool = False, threads: Optional[Dict[str, Any]] = None) -> None:
    """Send the internship-alert email via Gmail SMTP, threaded per day when *threads* is given."""
    email_cfg = load_email_config()
    _send_email_impl(
        message,
        subject="🚀 New Internship Alerts!",
        bcc=email_cfg["internship_bcc"],
        format_fn=format_message_html,
        test=test,
        email_cfg=email_cfg,
        threads=threads,
        kind="internship",
    )


def send_email_all(message: Dict[str, Any], test: bool = False, threads: Optional[Dict[str, Any]] = None) -> None:
    """Send every new internship, from every company scraped, to ``all_internships_bcc``.

    They're addressed in To, not Bcc: Gmail sent the first one, with no To
    header, to spam. Everyone on the list sees the others' addresses. "to"
    isn't sent a copy; it gets the usual alert.
    """
    email_cfg = load_email_config()
    _send_email_impl(
        message,
        subject="🚀 New Internship Alerts!",
        bcc=[],
        to=", ".join(email_cfg["all_internships_bcc"]),
        format_fn=format_message_html,
        test=test,
        email_cfg=email_cfg,
        threads=threads,
        kind="internship_all",
    )


def send_email_fulltime(
    message: Dict[str, Any], test: bool = False, threads: Optional[Dict[str, Any]] = None
) -> None:
    """Send the full-time-role alert email via Gmail SMTP, threaded per day when *threads* is given."""
    email_cfg = load_email_config()
    _send_email_impl(
        message,
        subject="💼 New Full-Time Role Alerts!",
        bcc=email_cfg["fulltime_bcc"],
        format_fn=format_message_html_fulltime,
        test=test,
        email_cfg=email_cfg,
        threads=threads,
        kind="fulltime",
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


def only_companies(message: dict, names: Set[str]) -> dict:
    """Return *message* keeping only the companies in *names*."""
    return {**message, "companies": {c: v for c, v in message.get("companies", {}).items() if c in names}}


def has_full_time_roles(message: dict) -> bool:
    """Return True if any job in *message* is a full-time (non-internship) role."""
    return any(
        is_full_time(job["title"])
        for company_data in message.get("companies", {}).values()
        for job in company_data.get("jobs", [])
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """Run the full scrape → store → alert pipeline."""
    load_config()
    manager = ScrapeManager()
    email_cfg = load_email_config()
    everyone = bool(email_cfg["all_internships_bcc"])
    companies, listed = scrape_scope(load_company_data(), load_company_list_setting(), everything=everyone)
    if not companies:
        print("No companies selected — check COMPANY_LIST in config.json.")
        return
    listed_names = {c.name for c in listed}
    # Companies scraped only for all_internships_bcc start out quiet: their
    # boards' current postings are recorded, not emailed as new.
    result = manager.scrape_companies(
        companies=companies, unlisted={c.name for c in companies} - listed_names)
    data = result["data"]
    storage = Path("storage.json")

    storage.write_text(json.dumps(data, indent=2), encoding="utf-8")

    new_jobs = result["new_jobs"]
    if new_jobs.get("companies"):
        update_icons(companies=companies)
        threads = data.setdefault(THREADS_KEY, {})
        # The usual alerts cover the company list only, as before.
        listed_jobs = only_companies(new_jobs, listed_names)
        if has_internships(listed_jobs):
            send_email(listed_jobs, test=False, threads=threads)
        else:
            print("Scrape complete: no new internship/co-op positions found.")
        if everyone and has_internships(new_jobs):
            # A failure here mustn't fail the run: the retry job would scrape
            # again and send the alerts above a second time.
            try:
                send_email_all(new_jobs, test=False, threads=threads)
            except Exception as e:
                logger.error("All-internships email failed: %s", e)
                print(f"All-internships email failed: {e}")
        if not email_cfg["fulltime_enabled"]:
            print("Full-time emails are disabled in config; skipping.")
        elif has_full_time_roles(listed_jobs):
            send_email_fulltime(listed_jobs, test=False, threads=threads)
        else:
            print("Scrape complete: no new full-time positions found.")
        # Saved again so the next run can reply to today's first alert.
        storage.write_text(json.dumps(data, indent=2), encoding="utf-8")
    else:
        print("Scrape complete: no new positions found.")


if __name__ == "__main__":
    main()
