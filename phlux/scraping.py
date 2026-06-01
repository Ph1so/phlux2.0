"""Core scraping logic: action parser, headless scraper, job deduplication, and orchestration."""
from __future__ import annotations

import csv
import json
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pytz
import requests
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tenacity import retry, stop_after_attempt, wait_fixed

from .models import Company, ScrapeResult
from .utils import get_driver, is_internship

logger = logging.getLogger(__name__)


CSS = "CSS"
CLICK = "CLICK"
FILTER = "FILTER"
UNDETECTED = "UNDETECTED"
ACTION_TYPES = {CSS, CLICK, FILTER, UNDETECTED}


class Actions:
    """Parses and iterates over a ``->``-delimited action string.

    Each action has the form ``TYPE:selector[:flag]``, e.g.
    ``CSS:.job-title``, ``CLICK:#load-more:pointer``, or simply ``UNDETECTED``.
    """

    def __init__(self, actions: List[str]) -> None:
        self.actions = actions

    def __iter__(self):
        return iter(self.actions)

    def get_type(self, action: str) -> str:
        """Return the action type (the part before the first ``:``)."""
        return action[: action.index(":")].strip()

    def get_selector(self, action: str) -> str:
        """Return the CSS/XPath selector, stripping any trailing ``:pointer`` flag."""
        raw = action[action.index(":") + 1 :].strip()
        return raw.replace(":pointer", "").strip()

    def has_flag(self, action: str, flag: str) -> bool:
        """Return True if *flag* is appended to *action*."""
        return f":{flag}" in action


@retry(wait=wait_fixed(5), stop=stop_after_attempt(5))
def get_jobs_headless(
    name: str,
    urls: str,
    instructions: str,
    headless: bool = True,
    test: bool = False,
) -> List[str]:
    """Scrape job titles from one or more URLs using a sequence of actions.

    Actions are specified as a ``->``-delimited string.  Supported types:

    * ``CSS:<selector>`` – collect text from every matched element.
      Use ``parent >> child`` to extract text from a child element within
      each matched parent.
    * ``CLICK:<selector>[:pointer]`` – click an element (use ``:pointer``
      to dispatch low-level pointer events instead of ``click()``).
    * ``FILTER:<keyword>`` – keep only jobs whose title contains *keyword*.
    * ``UNDETECTED`` – use ``undetected_chromedriver`` for this session.

    Multiple URLs are also separated by ``->``.

    After scraping, job titles that look like internship or co-op postings
    are prefixed with ``⭐️``.

    Args:
        name: Company name (used for logging).
        urls: One or more career-page URLs separated by ``->``.
        instructions: Action string describing how to extract jobs.
        headless: Whether to run Chrome in headless mode.
        test: If True, sleep 60 s before quitting (useful for debugging).

    Returns:
        List of job title strings.
    """
    if instructions.startswith('"') and instructions.endswith('"'):
        instructions = instructions[1:-1]

    actions = Actions(instructions.split("->"))
    use_undetected = any(a.strip() == UNDETECTED for a in actions)
    driver = get_driver(headless=headless, use_undetected=use_undetected)
    jobs: List[str] = []

    try:
        for url in urls.split("->"):
            try:
                driver.get(url.strip())
                time.sleep(3)

                for action in actions:
                    action = action.strip()
                    if action == UNDETECTED:
                        continue

                    if ":" not in action:
                        logger.warning("Invalid action format: %s", action)
                        continue

                    action_type = actions.get_type(action)
                    selector = actions.get_selector(action)
                    use_pointer = actions.has_flag(action, "pointer")

                    if action_type not in ACTION_TYPES:
                        logger.warning("Unknown action type '%s' for %s", action_type, name)
                        continue

                    if action_type == CSS:
                        if ">>" in selector:
                            parent_sel, child_sel = map(str.strip, selector.split(">>", 1))
                            WebDriverWait(driver, 15).until(
                                EC.presence_of_all_elements_located((By.CSS_SELECTOR, parent_sel))
                            )
                            for parent in driver.find_elements(By.CSS_SELECTOR, parent_sel):
                                try:
                                    text = parent.find_element(By.CSS_SELECTOR, child_sel).text.strip()
                                    if text:
                                        jobs.append(text)
                                except Exception:
                                    continue
                        else:
                            WebDriverWait(driver, 15).until(
                                EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                            )
                            for el in driver.find_elements(By.CSS_SELECTOR, selector):
                                text = el.text.strip()
                                if text:
                                    jobs.append(text)

                    elif action_type == CLICK:
                        try:
                            if selector.startswith("'") and selector.endswith("'"):
                                element = WebDriverWait(driver, 15).until(
                                    EC.presence_of_element_located((By.XPATH, selector[1:-1]))
                                )
                            else:
                                element = WebDriverWait(driver, 15).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                                )
                            if use_pointer:
                                driver.execute_script(
                                    """
                                    const el = arguments[0];
                                    el.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true }));
                                    el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                                    el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                                    el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                                    """,
                                    element,
                                )
                            else:
                                driver.execute_script("arguments[0].click();", element)
                            time.sleep(2)
                        except Exception as exc:
                            logger.error("Failed clicking for %s: %s", name, exc)

                    elif action_type == FILTER:
                        jobs = [j for j in jobs if selector.lower() in j.lower()]

            except TimeoutException:
                logger.warning("Timeout for %s at %s", name, url)
                continue

    finally:
        if test:
            time.sleep(60)
        try:
            driver.quit()
        except Exception:
            pass

    if not jobs:
        logger.warning("No jobs found - %s", name)
    else:
        logger.info("Jobs found - %s", name)

    # Normalize titles and star internship/co-op postings.
    for i, title in enumerate(jobs):
        title = title.strip()
        if title.endswith("New"):
            title = title[:-3].strip()
        if is_internship(title):
            title = "⭐️ " + title
        jobs[i] = title

    return jobs


def load_company_data(csv_path: Path = Path("companies.csv")) -> List[Company]:
    """Parse ``companies.csv`` and return a list of :class:`Company` objects.

    Args:
        csv_path: Path to the CSV file (default: ``companies.csv``).

    Returns:
        List of Company objects with ``name``, ``link``, and ``selector`` fields.
    """
    companies = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            companies.append(
                Company(
                    row["Name"].strip(),
                    row["Link"].strip().strip("'\""),
                    row["ClassName"].strip(),
                )
            )
    return companies


def process_jobs(data: dict, result: ScrapeResult, new_jobs: Dict) -> None:
    """Merge scrape results into *data*, recording only titles not seen before.

    New postings are also recorded in *new_jobs* so callers can send alerts.

    Args:
        data: Mutable dict representing ``storage.json`` contents.
        result: Scrape results for a single company.
        new_jobs: Accumulator dict for newly discovered jobs.
    """
    existing = data.setdefault("companies", {}).get(result.name, [])
    existing_titles = {j["title"] if isinstance(j, dict) else j for j in existing}

    eastern = pytz.timezone("US/Eastern")
    now = datetime.now(eastern)
    today = f"{now.month}/{now.day}"

    new_list = []
    for job in result.jobs:
        job = job.replace("\n", " - ")
        if job not in existing_titles:
            new_list.append({"title": job, "date": today})

    data["companies"][result.name] = existing + new_list

    if new_list:
        new_jobs.setdefault("companies", {})[result.name] = {
            "jobs": new_list,
            "link": result.link,
        }


def autoApply(jobs: List[str], url: str) -> None:
    """Trigger the ``auto-apply.yml`` GitHub Actions workflow for each job.

    Looks up the Susquehanna job sequence number from the careers page and
    dispatches one workflow run per job via the GitHub API.

    Args:
        jobs: List of job titles to apply to.
        url: Susquehanna careers page URL to search for job links.

    Raises:
        RuntimeError: If ``GH_TOKEN`` is not set in the environment.
    """
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN not set in environment")

    repo = "Ph1so/phlux2.0"
    workflow_id = "auto-apply.yml"
    driver = get_driver()

    try:
        driver.get(url)
        for job in jobs:
            logger.info("Auto Apply Job: %s", job)
            try:
                element = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located(
                        (
                            By.XPATH,
                            f"//a[.//div[contains(@class, 'job-title')]"
                            f"/span[normalize-space() = '{job}']]",
                        )
                    )
                )
                job_seqno = element.get_attribute("data-ph-at-job-seqno-text")
            except NoSuchElementException:
                logger.warning("Element for job '%s' not found on page.", job)
                continue

            if not job_seqno:
                logger.warning("No job_seqno found for job '%s'. Skipping.", job)
                continue

            apply_url = f"https://careers.sig.com/apply?jobSeqNo={job_seqno}"
            try:
                response = requests.post(
                    f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_id}/dispatches",
                    headers={
                        "Accept": "application/vnd.github+json",
                        "Authorization": f"Bearer {token}",
                    },
                    json={"ref": "main", "inputs": {"url": apply_url}},
                    timeout=10,
                )
                if response.status_code == 204:
                    logger.info("Successfully triggered workflow for: %s", job)
                else:
                    logger.error(
                        "Failed to trigger workflow for: %s | Status: %s | %s",
                        job, response.status_code, response.text,
                    )
            except requests.RequestException as e:
                logger.error("HTTP error while applying to job '%s': %s", job, e)

    except WebDriverException as e:
        logger.error("WebDriver error: %s", e)
    finally:
        try:
            driver.quit()
        except Exception:
            pass


class ScrapeManager:
    """Orchestrates parallel scraping of all companies and merges results.

    Args:
        config_path: Path to ``config.json`` (defaults to the repo root).
    """

    def __init__(self, config_path: Path | str = Path("config.json")) -> None:
        from .config import load_config
        self.config = load_config(config_path)

    def scrape_companies(
        self,
        companies: List[Company],
        storage_path: str = "storage.json",
        max_workers: int = os.cpu_count() or 4,
    ) -> Dict:
        """Scrape all companies in parallel and return updated job data.

        Args:
            companies: List of companies to scrape.
            storage_path: Path to the persistent job-storage JSON file.
            max_workers: Maximum number of parallel worker processes.

        Returns:
            A dict with keys ``"data"`` (full storage contents) and
            ``"new_jobs"`` (only jobs discovered this run).
        """
        data: Dict = {"companies": {}}
        if os.path.exists(storage_path):
            try:
                with open(storage_path, "r") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                logger.warning("%s is corrupted — starting fresh.", storage_path)
        else:
            logger.warning("%s not found — starting fresh.", storage_path)

        new_jobs: Dict = {"companies": {}}
        no_jobs_count = 0

        logger.info("Scraping %d companies with max_workers=%d", len(companies), max_workers)

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(get_jobs_headless, c.name, c.link, c.selector): c
                for c in companies
            }
            for future in as_completed(futures):
                company = futures[future]
                try:
                    jobs = future.result()
                except Exception as e:
                    logger.error("Error scraping %s: %s", company.name, e)
                    jobs = []
                if not jobs:
                    no_jobs_count += 1
                process_jobs(data, ScrapeResult(company.name, jobs, company.link), new_jobs)

        logger.info("Companies with no jobs found: %d", no_jobs_count)
        return {"data": data, "new_jobs": new_jobs}
