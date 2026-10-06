"""Trash internship-alert emails sent by this bot once they are older than a cutoff.

Only messages that match *all* of the following are touched:

* the ``From`` address is exactly the bot's configured sender,
* the decoded ``Subject`` is exactly :data:`INTERNSHIP_SUBJECT` (so replies,
  forwards and the full-time alert are left alone),
* Gmail's received date is older than ``max_age_days``.

Matching messages are moved to Gmail's Trash (recoverable for 30 days), not
permanently expunged.
"""
from __future__ import annotations

import email
import imaplib
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.utils import parseaddr
from typing import List, Optional

from phlux.config import load_email_config

logger = logging.getLogger(__name__)

INTERNSHIP_SUBJECT = "🚀 New Internship Alerts!"
MAX_AGE_DAYS = 14
IMAP_HOST = "imap.gmail.com"


def _decode_subject(raw: Optional[str]) -> str:
    """Return a header value decoded from RFC 2047 encoded-words."""
    if not raw:
        return ""
    return str(make_header(decode_header(raw))).strip()


def is_bot_internship_alert(raw_headers: bytes, sender: str) -> bool:
    """Return True only if *raw_headers* is exactly a bot internship alert."""
    msg = email.message_from_bytes(raw_headers)
    from_addr = parseaddr(msg.get("From", ""))[1].lower()
    return from_addr == sender.lower() and _decode_subject(msg.get("Subject")) == INTERNSHIP_SUBJECT


def _find_folder(imap: imaplib.IMAP4_SSL, flag: str) -> str:
    """Return the name of the mailbox carrying special-use *flag* (e.g. ``\\All``)."""
    _, folders = imap.list()
    for line in folders or []:
        decoded = line.decode()
        if flag in decoded:
            match = re.search(r'"([^"]+)"\s*$', decoded)
            if match:
                return match.group(1)
    raise RuntimeError(f"No Gmail folder with flag {flag}")


def cleanup_old_alerts(max_age_days: int = MAX_AGE_DAYS, dry_run: bool = False) -> List[str]:
    """Move bot internship alerts older than *max_age_days* to Trash.

    Returns the received dates of the messages that were (or would be) trashed.
    """
    email_cfg = load_email_config()
    sender = email_cfg["from"]
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    imap = imaplib.IMAP4_SSL(IMAP_HOST)
    try:
        imap.login(email_cfg["login"], os.environ["GMAIL_APP_PASSWORD"])
        # All Mail covers the inbox copy and the Sent copy in one place.
        imap.select(f'"{_find_folder(imap, chr(92) + "All")}"')

        # Gmail-side prefilter; every hit is re-verified below before trashing.
        query = f'from:{sender} subject:(New Internship Alerts) older_than:{max_age_days}d'
        _, data = imap.uid("SEARCH", "X-GM-RAW", f'"{query}"')
        uids = data[0].split() if data and data[0] else []

        trashed: List[str] = []
        for uid in uids:
            _, fetched = imap.uid("FETCH", uid, "(INTERNALDATE BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
            if not fetched or not isinstance(fetched[0], tuple):
                continue
            meta, headers = fetched[0]
            received = imaplib.Internaldate2tuple(meta)
            if received is None:
                continue
            # Internaldate2tuple returns local time; mktime turns it back into an epoch.
            received_at = datetime.fromtimestamp(time.mktime(received), tz=timezone.utc)
            if received_at >= cutoff or not is_bot_internship_alert(headers, sender):
                continue

            if not dry_run:
                imap.uid("STORE", uid, "+X-GM-LABELS", "\\Trash")
            trashed.append(f"{received_at:%Y-%m-%d %H:%M} UTC")

        logger.info("%s %d internship alert(s) older than %d days",
                    "Would trash" if dry_run else "Trashed", len(trashed), max_age_days)
        return trashed
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for item in cleanup_old_alerts(dry_run="--dry-run" in sys.argv):
        print(item)
