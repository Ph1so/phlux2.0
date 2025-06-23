"""Utility helpers for Selenium WebDriver creation."""
from __future__ import annotations

from contextlib import contextmanager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

CHROME_DRIVER_PATH = ChromeDriverManager().install()


def get_driver(headless: bool = True, *, user_agent: str | None = None) -> webdriver.Chrome:
    """Return a configured Selenium Chrome ``webdriver`` instance."""
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    if user_agent:
        options.add_argument(f"user-agent={user_agent}")
    else:
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
        )
    return webdriver.Chrome(service=Service(CHROME_DRIVER_PATH), options=options)


@contextmanager
def driver_context(headless: bool = True):
    """Context manager yielding a configured Chrome driver."""
    driver = get_driver(headless=headless)
    try:
        yield driver
    finally:
        driver.quit()

