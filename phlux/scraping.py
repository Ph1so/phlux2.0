from __future__ import annotations

"""Core scraping routines and manager class."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List

from .config import load_config
from .models import Company, ScrapeResult
from .utils import get_driver
from .scrapers import CompanyScraper, JPMorganScraper

import csv
import json
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from tenacity import retry, wait_fixed, stop_after_attempt


@retry(wait=wait_fixed(5), stop=stop_after_attempt(5))
def get_jobs_headless(name: str, url: str, selector: str, config: Dict[str, Dict[str, str]]) -> List[str]:
    """Scrape job titles from ``url`` using ``selector``."""
    clickable = config.get("CLICKABLE", {})
    needs_filter = config.get("NEEDS_FILTER", {})

    driver = get_driver()
    try:
        driver.get(url)
        if need_click := clickable.get(name):
            try:
                if "selector" in need_click:
                    element = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, need_click["selector"]))
                    )
                elif "text" in need_click:
                    element = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, f"//*[contains(normalize-space(), '{need_click['text']}')]")
                        )
                    )
                else:
                    raise ValueError(f"Invalid click config for {name}")
                driver.execute_script("arguments[0].click();", element)
                time.sleep(2)
            except Exception as exc:
                print(f"❌ Failed clicking for {name}: {exc}")
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
        )
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        jobs = [el.text.strip() for el in elements if el.text.strip()]
        if job_filter := needs_filter.get(name):
            jobs = [j for j in jobs if job_filter.lower() in j.lower()]
        return jobs
    except TimeoutException:
        print(f"❌ {name} - Timeout")
        return []
    finally:
        driver.quit()


def load_company_data(csv_path: Path = Path("companies.csv")) -> List[Company]:
    """Load ``Company`` entries from ``companies.csv``."""
    companies = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            companies.append(Company(row["Name"].strip(), row["Link"].strip().strip('"\''), row["ClassName"].strip()))
    return companies


def process_jobs(data: Dict[str, Dict[str, List[str]]], result: ScrapeResult, new_jobs: Dict) -> None:
    """Update ``data`` with ``result`` and record any new jobs."""
    existing = data.setdefault("companies", {}).get(result.name, [])
    new_list = []
    for job in result.jobs:
        job = job.replace("\n", " - ")
        if job not in existing:
            new_list.append(job)
    data.setdefault("companies", {})[result.name] = existing + new_list
    if new_list:
        new_jobs.setdefault("companies", {})[result.name] = {"jobs": new_list, "link": result.link}


class ScrapeManager:
    """Orchestrates scraping of all companies."""

    def __init__(self, config_path: Path | str = load_config.__defaults__[0]):
        self.config = load_config(config_path)

    def scrape_companies(self, companies: List[Company]) -> Dict:
        data: Dict[str, Dict] = {"companies": {}}
        new_jobs: Dict = {"companies": {}}
        with ProcessPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(get_jobs_headless, c.name, c.link, c.selector, self.config): c
                for c in companies
            }
            for future in as_completed(futures):
                company = futures[future]
                jobs = future.result()
                process_jobs(data, ScrapeResult(company.name, jobs, company.link), new_jobs)
        # built-in scrapers
        custom: List[CompanyScraper] = [JPMorganScraper()]
        for scraper in custom:
            name, jobs, link = scraper.get_jobs()
            process_jobs(data, ScrapeResult(name, jobs, link), new_jobs)
        return {"data": data, "new_jobs": new_jobs}

