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
import os

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from tenacity import retry, wait_fixed, stop_after_attempt

CSS = "CSS"
CLICK = "CLICK"
FILTER = "FILTER"
ACTION_TYPES = [CSS, CLICK, FILTER]


@retry(wait=wait_fixed(5), stop=stop_after_attempt(5))
def get_jobs_headless(name: str, url: str, instructions: str, config: Dict[str, Dict[str, str]]) -> List[str]:
    """Scrape job titles from ``url`` using a sequence of instructions."""
    driver = get_driver()
    actions = Actions(instructions.split("->"))
    jobs = []
    try:
        driver.get(url)
        for action in actions:
            if ":" not in action:
                print(f"⚠️ Invalid action format: {action}")
                continue

            action_type = actions.get_type(action)
            selector = actions.get_selector(action)

            if action_type not in ACTION_TYPES:
                print(f"⚠️ Unknown action type '{action_type}' for {name}")
                continue

            if action_type == CSS:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                )
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                jobs += [el.text.strip() for el in elements if el.text.strip()]

            elif action_type == CLICK:
                try:
                    if selector[0] == "'" and selector[-1] == "'":
                        xpath_text = selector[1:-1]
                        element = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, f"//*[contains(normalize-space(), '{xpath_text}')]"))
                        )
                    else:
                        element = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                    driver.execute_script("arguments[0].click();", element)
                    time.sleep(2)
                except Exception as exc:
                    print(f"❌ Failed clicking for {name}: {exc}")

            elif action_type == FILTER:
                jobs = [j for j in jobs if selector.lower() in j.lower()]

    except TimeoutException:
        print(f"❌ {name} - Timeout")
        return []
    finally:
        driver.quit()

    return jobs


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

    def scrape_companies(self, companies: List[Company], storage_path="storage.json", max_workers=os.cpu_count()) -> Dict:
        data = {"companies": {}}
        total_companies_with_no_jobs = 0
        if os.path.exists(storage_path):
            with open(storage_path, "r") as f:
                data = json.load(f)
        else:
            print(f"`{storage_path}` not found")

        new_jobs: Dict = {"companies": {}}
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(get_jobs_headless, c.name, c.link, c.selector, self.config): c
                for c in companies
            }
            print(f"max_workers: {max_workers}")
            for future in as_completed(futures):
                company = futures[future]
                jobs = future.result()
                if jobs == []:
                    total_companies_with_no_jobs += 1
                process_jobs(data, ScrapeResult(company.name, jobs, company.link), new_jobs)

        # built-in scrapers
        custom: List[CompanyScraper] = [JPMorganScraper()]
        for scraper in custom:
            name, jobs, link = scraper.get_jobs()
            process_jobs(data, ScrapeResult(name, jobs, link), new_jobs)
            
        print(f"Total companies with no jobs: {total_companies_with_no_jobs}")
        return {"data": data, "new_jobs": new_jobs}

class Actions:
    def __init__(self, actions: List[str]):
        """
        Example actions:
            ["CLICK:div.accordion.EARLYTALENT p", "CSS:div.panel.EARLYTALENT p.job a"]
        """
        self.actions = actions

    def __iter__(self):
        return iter(self.actions)

    def get_type(self, action: str) -> str:
        return action[:action.index(":")].strip()

    def get_selector(self, action: str) -> str:
        return action[action.index(":") + 1:].strip()
