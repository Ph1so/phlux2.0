"""Configuration loader for phlux."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

# Fallback email settings used when config.json omits an "EMAIL" key (or a field
# within it). The sender/login default to the account that has always been used;
# BCC lists default to empty so the email only goes to "to".
DEFAULT_EMAIL_CONFIG: Dict[str, Any] = {
    "from": "phiwe3296@gmail.com",
    "to": "phiwe3296@gmail.com",
    "login": "phiwe3296@gmail.com",
    "internship_bcc_enabled": True,
    "internship_bcc": [],
    "fulltime_enabled": True,
    "fulltime_bcc": [],
}


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Load JSON configuration from *path*."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_email_config(path: Path | str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Return email settings from the ``EMAIL`` section, filled with defaults.

    Missing fields fall back to :data:`DEFAULT_EMAIL_CONFIG`. ``internship_bcc``
    and ``fulltime_bcc`` may be given as a list of addresses or a single
    comma-separated string.
    """
    email = {**DEFAULT_EMAIL_CONFIG, **load_config(path).get("EMAIL", {})}
    for key in ("internship_bcc", "fulltime_bcc"):
        value = email[key]
        if isinstance(value, str):
            email[key] = [addr.strip() for addr in value.split(",") if addr.strip()]
    # When disabled, keep the saved addresses in config but don't BCC them, so the
    # internship email only reaches "to". Flip the flag back to re-enable them.
    if not email["internship_bcc_enabled"]:
        email["internship_bcc"] = []
    return email

