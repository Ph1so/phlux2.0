"""Tests for main.py — email formatting and send functions."""
import json
import os
from unittest.mock import MagicMock, mock_open, patch

import pytest

import main
from phlux.models import Company
from main import (
    format_message_html,
    format_message_html_fulltime,
    has_full_time_roles,
    has_internships,
    send_email,
    send_email_all,
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

    def test_shows_location_escaped(self, intern_message):
        intern_message["companies"]["Acme"]["jobs"][0]["location"] = "R&D Campus <Munich> +1"
        html = self._call(intern_message)
        assert "Software Engineer Intern <span" in html
        assert "· R&amp;D Campus &lt;Munich&gt; +1</span>" in html

    def test_no_location_span_without_location(self, intern_message):
        html = self._call(intern_message)
        assert "·" not in html

    def test_links_title_to_its_posting(self, intern_message):
        intern_message["companies"]["Acme"]["jobs"][0]["url"] = "https://jobs.lever.co/acme/1?a=1&b=2"
        html = self._call(intern_message)
        assert '<a href="https://jobs.lever.co/acme/1?a=1&amp;b=2" target="_blank"' in html
        assert ">Software Engineer Intern</a>" in html

    def test_plain_title_without_a_link(self, intern_message):
        html = self._call(intern_message)
        assert "Software Engineer Intern</a>" not in html


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


class TestEmailThreading:
    """A day's alerts reply to its first one so Gmail keeps them in one thread."""

    def _send(self, message, threads, fn=send_email):
        sent = []
        smtp_cls, smtp_instance = _make_smtp_mock()
        smtp_instance.send_message.side_effect = lambda msg: sent.append(msg)
        with patch("main.smtplib.SMTP_SSL", smtp_cls), \
             patch("builtins.open", mock_open(read_data="{}")), \
             patch.dict(os.environ, {"GMAIL_APP_PASSWORD": "secret"}):
            fn(message, test=True, threads=threads)
        return sent[0]

    def _today(self):
        return main.datetime.now(main.EASTERN).date().isoformat()

    def test_first_alert_of_the_day_starts_the_thread(self, intern_message):
        threads = {"internship": {"date": "2026-01-01", "message_id": "<old@phlux>"}}
        msg = self._send(intern_message, threads)
        assert "In-Reply-To" not in msg and "References" not in msg
        assert threads["internship"] == {"date": self._today(), "message_id": msg["Message-ID"]}

    def test_later_alerts_reply_to_the_first(self, intern_message):
        threads = {"internship": {"date": self._today(), "message_id": "<root@phlux>"}}
        msg = self._send(intern_message, threads)
        assert msg["In-Reply-To"] == "<root@phlux>"
        assert msg["References"] == "<root@phlux>"
        assert msg["Subject"] == "🚀 New Internship Alerts!"  # Gmail threads only on a matching subject
        assert threads["internship"]["message_id"] == "<root@phlux>"

    def test_kinds_keep_separate_threads(self, fulltime_message):
        threads = {"internship": {"date": self._today(), "message_id": "<root@phlux>"}}
        msg = self._send(fulltime_message, threads, fn=send_email_fulltime)
        assert "In-Reply-To" not in msg
        assert threads["fulltime"]["message_id"] == msg["Message-ID"]

    def test_failed_send_records_nothing(self, intern_message):
        threads = {}
        smtp_cls, smtp_instance = _make_smtp_mock()
        smtp_instance.send_message.side_effect = OSError("smtp down")
        with patch("main.smtplib.SMTP_SSL", smtp_cls), \
             patch("builtins.open", mock_open(read_data="{}")), \
             patch.dict(os.environ, {"GMAIL_APP_PASSWORD": "secret"}), \
             pytest.raises(OSError):
            send_email(intern_message, test=True, threads=threads)
        assert threads == {}


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


# ── all_internships_bcc ───────────────────────────────────────────────────────

ALL_CFG = {
    "from": "me@x.com", "to": "me@x.com", "login": "me@x.com",
    "internship_bcc": ["friend@x.com"], "all_internships_bcc": ["all@x.com"],
    "fulltime_enabled": False, "fulltime_bcc": [],
}


class TestSendEmailAll:
    def _send(self, message, test=False, threads=None):
        sent = []
        smtp_cls, smtp_instance = _make_smtp_mock()
        smtp_instance.send_message.side_effect = lambda msg: sent.append(msg)
        with patch("main.load_email_config", return_value=ALL_CFG), \
             patch("main.smtplib.SMTP_SSL", smtp_cls), \
             patch("builtins.open", mock_open(read_data="{}")), \
             patch.dict(os.environ, {"GMAIL_APP_PASSWORD": "secret"}):
            send_email_all(message, test=test, threads=threads)
        return sent[0]

    def test_addressed_to_all_internships_bcc_only(self, intern_message):
        msg = self._send(intern_message)
        assert msg["To"] == "all@x.com"  # a missing To header sent it to spam
        assert msg["Bcc"] is None  # "to" gets the usual alert, not a second copy
        assert msg["Subject"] == "🚀 New Internship Alerts!"

    def test_test_send_goes_to_the_alert_address(self, intern_message):
        msg = self._send(intern_message, test=True)
        assert msg["To"] == "me@x.com" and msg["Bcc"] is None

    def test_keeps_its_own_thread(self, intern_message):
        today = main.datetime.now(main.EASTERN).date().isoformat()
        threads = {"internship": {"date": today, "message_id": "<root@phlux>"}}
        msg = self._send(intern_message, threads=threads)
        assert "In-Reply-To" not in msg
        assert threads["internship_all"]["message_id"] == msg["Message-ID"]


class TestMainAlertsByAudience:
    """The usual alert covers the company list; all_internships_bcc gets every company."""

    def _run(self, tmp_path, monkeypatch, new_jobs, cfg=ALL_CFG, all_fails=False):
        monkeypatch.chdir(tmp_path)
        listed = [Company("Robo", "https://robo.com", "sel")]
        other = [Company("Bank", "https://bank.com", "sel")]
        everything = listed + other if cfg["all_internships_bcc"] else listed
        manager = MagicMock()
        manager.return_value.scrape_companies.return_value = {"data": {"companies": {}}, "new_jobs": new_jobs}
        sends = {}
        with patch("main.load_config"), patch("main.ScrapeManager", manager), \
             patch("main.load_email_config", return_value=cfg), \
             patch("main.load_company_data", return_value=everything), \
             patch("main.scrape_scope", return_value=(everything, listed)), \
             patch("main.update_icons"), \
             patch("main.send_email", side_effect=lambda m, **kw: sends.setdefault("usual", m)), \
             patch("main.send_email_all", side_effect=OSError("smtp down") if all_fails
                   else lambda m, **kw: sends.setdefault("all", m)):
            main.main()
        return sends, manager.return_value.scrape_companies.call_args.kwargs

    @staticmethod
    def _jobs(*companies):
        return {"companies": {c: {"jobs": [{"title": "Intern", "date": "2026-11-11"}], "link": ""}
                              for c in companies}}

    def test_usual_alert_keeps_to_the_list(self, tmp_path, monkeypatch):
        sends, _ = self._run(tmp_path, monkeypatch, self._jobs("Robo", "Bank"))
        assert list(sends["usual"]["companies"]) == ["Robo"]
        assert list(sends["all"]["companies"]) == ["Robo", "Bank"]

    def test_only_unlisted_internships_skip_the_usual_alert(self, tmp_path, monkeypatch):
        sends, _ = self._run(tmp_path, monkeypatch, self._jobs("Bank"))
        assert "usual" not in sends and list(sends["all"]["companies"]) == ["Bank"]

    def test_unlisted_companies_start_quiet(self, tmp_path, monkeypatch):
        _, kwargs = self._run(tmp_path, monkeypatch, self._jobs("Robo"))
        assert kwargs["unlisted"] == {"Bank"}

    def test_nobody_on_all_internships_bcc_sends_no_all_email(self, tmp_path, monkeypatch):
        sends, kwargs = self._run(tmp_path, monkeypatch, self._jobs("Robo"), cfg={**ALL_CFG, "all_internships_bcc": []})
        assert list(sends) == ["usual"] and kwargs["unlisted"] == set()

    def test_failed_all_email_does_not_fail_the_run(self, tmp_path, monkeypatch):
        sends, _ = self._run(tmp_path, monkeypatch, self._jobs("Robo"), all_fails=True)
        assert list(sends) == ["usual"]
        assert (tmp_path / "storage.json").exists()

