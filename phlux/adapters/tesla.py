"""Tesla careers: ``@tesla[:<department>|<department>…]``.

The search page loads every listing from ``/cua-api/apps/careers/state`` (see
:mod:`phlux.scrapers.tesla`). Akamai guards tesla.com: plain HTTP gets "Access
Denied", and the JSON endpoint answers anything but a browser with a
JavaScript challenge. So a headless Chrome loads the search page and fetches
the JSON from inside it. The row's URL gives the job type and country
(``type=intern&site=US``); the arg optionally names departments.

Akamai's verdict depends on the browser, the automation driving it and the
network it runs from, and it changes over time. Headless Chrome gives itself
away: across six GitHub runners, a headless browser got the JSON on 1 of 6,
while a headed one on a virtual display (``xvfb-run``) got it on 5 of 6, with
either undetected-chromedriver or nodriver. So when a display is available
(``DISPLAY`` set on Linux, as the workflow arranges) the browsers run headed;
elsewhere, e.g. a Mac, they stay headless rather than open windows. Each
scrape tries undetected-chromedriver, then nodriver, then undetected-
chromedriver again, a fresh browser each time, and gives up only when every
one is refused.
"""
from __future__ import annotations

import asyncio
import gc
import json
import logging
import os
import sys
import time
from typing import Callable, Dict, List, Tuple
from urllib.parse import parse_qs, urlparse

from ..models import Posting
from ..scrapers.tesla import _FETCH_JS, STATE_PATH, matching_listings
from ..utils import _chrome_major_version, _user_agent, get_driver
from .base import adapter

logger = logging.getLogger(__name__)

NAME = "tesla"
# Akamai's page script needs a moment before the JSON endpoint will answer.
PAGE_SETTLE_SECONDS = 3
FETCH_ATTEMPTS = 4
FETCH_RETRY_SECONDS = 3
DENIED_TITLE = "Access Denied"


def headed() -> bool:
    """Run browsers headed only on Linux with a display (the workflow's xvfb-run)."""
    return sys.platform.startswith("linux") and bool(os.environ.get("DISPLAY"))

_NODRIVER_FETCH = (
    f"fetch({STATE_PATH!r})"
    ".then(r => r.ok ? r.text() : 'HTTP ' + r.status).catch(e => 'ERR ' + e)"
)


class Refused(RuntimeError):
    """Akamai turned this browser away."""


def _is_state(raw) -> bool:
    return isinstance(raw, str) and raw.startswith("{")


def state_via_undetected(url: str) -> Dict:
    """Return the careers state, fetched in an undetected-chromedriver session."""
    driver = get_driver(headless=not headed(), use_undetected=True)
    try:
        driver.set_script_timeout(60)
        driver.get(url)
        time.sleep(PAGE_SETTLE_SECONDS)
        if DENIED_TITLE in driver.title:
            raise Refused("page denied")
        raw = None
        for _ in range(FETCH_ATTEMPTS):
            raw = driver.execute_async_script(_FETCH_JS, STATE_PATH)
            if _is_state(raw):
                return json.loads(raw)
            time.sleep(FETCH_RETRY_SECONDS)
        raise Refused(str(raw)[:60])
    finally:
        try:
            driver.quit()
        except Exception:
            pass


async def _nodriver_state(url: str) -> Dict:
    import nodriver

    major = _chrome_major_version()
    args = ["--window-size=1920,1080", "--lang=en-US"]
    if major:
        # Headless Chrome otherwise announces itself as "HeadlessChrome".
        args.append(f"--user-agent={_user_agent(major)}")
    # Chrome's sandbox can't start for an unprivileged user on Ubuntu runners.
    browser = await nodriver.start(
        headless=not headed(), sandbox=not sys.platform.startswith("linux"), browser_args=args
    )
    try:
        page = await browser.get(url)
        await asyncio.sleep(PAGE_SETTLE_SECONDS)
        if DENIED_TITLE in (await page.evaluate("document.title") or ""):
            raise Refused("page denied")
        raw = None
        for _ in range(FETCH_ATTEMPTS):
            raw = await page.evaluate(_NODRIVER_FETCH, await_promise=True)
            if _is_state(raw):
                return json.loads(raw)
            await asyncio.sleep(FETCH_RETRY_SECONDS)
        raise Refused(str(raw)[:60])
    finally:
        browser.stop()


def state_via_nodriver(url: str) -> Dict:
    """Return the careers state, fetched in a nodriver (CDP-only) Chrome."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_nodriver_state(url))
    finally:
        # Let Chrome's subprocess transport be collected while the loop is
        # open; closing first prints "Event loop is closed" tracebacks.
        gc.collect()
        loop.run_until_complete(asyncio.sleep(0.5))
        loop.close()


STRATEGIES: List[Tuple[str, Callable[[str], Dict]]] = [
    ("undetected-chromedriver", state_via_undetected),
    # nodriver sometimes fails to start Chrome at all on a runner, so the last
    # try goes back to undetected-chromedriver with a fresh browser.
    ("nodriver", state_via_nodriver),
    ("undetected-chromedriver", state_via_undetected),
]


def fetch_state(url: str) -> Dict:
    """Return the careers state from the first browser Akamai lets through.

    Raises:
        RuntimeError: Naming why each browser failed.
    """
    failures = []
    for name, strategy in STRATEGIES:
        try:
            return strategy(url)
        except Exception as e:
            failures.append(f"{name}: {type(e).__name__}: {str(e)[:80]}")
            logger.info("Tesla via %s failed: %s", name, failures[-1])
    raise RuntimeError("Tesla refused every browser (" + "; ".join(failures) + ")")


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the Tesla listings the search URL and *arg*'s departments select."""
    query = parse_qs(urlparse(url).query)
    job_type = query.get("type", ["intern"])[0]
    site = query.get("site", ["US"])[0]
    departments = [d.strip() for d in arg.split("|") if d.strip()]
    state = fetch_state(url)
    return [
        Posting(f"{NAME}:{listing['id']}", " ".join(listing["t"].split()))
        for listing in matching_listings(state, job_type, site, departments)
    ]
