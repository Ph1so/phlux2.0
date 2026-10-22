"""Shared utilities: WebDriver factory, icon fetching, and job-title helpers."""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType, OperationSystemManager

from phlux.models import Company

logger = logging.getLogger(__name__)

_ICONS_PATH = Path(__file__).resolve().parent.parent / "icons.json"
_CHROME_DRIVER_PATH: str | None = None


def _get_chrome_driver_path() -> str:
    global _CHROME_DRIVER_PATH
    if _CHROME_DRIVER_PATH is None:
        _CHROME_DRIVER_PATH = ChromeDriverManager().install()
    return _CHROME_DRIVER_PATH


def _chrome_major_version() -> int | None:
    """Return the installed Chrome's major version, or None if it can't be found."""
    try:
        version = OperationSystemManager().get_browser_version_from_os(ChromeType.GOOGLE)
        return int(version.split(".")[0])
    except Exception:
        return None


def _user_agent(chrome_major: int) -> str:
    """Return a regular (non-headless) Chrome user agent for this OS."""
    platform = {
        "darwin": "Macintosh; Intel Mac OS X 10_15_7",
        "win32": "Windows NT 10.0; Win64; x64",
    }.get(sys.platform, "X11; Linux x86_64")
    return (
        f"Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{chrome_major}.0.0.0 Safari/537.36"
    )


# Matches internship / co-op postings. "intern" has no trailing word boundary so
# scraped titles with a glued-on badge ("InternNew") still match; instead it
# excludes the words that merely start with it (Internal, International, Internet).
# "student" catches student-worker roles (e.g. Zoox's "Contract Student Worker").
_INTERN_PATTERN = re.compile(
    r"\bintern(?!al|ation|et)|\bco[- ]?ops?\b|\bstudents?\b", re.IGNORECASE
)


def is_internship(title: str) -> bool:
    """Return True if *title* matches internship, co-op or student keywords."""
    return bool(_INTERN_PATTERN.search(title))


def board_link(link: str) -> str:
    """Return the careers page a person should open for a ``companies.csv`` link.

    Keeps only the first of several ``->``-separated URLs and drops the Greenhouse
    ``keyword`` search, so the link opens the whole job board rather than the
    narrowed results the scraper reads.
    """
    first = link.split("->")[0]
    parts = urlsplit(first)
    query = parse_qsl(parts.query, keep_blank_values=True)
    if not any(k == "keyword" for k, _ in query):
        return first
    kept = [(k, v) for k, v in query if k != "keyword"]
    return urlunsplit(parts._replace(query=urlencode(kept, safe="[]")))


def is_full_time(title: str) -> bool:
    """Return True if *title* does not match internship, co-op or student keywords."""
    return not is_internship(title)


def get_driver(headless: bool = True, use_undetected: bool = False):
    """Create and return a Selenium WebDriver instance.

    Args:
        headless: Run the browser without a visible window.
        use_undetected: Use ``undetected_chromedriver`` to bypass bot detection.

    Returns:
        A configured Chrome WebDriver.
    """
    chrome_args = [
        "--disable-gpu",
        "--window-size=1920x1080",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
    ]

    if use_undetected:
        # Bot walls (e.g. Akamai) block a user agent that disagrees with the real
        # browser version or says "HeadlessChrome", so advertise the installed one.
        # Pinning version_main also stops uc from fetching a driver newer than Chrome.
        major = _chrome_major_version()
        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        for arg in ("--window-size=1920,1080", "--no-sandbox", "--disable-dev-shm-usage"):
            options.add_argument(arg)
        if major:
            options.add_argument(f"--user-agent={_user_agent(major)}")
        return uc.Chrome(options=options, version_main=major)

    options = Options()
    if headless:
        options.add_argument("--headless")
    for arg in chrome_args:
        options.add_argument(arg)
    return webdriver.Chrome(service=Service(_get_chrome_driver_path()), options=options)


def update_icons(companies: List[Company]) -> None:
    """Fetch and cache brand logos for each company via the Brandfetch API.

    Existing entries in ``icons.json`` are preserved; only missing companies
    trigger a network request.

    Args:
        companies: List of Company objects whose names will be looked up.
    """
    icons_id = os.environ["ICONS_ID"]

    try:
        with open(_ICONS_PATH, "r", encoding="utf-8") as f:
            icons = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        icons = {}

    for company in companies:
        name = company.name
        if name in icons:
            continue
        try:
            response = requests.get(
                f"https://api.brandfetch.io/v2/search/{name}?c={icons_id}",
                timeout=10,
            )
            response.raise_for_status()
            domain = response.json()[0]["domain"]
            icons[name] = f"https://cdn.brandfetch.io/{domain}/w/400/h/400?c={icons_id}"
        except Exception as e:
            logger.warning("Failed to get icon for %s: %s", name, e)

    with open(_ICONS_PATH, "w", encoding="utf-8") as f:
        json.dump(icons, f, indent=2)
