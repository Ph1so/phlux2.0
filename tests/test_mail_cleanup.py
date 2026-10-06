"""Tests for phlux/mail_cleanup.py."""
from phlux.mail_cleanup import is_bot_internship_alert

BOT = "phiwe3296@gmail.com"


def _headers(from_: str, subject: str) -> bytes:
    from email.header import Header
    encoded = Header(subject, "utf-8").encode()
    return f"From: {from_}\r\nSubject: {encoded}\r\n\r\n".encode()


def test_matches_bot_internship_alert():
    assert is_bot_internship_alert(_headers(BOT, "🚀 New Internship Alerts!"), BOT)


def test_matches_display_name_and_case():
    assert is_bot_internship_alert(_headers(f"Phi <{BOT.upper()}>", "🚀 New Internship Alerts!"), BOT)


def test_rejects_other_sender():
    assert not is_bot_internship_alert(_headers("someone@gmail.com", "🚀 New Internship Alerts!"), BOT)


def test_rejects_fulltime_alert():
    assert not is_bot_internship_alert(_headers(BOT, "💼 New Full-Time Role Alerts!"), BOT)


def test_rejects_reply_and_forward():
    assert not is_bot_internship_alert(_headers(BOT, "Re: 🚀 New Internship Alerts!"), BOT)
    assert not is_bot_internship_alert(_headers(BOT, "Fwd: 🚀 New Internship Alerts!"), BOT)


def test_rejects_other_email_from_self():
    assert not is_bot_internship_alert(_headers(BOT, "Internship notes"), BOT)
