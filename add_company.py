"""Interactive CLI tool for discovering CSS selectors and adding new companies."""
from __future__ import annotations

import csv
import logging
import time

from selenium.webdriver.common.by import By

from phlux.scraping import get_jobs_headless
from phlux.utils import get_driver

logging.getLogger().setLevel(logging.ERROR)


def get_tag_chain_selector(el) -> str | None:
    """Walk up the DOM from *el* to build a ``tag > tag > ...`` selector string.

    Stops as soon as an ancestor with a CSS class is found and uses
    ``tag.class`` as the final segment.

    Args:
        el: A Selenium WebElement to start from.

    Returns:
        A CSS selector string, or ``None`` if traversal fails.
    """
    path = []
    current = el
    try:
        while current.tag_name.lower() != "html":
            tag = current.tag_name
            class_attr = current.get_attribute("class")
            if class_attr:
                class_selector = "." + ".".join(class_attr.strip().split())
                path.insert(0, f"{tag}{class_selector}")
                break
            path.insert(0, tag)
            current = current.find_element(By.XPATH, "..")
    except Exception:
        return None
    return " > ".join(path)


def get_specific_css_selector(driver, job_title: str, name: str, link: str) -> str | None:
    """Attempt to auto-detect a CSS selector that matches *job_title* on the page.

    Tries up to four candidate selectors by walking up the DOM and using tag
    chains, then prompts the user to confirm each one.

    Args:
        driver: An active Selenium WebDriver pointed at the careers page.
        job_title: Exact text of a known job posting on the page.
        name: Company name (passed to the scraper for logging).
        link: Careers page URL (passed to the scraper).

    Returns:
        A confirmed CSS selector string, or ``None`` if none was accepted.
    """
    elements = driver.find_elements(By.XPATH, f"//*[normalize-space(text())='{job_title}']")
    if not elements:
        print("❌ No elements found with that exact text.")
        return None

    for el in elements:
        candidates = []

        # Strategy 1: walk up 4 ancestors and use the first one with a class.
        parent = el
        for _ in range(4):
            parent = parent.find_element(By.XPATH, "..")
            class_attr = parent.get_attribute("class")
            if class_attr:
                class_sel = "." + ".".join(class_attr.strip().split())
                candidates.append(f"{parent.tag_name}{class_sel}")

        # Strategy 2: full tag-chain path.
        chain = get_tag_chain_selector(el)
        if chain:
            candidates.append(chain)

        for selector in candidates:
            try:
                jobs = get_jobs_headless(name, link, f"CSS:{selector}")
                print(f"\n🔍 Candidate Selector: `{selector}`")
                print(f"⚙️  Total elements matched: {len(jobs)}")
                for job in jobs:
                    print(f"  • {job.strip().splitlines()[0] if job.strip() else 'EMPTY'}")
                if input("Use this selector? (y/n): ").strip().lower() == "y":
                    return selector
            except Exception as e:
                print(f"⚠️ Failed to use selector `{selector}`: {e}")

    print("⚠️ Could not find an acceptable selector automatically.")
    return None


def main() -> None:
    """Prompt the user for company details, detect a CSS selector, and save to CSV."""
    name = input("Company name: ").strip()
    link = input("Company careers page URL: ").strip()
    job_title = input("Example job title (exact match): ").strip()

    driver = get_driver(headless=False)
    driver.get(link)
    time.sleep(2)

    css_selector = get_specific_css_selector(driver, job_title, name, link)

    while not css_selector:
        css_selector = input("Enter a CSS selector manually: ").strip()
        jobs = get_jobs_headless(name, link, f"CSS:{css_selector}")
        print(f"\n🔍 Selector: `{css_selector}`")
        print(f"⚙️  Total elements matched: {len(jobs)}")
        for job in jobs:
            print(f"  • {job.strip().splitlines()[0] if job.strip() else 'EMPTY'}")
        if input("Use this selector? (y/n): ").strip().lower() != "y":
            css_selector = None

    driver.quit()

    with open("companies.csv", mode="a", newline="") as file:
        csv.writer(file).writerow([name, link, css_selector])

    print(f"✅ Saved: {name}, {link}, {css_selector}")


if __name__ == "__main__":
    main()
