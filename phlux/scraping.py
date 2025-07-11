import os
import csv
import json
import time
from pathlib import Path
from typing import Dict, List
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
import pytz

import requests
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tenacity import retry, wait_fixed, stop_after_attempt

from .config import load_config
from .models import Company, ScrapeResult
from .utils import get_driver
from .scrapers import CompanyScraper, JPMorganScraper


CSS = "CSS"
CLICK = "CLICK"
FILTER = "FILTER"
UNDETECTED = "UNDETECTED"
ACTION_TYPES = [CSS, CLICK, FILTER, UNDETECTED]

class Actions:
    def __init__(self, actions: List[str]):
        self.actions = actions

    def __iter__(self):
        return iter(self.actions)

    def get_type(self, action: str) -> str:
        return action[:action.index(":")].strip()

    def get_selector(self, action: str) -> str:
        raw = action[action.index(":") + 1:].strip()
        return raw.replace(":pointer", "").strip()

    def has_flag(self, action: str, flag: str) -> bool:
        return f":{flag}" in action

@retry(wait=wait_fixed(5), stop=stop_after_attempt(5))
def get_jobs_headless(name: str, urls: str, instructions: str, headless=True, test=False) -> List[str]:
    """Scrape job titles from `url` using a sequence of actions like CLICK, CSS, FILTER, UNDETECTED."""
    
    # Clean quote wrapping, e.g. "CSS:.job-title" -> CSS:.job-title
    if instructions.startswith('"') and instructions.endswith('"'):
        instructions = instructions[1:-1]

    actions = Actions(instructions.split("->"))
    use_undetected = any(a.strip() == UNDETECTED for a in actions)
    
    driver = get_driver(headless=headless, use_undetected=use_undetected)
    jobs = []

    try:
        for url in urls.split("->"):
            try:
                driver.get(url)
                time.sleep(3)

                for action in actions:
                    action = action.strip()
                    if action == UNDETECTED:
                        continue  # Already handled by flag

                    if ":" not in action:
                        print(f"\u26a0\ufe0f Invalid action format: {action}")
                        continue

                    action_type = actions.get_type(action)
                    selector = actions.get_selector(action)
                    use_pointer = actions.has_flag(action, "pointer")

                    if action_type not in ACTION_TYPES:
                        print(f"\u26a0\ufe0f Unknown action type '{action_type}' for {name}")
                        continue

                    elif action_type == CSS:
                        if ">>" in selector:
                            parent_selector, child_selector = map(str.strip, selector.split(">>", 1))

                            WebDriverWait(driver, 15).until(
                                EC.presence_of_all_elements_located((By.CSS_SELECTOR, parent_selector))
                            )
                            parents = driver.find_elements(By.CSS_SELECTOR, parent_selector)

                            for el in parents:
                                try:
                                    child = el.find_element(By.CSS_SELECTOR, child_selector)
                                    text = child.text.strip()
                                    if text:
                                        jobs.append(text)
                                except Exception:
                                    continue
                        else:
                            WebDriverWait(driver, 15).until(
                                EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                            )
                            elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            for el in elements:
                                text = el.text.strip()
                                if text:
                                    jobs.append(text)

                    elif action_type == CLICK:
                        try:
                            if selector.startswith("'") and selector.endswith("'"):
                                xpath_text = selector[1:-1]
                                element = WebDriverWait(driver, 15).until(
                                    EC.presence_of_element_located((By.XPATH, xpath_text))
                                )
                            else:
                                element = WebDriverWait(driver, 15).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                                )

                            if use_pointer:
                                driver.execute_script("""
                                    const el = arguments[0];
                                    el.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true }));
                                    el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                                    el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                                    el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                                """, element)
                            else:
                                driver.execute_script("arguments[0].click();", element)
                            time.sleep(2)
                        except Exception as exc:
                            print(f"\u274c Failed clicking for {name} - {exc}")

                    elif action_type == FILTER:
                        jobs = [j for j in jobs if selector.lower() in j.lower()]

            except TimeoutException:
                print(f"Timeout for {name} at {url}")
                continue

    finally:
        if test:
            time.sleep(60)
        try:
            driver.quit()
        except Exception:
            pass

    if not jobs:
        print(f"\u274c No jobs found - {name}")
    else:
        print(f"\u2705 Jobs found - {name}")

    return jobs

def load_company_data(csv_path: Path = Path("companies.csv")) -> List[Company]:
    companies = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            companies.append(Company(row["Name"].strip(), row["Link"].strip().strip('"\''), row["ClassName"].strip()))
    return companies


def process_jobs(data, result: ScrapeResult, new_jobs: Dict) -> None:
    existing = data.setdefault("companies", {}).get(result.name, [])
    new_list = []

    eastern_timezone = pytz.timezone('US/Eastern')
    today = datetime.now(eastern_timezone).strftime("%-m/%-d")

    # Make sure to only compare job titles for uniqueness
    existing_titles = {j["title"] if isinstance(j, dict) else j for j in existing}

    for job in result.jobs:
        job = job.replace("\n", " - ")
        if job not in existing_titles:
            new_entry = {
                "title": job,
                "date": today
            }
            new_list.append(new_entry)

    data["companies"][result.name] = existing + new_list

    if new_list:
        new_jobs.setdefault("companies", {})[result.name] = {
            "jobs": new_list,
            "link": result.link
        }

def autoApply(jobs: List[str], url: str):
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN not set in environment")

    repo = "Ph1so/phlux2.0"
    workflow_id = "auto-apply.yml"

    try:
        driver = get_driver()
        driver.get(url)

        for job in jobs:
            print(f"Auto Apply Job: {job}")

            try:
                element = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.XPATH,
                f"//a[.//div[contains(@class, 'job-title')]/span[normalize-space() = '{job}']]"))
                )
                job_seqno = element.get_attribute("data-ph-at-job-seqno-text")
            except NoSuchElementException:
                print(f"\u26a0\ufe0f Element for job '{job}' not found on page.")
                continue

            if not job_seqno:
                print(f"\u26a0\ufe0f No job_seqno found for job '{job}'. Skipping.")
                continue

            apply_url = f"https://careers.sig.com/apply?jobSeqNo={job_seqno}"
            try:
                response = requests.post(
                    f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_id}/dispatches",
                    headers={
                        "Accept": "application/vnd.github+json",
                        "Authorization": f"Bearer {token}",
                    },
                    json={
                        "ref": "main",
                        "inputs": {
                            "url": apply_url
                        }
                    },
                    timeout=10
                )
                if response.status_code == 204:
                    print(f"\u2705 Successfully triggered workflow for: {job}")
                else:
                    print(f"\u274c Failed to trigger workflow for: {job} | Status: {response.status_code} | Response: {response.text}")

            except requests.RequestException as e:
                print(f"\u274c HTTP error while applying to job '{job}': {e}")

    except WebDriverException as e:
        print(f"\u274c WebDriver error: {e}")

    finally:
        try:
            driver.quit()
        except Exception:
            pass

class ScrapeManager:
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

        print(f"Total companies with no jobs: {total_companies_with_no_jobs}")
        return {"data": data, "new_jobs": new_jobs}

