"""Scrape Y Combinator job listings and persist them to storage_yc.json."""
from __future__ import annotations

import json
import time

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from phlux.utils import get_driver

YC_URL = "https://www.ycombinator.com/jobs/role/software-engineer"


def update_yc_jobs(storage_file: str = "storage_yc.json") -> None:
    """Scrape the YC jobs page and merge results into *storage_file*.

    Scrolls the page to trigger lazy-loading, then collects company name,
    job title, application link, and logo for each listing card. Existing
    entries are preserved; only new companies/titles are added.

    Args:
        storage_file: Path to the JSON file used to persist YC job data.
    """
    driver = get_driver(headless=True)
    driver.get(YC_URL)
    wait = WebDriverWait(driver, 15)

    try:
        with open(storage_file, "r") as f:
            storage = json.load(f)
    except FileNotFoundError:
        storage = {}

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".flex.flex-col.items-start.gap-y-1")))

    # Scroll to trigger lazy-loading.
    last_h = 0
    for _ in range(4):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.0)
        h = driver.execute_script("return document.body.scrollHeight")
        if h == last_h:
            break
        last_h = h

    cards = driver.find_elements(By.CSS_SELECTOR, ".flex.flex-col.items-start.gap-y-1")
    added, updated = 0, 0

    for card in cards:
        try:
            company = card.find_element(By.CSS_SELECTOR, "span.block").text.strip()
        except NoSuchElementException:
            continue

        try:
            title_el = card.find_element(By.CSS_SELECTOR, ".text-sm.font-semibold.leading-tight.text-linkColor")
            job_title = title_el.text.strip()
        except NoSuchElementException:
            job_title = ""

        # Prefer a direct anchor on the title; fall back to any anchor in the card.
        link = ""
        try:
            link = title_el.find_element(By.TAG_NAME, "a").get_attribute("href") or ""
        except Exception:
            try:
                link = card.find_element(By.CSS_SELECTOR, "a[href]").get_attribute("href") or ""
            except NoSuchElementException:
                pass

        # Logo lives in the parent list item, not the card itself.
        logo = ""
        try:
            row = card.find_element(By.XPATH, "./ancestor::li[1]")
            logo = row.find_element(By.CSS_SELECTOR, "img.rounded-full").get_attribute("src") or ""
        except NoSuchElementException:
            pass

        if company not in storage:
            storage[company] = {"logo": logo, "link": link, "job_title": []}
            added += 1
        else:
            if logo:
                storage[company]["logo"] = logo
            if link:
                storage[company]["link"] = link

        if job_title and job_title not in storage[company]["job_title"]:
            storage[company]["job_title"].append(job_title)
            updated += 1

    with open(storage_file, "w") as f:
        json.dump(storage, f, indent=4)

    print(f"✅ Parsed {len(cards)} cards | New companies: {added} | Titles added: {updated}")
    driver.quit()


if __name__ == "__main__":
    update_yc_jobs()
