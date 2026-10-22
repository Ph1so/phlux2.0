"""Core scraping logic: action parser, headless scraper, job deduplication, and orchestration."""
from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pytz
import requests
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tenacity import RetryError, retry, stop_after_attempt, wait_fixed

from .boards import BOARDS, board_postings, keyword_in
from .lists import filter_companies, load_companies
from .models import Company, ScrapeResult
from .scrapers import API_SCRAPERS
from .utils import board_link, get_driver, is_internship

logger = logging.getLogger(__name__)


CSS = "CSS"
CLICK = "CLICK"
FILTER = "FILTER"
UNDETECTED = "UNDETECTED"
API = "API"
PAGINATE = "PAGINATE"
ACTION_TYPES = {CSS, CLICK, FILTER, UNDETECTED, API, PAGINATE}
# Safety cap so a broken "next" selector or an unfiltered board can't page forever.
MAX_PAGES = 10

# Job-board presets: an ``@name`` action expands to the board's standard action.
# Every company on the same ATS shares its markup, so one fix here covers them all.
# ScrapeManager reads @greenhouse, @lever and @ashby boards from their APIs
# instead (see board_of / phlux.boards); their page actions here only serve
# direct get_jobs_headless calls such as add_company.py.
PRESET_PREFIX = "@"
PRESETS = {
    "greenhouse": "CSS:tr.job-post p.body.body--medium",
    "ashby": "CSS:.ashby-job-posting-brief-title",
    "lever": "CSS:a.posting-title h5",
    "workday": "CSS:a[data-automation-id='jobTitle']->PAGINATE:button[data-uxi-element-id='next']",
}


def expand_presets(instructions: str) -> str:
    """Replace each ``@preset`` action in *instructions* with its full action.

    Presets chain like any other action, e.g. ``@ashby->FILTER:intern``.

    Raises:
        ValueError: If an ``@`` action names an unknown preset.
    """
    expanded = []
    for action in instructions.split("->"):
        token = action.strip()
        if token.startswith(PRESET_PREFIX):
            key = token[len(PRESET_PREFIX):].lower()
            if key not in PRESETS:
                raise ValueError(f"Unknown preset '{token}'; expected one of {sorted(PRESETS)}")
            action = PRESETS[key]
        expanded.append(action)
    return "->".join(expanded)


# Date stamp for titles found on a company's first look, when the open date is unknown.
NA_DATE = "N/A"
# Top-level storage key that turns on silent seeding (see ScrapeManager.scrape_companies).
SEED_FLAG = "seed_new_companies"


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


def _collect_css(driver, selector: str) -> List[str]:
    """Return the text of every element matching *selector* (``parent >> child`` allowed)."""
    texts: List[str] = []
    if ">>" in selector:
        parent_sel, child_sel = map(str.strip, selector.split(">>", 1))
        WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, parent_sel))
        )
        for parent in driver.find_elements(By.CSS_SELECTOR, parent_sel):
            try:
                text = parent.find_element(By.CSS_SELECTOR, child_sel).text.strip()
                if text:
                    texts.append(text)
            except Exception:
                continue
    else:
        WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
        )
        for el in driver.find_elements(By.CSS_SELECTOR, selector):
            text = el.text.strip()
            if text:
                texts.append(text)
    return texts


def _paginate(driver, next_selector: str, collect, max_pages: int = MAX_PAGES) -> List[str]:
    """Click *next_selector* page by page, returning ``collect()`` for every page after the first.

    Stops when the button is missing or disabled, when the click never changes the
    page, or after *max_pages* pages in total.
    """
    texts: List[str] = []
    current = collect()
    for _ in range(max_pages - 1):
        buttons = driver.find_elements(By.CSS_SELECTOR, next_selector)
        if not buttons:
            break
        button = buttons[0]
        if button.get_attribute("disabled") is not None or button.get_attribute("aria-disabled") == "true":
            break
        driver.execute_script("arguments[0].click();", button)
        page = _wait_for_new_page(collect, current)
        if not page:
            break
        texts.extend(page)
        current = page
    return texts


def _wait_for_new_page(collect, current: List[str], timeout: float = 15) -> List[str]:
    """Poll ``collect()`` until it differs from *current* and reads the same twice in a row.

    Requiring two matching reads skips the half-rendered list some boards show while
    swapping pages. Returns an empty list if no new page settles within *timeout* seconds.
    """
    last = None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(1)
        try:
            page = collect()
        except TimeoutException:
            page = []
        if page and page != current and page == last:
            return page
        last = page
    return []


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
    * ``PAGINATE:<selector>`` – click the "next page" button until it's gone or
      disabled (at most :data:`MAX_PAGES` pages), re-running the earlier ``CSS``
      actions on each new page.
    * ``UNDETECTED`` – use ``undetected_chromedriver`` for this session.
    * ``API:<name>[:<arg>]`` – collect titles with a site-specific extractor
      from :data:`phlux.scrapers.API_SCRAPERS`, e.g. ``API:tesla:Tesla SI``.
    * ``@<preset>`` – a job board's standard action, e.g. ``@workday``
      (see :data:`PRESETS`). :func:`scrape_company` sends ``@greenhouse``,
      ``@lever`` and ``@ashby`` to their APIs rather than here.

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
    instructions = expand_presets(instructions)

    actions = Actions(instructions.split("->"))
    use_undetected = any(a.strip() == UNDETECTED for a in actions)
    driver = get_driver(headless=headless, use_undetected=use_undetected)
    jobs: List[str] = []

    try:
        for url in urls.split("->"):
            try:
                driver.get(url.strip())
                time.sleep(3)
                css_selectors: List[str] = []

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
                        css_selectors.append(selector)
                        jobs.extend(_collect_css(driver, selector))

                    elif action_type == PAGINATE:
                        jobs.extend(_paginate(
                            driver,
                            selector,
                            lambda: [t for sel in css_selectors for t in _collect_css(driver, sel)],
                        ))

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

                    elif action_type == API:
                        scraper_name, _, arg = selector.partition(":")
                        driver.set_script_timeout(60)
                        jobs.extend(API_SCRAPERS[scraper_name](driver, arg))

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

    return finish_titles(name, jobs)


def finish_titles(name: str, jobs: List[str], strip_badge: bool = True) -> List[str]:
    """Normalize scraped titles in place and star internship/co-op postings.

    Logs whether *name* had any jobs, and returns *jobs*.

    Args:
        name: Company name (used for logging).
        jobs: Titles to normalize.
        strip_badge: Drop a trailing "New" that some boards glue onto the title
            text. Only page scrapes need this; API titles are the real titles.
    """
    if not jobs:
        logger.warning("No jobs found - %s", name)
    else:
        logger.info("Jobs found - %s", name)

    for i, title in enumerate(jobs):
        title = title.strip()
        if strip_badge and title.endswith("New"):
            title = title[:-3].strip()
        if is_internship(title):
            title = "⭐️ " + title
        jobs[i] = title

    return jobs


def _board_token(instructions: str) -> Tuple[str | None, str]:
    """Split a leading ``@board[:arg]`` action into ``(board, arg)``; board is None if absent."""
    first = instructions.strip().strip('"').split("->")[0].strip()
    if not first.startswith(PRESET_PREFIX):
        return None, ""
    name, _, arg = first[len(PRESET_PREFIX):].partition(":")
    name = name.strip().lower()
    return (name, arg.strip()) if name in BOARDS else (None, "")


def board_of(instructions: str) -> str | None:
    """Return the board or adapter an action string reads without a browser, else None.

    Only a leading ``@name`` (or ``@name:arg``) naming one in
    :data:`phlux.boards.BOARDS` counts; any other preset still expands to
    page-scraping actions.
    """
    return _board_token(instructions)[0]


@retry(wait=wait_fixed(5), stop=stop_after_attempt(3))
def get_board_jobs(name: str, urls: str, instructions: str) -> Tuple[List[str], List[str]]:
    """Read a company's postings from its job board's API.

    *urls* are the company's board URLs, whose query parameters narrow the board
    (see :mod:`phlux.boards`). Of the actions after the ``@board`` preset only
    ``FILTER:<keyword>`` applies, matching like :func:`phlux.boards.keyword_in`
    (word starts, so "intern" skips "Internal"); page actions like ``CLICK`` have
    no meaning here.

    Returns:
        ``(titles, ids)``: titles normalized and starred like page scrapes, and
        each posting's ``board:id`` key in the same order.
    """
    board, arg = _board_token(instructions)
    postings = board_postings(board, urls, arg)
    # Boards keep stray double spaces that a browser would collapse.
    pairs = [(" ".join(p.title.split()), p.id) for p in postings]
    for action in instructions.strip().strip('"').split("->")[1:]:
        action = action.strip()
        if action.startswith(f"{FILTER}:"):
            keyword = action[len(FILTER) + 1:].strip()
            pairs = [(t, i) for t, i in pairs if keyword_in(t, keyword)]
        elif action and action != UNDETECTED:
            logger.warning("Ignoring %s for %s: it has no meaning for a board API", action, name)
    titles = finish_titles(name, [t for t, _ in pairs], strip_badge=False)
    return titles, [i for _, i in pairs]


def scrape_company(company: Company) -> ScrapeResult:
    """Scrape one company: by board API when its actions name one, else in a browser."""
    if board_of(company.selector):
        try:
            titles, ids = get_board_jobs(company.name, company.link, company.selector)
        except Exception as e:
            # A RetryError holds futures that can't be pickled back from a worker
            # process, which would hide the real error; send its message instead.
            cause = e.last_attempt.exception() if isinstance(e, RetryError) else e
            raise RuntimeError(f"{type(cause).__name__}: {cause}") from None
        return ScrapeResult(company.name, titles, company.link, ids)
    jobs = get_jobs_headless(company.name, company.link, company.selector)
    return ScrapeResult(company.name, jobs, company.link)


def load_company_data(
    csv_path: Path = Path("companies.csv"),
    names: Iterable[str] | None = None,
) -> List[Company]:
    """Parse ``companies.csv`` and return a list of :class:`Company` objects.

    Args:
        csv_path: Path to the CSV file (default: ``companies.csv``).
        names: Optional company names to keep; ``None`` keeps every row.
            See :func:`phlux.lists.filter_companies` for matching rules.

    Returns:
        List of Company objects with ``name``, ``link``, and ``selector`` fields.
    """
    companies = load_companies(csv_path)
    if names is None:
        return companies
    return filter_companies(companies, names)


def switching_to_ids(existing: List, result: ScrapeResult) -> bool:
    """Return True on a company's first scrape by board API.

    It has titles stored from page scrapes but none of them has an id yet. The
    API reads the whole board where the page showed only the first page or so,
    so its unseen titles are mostly old postings, not new ones.
    """
    return bool(result.ids) and bool(existing) and not any(
        isinstance(j, dict) and j.get("id") for j in existing
    )


def process_jobs(data: dict, result: ScrapeResult, new_jobs: Dict, seed: bool = False) -> None:
    """Merge scrape results into *data*, recording only postings not seen before.

    A posting is new when neither its title nor (for board APIs) its id is
    stored. An id keeps a posting from coming back as new after its title is
    edited; matching titles keep the existing one-row-per-title behaviour. A
    stored title that turns up with an id gets that id recorded.

    New postings are also recorded in *new_jobs* so callers can send alerts.

    Args:
        data: Mutable dict representing ``storage.json`` contents.
        result: Scrape results for a single company.
        new_jobs: Accumulator dict for newly discovered jobs.
        seed: Record the titles as backlog already on the careers page: dated
            ``"N/A"`` and left out of *new_jobs*, so no alert goes out for them.
            Also applied automatically on a company's first board-API scrape
            (see :func:`switching_to_ids`).
    """
    existing = data.setdefault("companies", {}).get(result.name, [])
    existing_titles = {j["title"] if isinstance(j, dict) else j for j in existing}
    existing_ids = {j["id"] for j in existing if isinstance(j, dict) and j.get("id")}
    # Where to record an id for a stored title (dict entries only; legacy strings can't hold one).
    by_title = {}
    for j in existing:
        if isinstance(j, dict):
            by_title.setdefault(j["title"], j)

    if switching_to_ids(existing, result):
        logger.info("First board-API scrape of %s: recording unseen titles silently", result.name)
        seed = True

    eastern = pytz.timezone("US/Eastern")
    now = datetime.now(eastern)
    stamp = NA_DATE if seed else now.date().isoformat()

    ids = result.ids or [None] * len(result.jobs)
    new_list = []
    for job, job_id in zip(result.jobs, ids):
        job = job.replace("\n", " - ")
        if job_id and job_id in existing_ids:
            continue
        if job in existing_titles:
            entry = by_title.get(job)
            if job_id and entry is not None and not entry.get("id"):
                entry["id"] = job_id
                existing_ids.add(job_id)
            continue
        record = {"title": job, "date": stamp}
        if job_id:
            record["id"] = job_id
        new_list.append(record)

    data["companies"][result.name] = existing + new_list

    if new_list and not seed:
        new_jobs.setdefault("companies", {})[result.name] = {
            "jobs": new_list,
            "link": board_link(result.link),
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
        # Set by archive_season.py on a fresh storage file: a company with nothing
        # stored yet has its first batch recorded silently instead of emailed.
        seed_empty = data.get(SEED_FLAG, False)

        logger.info("Scraping %d companies with max_workers=%d", len(companies), max_workers)

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(scrape_company, c): c for c in companies}
            for future in as_completed(futures):
                company = futures[future]
                try:
                    result = future.result()
                except Exception as e:
                    logger.error("Error scraping %s: %s", company.name, e)
                    result = ScrapeResult(company.name, [], company.link)
                if not result.jobs:
                    no_jobs_count += 1
                seed = seed_empty and not data.get("companies", {}).get(company.name)
                process_jobs(data, result, new_jobs, seed=seed)

        logger.info("Companies with no jobs found: %d", no_jobs_count)
        return {"data": data, "new_jobs": new_jobs}
