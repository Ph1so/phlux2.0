"""Find companies whose scraping has gone wrong, for the site and a weekly email.

A broken scraper fails quietly: the bot just stops seeing a company's postings.
Storage already holds what's needed to notice, so nothing here scrapes:

* ``failing`` (see :func:`phlux.scraping.track_failures`): the scrape raises,
  e.g. a board that answers 403 or was deleted.
* ``checked`` (see :func:`phlux.scraping.track_closures`): the last scrape
  trusted to list a company's postings. One that hasn't been checked for
  :data:`STALE_DAYS` without failing is a page scrape coming back empty.
* ``pending_closures``: a big drop is held for a second look an hour later. One
  still held after :data:`STUCK_DAYS` means the second look never came.
* A company checked recently with nothing open at all is listed too, as a
  board that may have moved; often it simply isn't hiring.

``python -m phlux.health`` prints the report; ``--email`` sends it to the
address alerts go to (never the BCC list), which the weekly workflow does.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import smtplib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from typing import Dict, Iterable, List, Optional

import pytz

from .config import load_company_list_setting, load_email_config
from .lists import REPO_ROOT, scrape_scope
from .scraping import CHECKED_KEY, FAILING_KEY, PENDING_KEY, load_company_data

STALE_DAYS = 2
STUCK_DAYS = 1
EASTERN = pytz.timezone("US/Eastern")

# Issue kinds, most serious first.
FAILING, STALE, STUCK, EMPTY = "failing", "stale", "stuck", "empty"
TITLES = {
    FAILING: "Scrape failing",
    STALE: "Not checked lately",
    STUCK: "Drop waiting for a second look",
    EMPTY: "Nothing listed",
}


@dataclass(frozen=True)
class Issue:
    company: str
    kind: str
    since: Optional[str]  # ISO date the problem started, when known
    detail: str


def find_issues(storage: Dict, companies: Iterable[str], today: date) -> List[Issue]:
    """Return the problems with *companies*' scraping, most serious first."""
    failing = storage.get(FAILING_KEY, {})
    checked = storage.get(CHECKED_KEY, {})
    pending = storage.get(PENDING_KEY, {})
    stored = storage.get("companies", {})
    issues: List[Issue] = []
    for name in companies:
        if name in failing:
            issues.append(Issue(name, FAILING, failing[name]["since"], failing[name]["error"]))
            continue
        last = checked.get(name)
        if not last or date.fromisoformat(last) < today - timedelta(days=STALE_DAYS):
            issues.append(Issue(name, STALE, last, f"last checked {last}" if last else "never checked"))
            continue
        held = pending.get(name)
        if held and datetime.fromisoformat(held["since"]).date() < today - timedelta(days=STUCK_DAYS):
            issues.append(Issue(name, STUCK, held["since"][:10], f"{len(held['keys'])} postings missing since {held['since'][:10]}"))
            continue
        if not any(isinstance(j, dict) and "closed" not in j for j in stored.get(name, [])):
            issues.append(Issue(name, EMPTY, None, "nothing open matches its search"))
    order = list(TITLES)
    return sorted(issues, key=lambda i: (order.index(i.kind), i.since or "", i.company))


def status(issue: Optional[Issue]) -> Dict:
    """Return a company's health for the site: ``{"status", "since", "detail"}``."""
    if issue is None or issue.kind == EMPTY:
        return {"status": "ok", "since": None, "detail": issue.detail if issue else ""}
    return {"status": issue.kind, "since": issue.since, "detail": issue.detail}


def render_email(issues: List[Issue], total: int, today: date) -> tuple[str, str]:
    """Return the weekly email's subject and HTML body."""
    serious = [i for i in issues if i.kind != EMPTY]
    subject = (f"phlux health: {len(serious)} of {total} companies need a look" if serious
               else f"phlux health: all {total} companies scraping fine")
    lines = [f'<h2 style="font-family: sans-serif;">Scraper health, {today:%b %-d}</h2>',
             f'<p style="font-family: sans-serif;">{total - len(serious)} of {total} companies scraped fine this week.</p>']
    for kind, title in TITLES.items():
        group = [i for i in issues if i.kind == kind]
        if not group:
            continue
        lines.append(f'<h3 style="font-family: sans-serif;">{title} ({len(group)})</h3><ul>')
        for issue in group:
            since = f" since {issue.since}" if issue.since and kind != STALE else ""
            lines.append(f'<li style="font-family: monospace;"><b>{html.escape(issue.company)}</b>{since}: '
                         f'{html.escape(issue.detail)}</li>')
        lines.append("</ul>")
    return subject, "\n".join(lines)


def send(subject: str, body: str) -> None:
    """Email *body* to the alert address only (never the BCC list)."""
    cfg = load_email_config()
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, cfg["from"], cfg["to"]
    msg.set_content("This email contains HTML. Please view it in an HTML-compatible client.")
    msg.add_alternative(body, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(cfg["login"], os.environ["GMAIL_APP_PASSWORD"])
        smtp.send_message(msg)


def active_companies() -> List[str]:
    """Names of the companies the bot scrapes, including any scraped only for ``all_internships_bcc``."""
    companies, _ = scrape_scope(load_company_data(REPO_ROOT / "companies.csv"), load_company_list_setting(),
                                everything=bool(load_email_config()["all_internships_bcc"]))
    return list(dict.fromkeys(c.name for c in companies))


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m phlux.health", description=__doc__.splitlines()[0])
    parser.add_argument("--email", action="store_true", help="Send the report to the alert address.")
    args = parser.parse_args(argv)
    storage = json.loads((REPO_ROOT / "storage.json").read_text(encoding="utf-8"))
    names = active_companies()
    today = datetime.now(EASTERN).date()
    issues = find_issues(storage, names, today)
    subject, body = render_email(issues, len(names), today)
    print(subject)
    for issue in issues:
        print(f"  {issue.kind:8} {issue.company}: {issue.detail}")
    if args.email:
        send(subject, body)
        print("Sent.")


if __name__ == "__main__":
    main()
