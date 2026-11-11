"""Core scraping logic: action parser, headless scraper, job deduplication, and orchestration."""
from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Collection, Dict, Iterable, List, Tuple

import pytz
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tenacity import RetryError, retry, stop_after_attempt, wait_fixed

from .boards import BOARDS, board_postings, keyword_in
from .early_career import early_career_lines
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
# Top-level storage keys kept by track_closures: each company's last trusted
# scrape date, and closures waiting for a second look.
CHECKED_KEY = "checked"
PENDING_KEY = "pending_closures"
# Top-level storage key kept by track_failures: companies whose scrape is
# failing, since when and with what error (see phlux.health).
FAILING_KEY = "failing"
# A drop of at least this many postings, and over this share of a company's open
# ones, is held until a scrape at least CONFIRM_AFTER later sees the same.
BIG_DROP_MIN = 5
BIG_DROP_SHARE = 0.5
CONFIRM_AFTER = timedelta(hours=1)
EASTERN = pytz.timezone("US/Eastern")


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
def get_board_jobs(name: str, urls: str, instructions: str
                   ) -> Tuple[List[str], List[str], List[str], List[str], List[str]]:
    """Read a company's postings from its job board's API.

    *urls* are the company's board URLs, whose query parameters narrow the board
    (see :mod:`phlux.boards`). Of the actions after the ``@board`` preset only
    ``FILTER:<keyword>[|<keyword>…]`` applies, keeping titles that contain any
    of the keywords, matched like :func:`phlux.boards.keyword_in` (word starts,
    so "intern" skips "Internal"); page actions like ``CLICK`` have no meaning
    here.

    Returns:
        ``(titles, ids, locations, urls, early)``: titles normalized and starred
        like page scrapes, and each posting's ``board:id`` key, location, own
        page and new-grad description line (:mod:`phlux.early_career`; "" for
        most, and always for internships) in the same order.
    """
    board, arg = _board_token(instructions)
    postings = board_postings(board, urls, arg)
    # The whole board, before any FILTER: its senior postings tell boilerplate apart.
    early = early_career_lines((p.id, p.title, p.description) for p in postings)
    # Boards keep stray double spaces that a browser would collapse.
    rows = [(" ".join(p.title.split()), p.id, p.location, p.url, early.get(p.id, "")) for p in postings]
    for action in instructions.strip().strip('"').split("->")[1:]:
        action = action.strip()
        if action.startswith(f"{FILTER}:"):
            keywords = [k.strip() for k in action[len(FILTER) + 1:].split("|") if k.strip()]
            rows = [row for row in rows if any(keyword_in(row[0], k) for k in keywords)]
        elif action and action != UNDETECTED:
            logger.warning("Ignoring %s for %s: it has no meaning for a board API", action, name)
    titles = finish_titles(name, [row[0] for row in rows], strip_badge=False)
    return (titles, [row[1] for row in rows], [row[2] for row in rows], [row[3] for row in rows],
            ["" if t.startswith("⭐️") else row[4] for t, row in zip(titles, rows)])


def scrape_company(company: Company) -> ScrapeResult:
    """Scrape one company: by board API when its actions name one, else in a browser.

    Raises:
        RuntimeError: Carrying the underlying error's type and message. A
            RetryError holds futures that can't be pickled back from a worker
            process, which would hide the real error behind a pickling one.
    """
    try:
        if board_of(company.selector):
            titles, ids, locations, urls, early = get_board_jobs(company.name, company.link, company.selector)
            return ScrapeResult(company.name, titles, company.link, ids, locations, urls, early)
        jobs = get_jobs_headless(company.name, company.link, company.selector)
        return ScrapeResult(company.name, jobs, company.link)
    except Exception as e:
        cause = e.last_attempt.exception() if isinstance(e, RetryError) else e
        raise RuntimeError(f"{type(cause).__name__}: {cause}") from None


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


def _fill_in(entry: dict | None, **fields: str) -> None:
    """Set each non-empty field *entry* doesn't have yet; never replace one."""
    if entry is None:
        return
    for key, value in fields.items():
        if value and not entry.get(key):
            entry[key] = value


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
    stored posting that turns up with an id, page link, location or new-grad
    description line (``early``) it lacks gets them recorded. Stored links and locations are never replaced: some
    sites put per-visit tracking in their links, and rewriting storage on every
    run would make every bot run commit (and every commit start another run).

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

    by_id = {j["id"]: j for j in existing if isinstance(j, dict) and j.get("id")}

    ids = result.ids or [None] * len(result.jobs)
    locations = result.locations or [""] * len(result.jobs)
    urls = result.urls or [""] * len(result.jobs)
    lines = result.early or [""] * len(result.jobs)
    new_list = []
    alerts = []
    for job, job_id, location, url, early in zip(result.jobs, ids, locations, urls, lines):
        job = job.replace("\n", " - ")
        if job_id and job_id in existing_ids:
            _fill_in(by_id.get(job_id), url=url, location=location, early=early)
            continue
        if job in existing_titles:
            entry = by_title.get(job)
            if job_id and entry is not None and not entry.get("id"):
                entry["id"] = job_id
                existing_ids.add(job_id)
                by_id[job_id] = entry
            _fill_in(entry, url=url, location=location, early=early)
            continue
        record = {"title": job, "date": stamp}
        if job_id:
            record["id"] = job_id
        _fill_in(record, url=url, location=location, early=early)
        new_list.append(record)
        alerts.append(record)

    data["companies"][result.name] = existing + new_list

    if new_list and not seed:
        new_jobs.setdefault("companies", {})[result.name] = {
            "jobs": alerts,
            "link": board_link(result.link),
        }


def track_failures(data: dict, name: str, error: str | None = None, now: datetime | None = None) -> None:
    """Record when a company's scrape starts failing, and forget it once it works again.

    Only the first failure is written (its date and error), so a company that
    fails every run changes storage once rather than on every run (each bot
    commit starts another run).

    Args:
        data: Mutable ``storage.json`` contents.
        name: The company scraped.
        error: The scrape's error, or None if it succeeded.
        now: Stand-in for the current time.
    """
    failing = data.setdefault(FAILING_KEY, {})
    if error is None:
        failing.pop(name, None)
    elif name not in failing:
        today = (now or datetime.now(EASTERN)).date().isoformat()
        failing[name] = {"since": today, "error": " ".join(error.split())[:200]}


def _posting_key(entry: dict) -> str:
    return entry.get("id") or f"title:{entry['title']}"


def track_closures(data: dict, result: ScrapeResult, trust_empty: bool = False,
                   now: datetime | None = None) -> None:
    """Record which of a company's stored postings closed, from a scrape that succeeded.

    A stored posting the scrape no longer shows gets ``closed`` (the date it was
    first missed); one that shows again loses it. The company's ``checked`` date
    (in :data:`CHECKED_KEY`) records the last scrape trusted this way. Postings
    already gone on a company's first such look closed at some unknown point
    before tracking began, so they are stamped ``"N/A"`` instead.

    Missing a posting is not proof it closed, so two guards stand between a
    flaky scrape and a wave of false closures:

    * An empty result closes nothing unless *trust_empty* (board APIs raise on
      failure, so their empty answer means an empty board; a page scrape that
      timed out also returns nothing).
    * A big drop (an empty result, or :data:`BIG_DROP_MIN`+ postings and over
      :data:`BIG_DROP_SHARE` of the open ones) waits in :data:`PENDING_KEY`. A
      scrape at least :data:`CONFIRM_AFTER` later closes those of them it still
      misses. The hold is never rewritten while it waits, so a scraper that
      returns a different partial list every run can't make every run write.

    Storage changes only when something closes, reopens or the day turns, so a
    quiet run still writes nothing (each bot commit starts another run).

    Args:
        data: Mutable ``storage.json`` contents, after :func:`process_jobs`.
        result: The company's scrape, which must not have failed.
        trust_empty: Whether an empty result means the company lists nothing.
        now: Stand-in for the current time.
    """
    now = now or datetime.now(EASTERN)
    today = now.date().isoformat()
    pending = data.setdefault(PENDING_KEY, {})
    if not result.jobs and not trust_empty:
        return
    checked = data.setdefault(CHECKED_KEY, {})
    stamp = NA_DATE if result.name not in checked else today
    checked[result.name] = today

    seen_ids = {i for i in result.ids if i}
    seen_titles = {job.replace("\n", " - ") for job in result.jobs}
    entries = [j for j in data.get("companies", {}).get(result.name, []) if isinstance(j, dict)]
    missing = []
    for entry in entries:
        if (entry.get("id") and entry["id"] in seen_ids) or entry["title"] in seen_titles:
            entry.pop("closed", None)
        elif "closed" not in entry:
            missing.append(entry)

    open_count = sum(1 for e in entries if "closed" not in e)
    big = bool(missing) and (
        not result.jobs or (len(missing) >= BIG_DROP_MIN and len(missing) > BIG_DROP_SHARE * open_count)
    )
    if big:
        held = pending.get(result.name)
        if not held:
            pending[result.name] = {
                "since": now.isoformat(timespec="minutes"),
                "keys": sorted(_posting_key(e) for e in missing),
                **({"backlog": True} if stamp == NA_DATE else {}),
            }
            logger.warning("%s: %d of %d postings missing; holding closures for a second look",
                           result.name, len(missing), open_count)
            return
        if now - datetime.fromisoformat(held["since"]) < CONFIRM_AFTER:
            return
        confirmed = set(held["keys"])
        missing = [e for e in missing if _posting_key(e) in confirmed]
        if held.get("backlog"):
            stamp = NA_DATE
    pending.pop(result.name, None)
    for entry in missing:
        entry["closed"] = stamp


def mark_checked(data: dict, result: ScrapeResult, trust_empty: bool = False,
                 now: datetime | None = None) -> None:
    """Record a trusted scrape's ``checked`` date without tracking closures.

    For companies scraped only for ``all_internships_bcc``. Many are page
    scrapes that show a different slice of a long board each run (Cisco,
    Adobe), so tracking closures would close and reopen postings every run:
    each run would commit, and every bot commit starts another run. Any
    closures held for a second look are dropped.
    """
    if not result.jobs and not trust_empty:
        return
    data.setdefault(CHECKED_KEY, {})[result.name] = (now or datetime.now(EASTERN)).date().isoformat()
    data.get(PENDING_KEY, {}).pop(result.name, None)


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
        unlisted: Collection[str] = (),
    ) -> Dict:
        """Scrape all companies in parallel and return updated job data.

        Args:
            companies: List of companies to scrape.
            storage_path: Path to the persistent job-storage JSON file.
            max_workers: Maximum number of parallel worker processes.
            unlisted: Companies scraped only for ``all_internships_bcc``.
                Their postings are recorded silently (like
                ``seed_new_companies``) until a scrape first gives them a
                ``checked`` date, so turning a company on alerts only what's
                posted after, not its whole board. Stored entries don't count:
                a company dropped from the list long ago has missed postings
                since, and they would all look new. Their closures aren't
                tracked (see :func:`mark_checked`).

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
                failed = False
                try:
                    result = future.result()
                    track_failures(data, company.name)
                except Exception as e:
                    logger.error("Error scraping %s: %s", company.name, e)
                    result = ScrapeResult(company.name, [], company.link)
                    failed = True
                    track_failures(data, company.name, str(e))
                if not result.jobs:
                    no_jobs_count += 1
                seed = (seed_empty and not data.get("companies", {}).get(company.name)) or (
                    company.name in unlisted and company.name not in data.get(CHECKED_KEY, {}))
                process_jobs(data, result, new_jobs, seed=seed)
                if failed:
                    continue
                trust_empty = bool(board_of(company.selector))
                if company.name in unlisted:
                    mark_checked(data, result, trust_empty=trust_empty)
                else:
                    track_closures(data, result, trust_empty=trust_empty)

        logger.info("Companies with no jobs found: %d", no_jobs_count)
        return {"data": data, "new_jobs": new_jobs}
