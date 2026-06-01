"""Tests for main.py — email formatting and send functions."""
import json
import os
from unittest.mock import MagicMock, mock_open, patch

import pytest

import main
from main import (
    format_message_html,
    format_message_html_fulltime,
    has_full_time_roles,
    has_internships,
    send_email,
    send_email_fulltime,
)


# ── has_internships / has_full_time_roles ─────────────────────────────────────

class TestHasInternships:
    def test_true_when_intern_job_present(self, intern_message):
        assert has_internships(intern_message) is True

    def test_false_when_only_fulltime(self, fulltime_message):
        assert has_internships(fulltime_message) is False

    def test_false_for_empty_companies(self):
        assert has_internships({"companies": {}}) is False

    def test_true_in_mixed_message(self, mixed_message):
        assert has_internships(mixed_message) is True


class TestHasFullTimeRoles:
    def test_true_when_fulltime_present(self, fulltime_message):
        assert has_full_time_roles(fulltime_message) is True

    def test_false_for_empty_companies(self):
        assert has_full_time_roles({"companies": {}}) is False

    def test_false_when_only_internships(self, intern_message):
        assert has_full_time_roles(intern_message) is False

    def test_true_in_mixed_message(self, mixed_message):
        assert has_full_time_roles(mixed_message) is True


# ── format_message_html (internships) ─────────────────────────────────────────

class TestFormatMessageHtml:
    def _call(self, message, icons=None):
        icons_data = json.dumps(icons or {})
        with patch("builtins.open", mock_open(read_data=icons_data)):
            return format_message_html(message)

    def test_contains_company_name(self, intern_message):
        html = self._call(intern_message)
        assert "Acme" in html

    def test_contains_job_title(self, intern_message):
        html = self._call(intern_message)
        assert "Software Engineer Intern" in html

    def test_contains_apply_link(self, intern_message):
        html = self._call(intern_message)
        assert "https://acme.com/careers" in html

    def test_filters_out_fulltime_jobs(self, fulltime_message):
        html = self._call(fulltime_message)
        # No intern jobs → company section absent
        assert "Apply Here" not in html

    def test_includes_img_tag_when_icon_exists(self, intern_message):
        icons = {"Acme": "https://cdn.example.com/acme.png"}
        html = self._call(intern_message, icons=icons)
        assert "<img" in html
        assert "https://cdn.example.com/acme.png" in html

    def test_omits_img_tag_when_no_icon(self, intern_message):
        html = self._call(intern_message, icons={})
        assert "<img" not in html

    def test_handles_dict_icon_format(self, intern_message):
        icons = {"Acme": {"email": "https://cdn.example.com/acme.png"}}
        html = self._call(intern_message, icons=icons)
        assert "https://cdn.example.com/acme.png" in html

    def test_handles_missing_icons_file(self, intern_message):
        with patch("builtins.open", side_effect=FileNotFoundError):
            html = format_message_html(intern_message)
        assert "Acme" in html  # still renders, just no icons

    def test_returns_string(self, intern_message):
        html = self._call(intern_message)
        assert isinstance(html, str)


# ── format_message_html_fulltime ──────────────────────────────────────────────

class TestFormatMessageHtmlFulltime:
    def _call(self, message, icons=None):
        icons_data = json.dumps(icons or {})
        with patch("builtins.open", mock_open(read_data=icons_data)):
            return format_message_html_fulltime(message)

    def test_excludes_internship_title(self, intern_message):
        html = self._call(intern_message)
        assert "Apply Here" not in html  # intern-only → no FT section rendered

    def test_includes_fulltime_title(self, fulltime_message):
        html = self._call(fulltime_message)
        assert "Software Engineer" in html

    def test_contains_company_name(self, fulltime_message):
        html = self._call(fulltime_message)
        assert "Acme" in html

    def test_contains_apply_link(self, fulltime_message):
        html = self._call(fulltime_message)
        assert "https://acme.com/careers" in html


# ── send_email / send_email_fulltime ──────────────────────────────────────────

def _make_smtp_mock():
    smtp_instance = MagicMock()
    smtp_cls = MagicMock()
    smtp_cls.return_value.__enter__ = MagicMock(return_value=smtp_instance)
    smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
    return smtp_cls, smtp_instance


class TestSendEmail:
    def test_calls_smtp_login_with_password(self, intern_message):
        smtp_cls, smtp_instance = _make_smtp_mock()
        with patch("main.smtplib.SMTP_SSL", smtp_cls), \
             patch("builtins.open", mock_open(read_data="{}")), \
             patch.dict(os.environ, {"GMAIL_APP_PASSWORD": "secret"}):
            send_email(intern_message, test=True)
        smtp_instance.login.assert_called_once_with("phiwe3296@gmail.com", "secret")

    def test_calls_send_message(self, intern_message):
        smtp_cls, smtp_instance = _make_smtp_mock()
        with patch("main.smtplib.SMTP_SSL", smtp_cls), \
             patch("builtins.open", mock_open(read_data="{}")), \
             patch.dict(os.environ, {"GMAIL_APP_PASSWORD": "secret"}):
            send_email(intern_message, test=True)
        smtp_instance.send_message.assert_called_once()

    def test_test_mode_omits_bcc(self, intern_message):
        sent_msgs = []
        smtp_cls, smtp_instance = _make_smtp_mock()
        smtp_instance.send_message.side_effect = lambda msg: sent_msgs.append(msg)

        with patch("main.smtplib.SMTP_SSL", smtp_cls), \
             patch("builtins.open", mock_open(read_data="{}")), \
             patch.dict(os.environ, {"GMAIL_APP_PASSWORD": "secret"}):
            send_email(intern_message, test=True)

        assert sent_msgs, "send_message was not called"
        assert "Bcc" not in sent_msgs[0]


class TestSendEmailFulltime:
    def test_uses_fulltime_subject(self, fulltime_message):
        sent_msgs = []
        smtp_cls, smtp_instance = _make_smtp_mock()
        smtp_instance.send_message.side_effect = lambda msg: sent_msgs.append(msg)

        with patch("main.smtplib.SMTP_SSL", smtp_cls), \
             patch("builtins.open", mock_open(read_data="{}")), \
             patch.dict(os.environ, {"GMAIL_APP_PASSWORD": "secret"}):
            send_email_fulltime(fulltime_message, test=True)

        assert sent_msgs, "send_message was not called"
        assert "Full-Time" in sent_msgs[0]["Subject"]

    def test_calls_smtp_login(self, fulltime_message):
        smtp_cls, smtp_instance = _make_smtp_mock()
        with patch("main.smtplib.SMTP_SSL", smtp_cls), \
             patch("builtins.open", mock_open(read_data="{}")), \
             patch.dict(os.environ, {"GMAIL_APP_PASSWORD": "secret"}):
            send_email_fulltime(fulltime_message, test=True)
        smtp_instance.login.assert_called_once()
