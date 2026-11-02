"""Tests for phlux/health.py."""
from datetime import date
from unittest.mock import MagicMock, patch

from phlux import health
from phlux.health import EMPTY, FAILING, STALE, STUCK, Issue, find_issues, render_email, status

TODAY = date(2026, 11, 2)
OPEN = [{"title": "Planner", "date": "2026-10-01"}]


def storage(**extra):
    base = {
        "companies": {"Acme": OPEN, "Beta": OPEN, "Gamma": OPEN, "Delta": OPEN,
                      "Echo": [{"title": "Old", "date": "N/A", "closed": "N/A"}], "Fox": OPEN},
        "checked": {"Acme": "2026-11-02", "Beta": "2026-11-02", "Gamma": "2026-10-29", "Delta": "2026-11-02",
                    "Echo": "2026-11-02", "Fox": "2026-11-01"},
        "failing": {"Beta": {"since": "2026-11-01", "error": "HTTPError: 403 Forbidden"}},
        "pending_closures": {"Delta": {"since": "2026-10-30T09:00-04:00", "keys": ["x:1", "x:2"]},
                             "Fox": {"since": "2026-11-02T08:00-05:00", "keys": ["x:9"]}},
    }
    base.update(extra)
    return base


def test_finds_each_kind_most_serious_first():
    issues = find_issues(storage(), ["Acme", "Beta", "Gamma", "Delta", "Echo", "Fox", "Never"], TODAY)
    assert [(i.company, i.kind) for i in issues] == [
        ("Beta", FAILING), ("Never", STALE), ("Gamma", STALE), ("Delta", STUCK), ("Echo", EMPTY)]
    assert issues[0].detail == "HTTPError: 403 Forbidden"
    assert issues[3].detail == "2 postings missing since 2026-10-30"


def test_status_for_the_site():
    assert status(None) == {"status": "ok", "since": None, "detail": ""}
    assert status(Issue("Echo", EMPTY, None, "nothing open matches its search"))["status"] == "ok"
    assert status(Issue("Beta", FAILING, "2026-11-01", "403")) == {"status": "failing", "since": "2026-11-01", "detail": "403"}


def test_email_names_the_problems():
    issues = find_issues(storage(), ["Acme", "Beta", "Echo"], TODAY)
    subject, body = render_email(issues, 3, TODAY)
    assert subject == "phlux health: 1 of 3 companies need a look"
    assert "Scrape failing (1)" in body and "<b>Beta</b> since 2026-11-01: HTTPError: 403 Forbidden" in body
    assert "Nothing listed (1)" in body
    assert render_email([], 3, TODAY)[0] == "phlux health: all 3 companies scraping fine"


def test_send_goes_to_the_alert_address_only():
    cfg = {"from": "me@x.com", "to": "me@x.com", "login": "me@x.com", "internship_bcc": ["friend@x.com"]}
    smtp = MagicMock()
    with patch("phlux.health.load_email_config", return_value=cfg), \
         patch("phlux.health.smtplib.SMTP_SSL") as ssl, \
         patch.dict("os.environ", {"GMAIL_APP_PASSWORD": "pw"}):
        ssl.return_value.__enter__.return_value = smtp
        health.send("subject", "<p>body</p>")
    msg = smtp.send_message.call_args.args[0]
    assert msg["To"] == "me@x.com" and msg["Bcc"] is None
