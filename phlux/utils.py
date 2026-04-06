"""Shared utilities: WebDriver factory, icon fetching, and job-title helpers."""
from __future__ import annotations

import json
import os
from typing import List

import requests
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from phlux.models import Company

CHROME_DRIVER_PATH = ChromeDriverManager().install()

# Keywords that identify internship / co-op postings.
_INTERN_KEYWORDS = ("intern", "ship", "co-op", "coop", "co op")


def is_internship(title: str) -> bool:
    """Return True if *title* matches internship or co-op keywords."""
    lower = title.lower()
    return any(kw in lower for kw in _INTERN_KEYWORDS)


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
        options = uc.ChromeOptions()
        options.headless = headless
        for arg in chrome_args:
            options.add_argument(arg)
        return uc.Chrome(options=options)

    options = Options()
    if headless:
        options.add_argument("--headless")
    for arg in chrome_args:
        options.add_argument(arg)
    return webdriver.Chrome(service=Service(CHROME_DRIVER_PATH), options=options)


def update_icons(companies: List[Company]) -> None:
    """Fetch and cache brand logos for each company via the Brandfetch API.

    Existing entries in ``icons.json`` are preserved; only missing companies
    trigger a network request.

    Args:
        companies: List of Company objects whose names will be looked up.
    """
    icons_id = os.environ["ICONS_ID"]

    try:
        with open("icons.json", "r", encoding="utf-8") as f:
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
            print(f"❌ Failed to get icon for {name}: {e}")

    with open("icons.json", "w", encoding="utf-8") as f:
        json.dump(icons, f, indent=2)
