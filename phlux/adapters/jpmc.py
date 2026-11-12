"""JPMorganChase student program pages (``jpmorganchase.com/careers/explore-opportunities/programs/…``).

A row's Link is a program page a person opens, e.g.
``https://www.jpmorganchase.com/careers/explore-opportunities/programs/quant-fin-programs``;
several programs are chained with ``->``. The page's "Apply now" list is not in
its HTML: the page names its program in ``<div class="cmp-careers-apply-now"
programId="…">``, and its script asks
``GET /services/json/v1/careers/gate/programs.<programId>.json``, which answers
``{"<programId>": [{"name", "region", "country", "locations", "start_date",
"end_date", "application_url", "level"}, …]}``, one entry per open posting (an
empty list while the program is closed). The script shows every entry, so this
module reads the same JSON and keeps them all.

A posting's key is the Oracle Cloud HCM requisition number that ends its
``application_url`` (``…/CandidateExperience/en/sites/CX/job/210773869``), and
that URL is its page. Its ``locations`` ("Chicago, IL, United States",
"Singapore") are written "Chicago, IL +7".
"""
from __future__ import annotations

import logging
import re
from typing import List
from urllib.parse import urljoin, urlsplit

from ..models import Posting
from .base import adapter, get, place, soup, tidy_place, title_id, unique

logger = logging.getLogger(__name__)

NAME = "jpmc"
GATE = "{origin}/services/json/v1/careers/gate/programs.{program}.json"
# The page's script only fetches a programId made of these.
PROGRAM_ID = re.compile(r"^[A-Za-z0-9]+$")
# The requisition number that ends an Oracle HCM job link.
JOB_NUMBER = re.compile(r"/job/(\d+)/?$")


def program_ids(html: str) -> List[str]:
    """Return the programIds a program page's "Apply now" lists ask for, in page order."""
    ids: List[str] = []
    # lxml lowercases attribute names.
    for node in soup(html).select("[programid]"):
        value = node.get("programid", "").strip()
        if PROGRAM_ID.match(value) and value not in ids:
            ids.append(value)
    return ids


def to_posting(entry: dict, origin: str) -> Posting | None:
    """Return a gate entry as a posting, or None if it has no name."""
    title = " ".join(str(entry.get("name") or "").split())
    if not title:
        return None
    url = urljoin(origin + "/", entry["application_url"].strip()) if entry.get("application_url") else ""
    number = JOB_NUMBER.search(urlsplit(url).path) if url else None
    key = f"{NAME}:{number.group(1)}" if number else (f"{NAME}:{url}" if url else title_id(NAME, title))
    names = [tidy_place(n) for n in entry.get("locations") or [] if isinstance(n, str)]
    return Posting(key, title, place(names[0] if names else "", names[1:]), url)


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the open postings a JPMorganChase program page lists under "Apply now".

    Raises:
        ValueError: If the page names no program (not a program page).
    """
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    ids = program_ids(get(url).text)
    if not ids:
        raise ValueError(f"No programId on {url}: not a JPMorganChase program page")
    postings: List[Posting] = []
    for program in ids:
        body = get(GATE.format(origin=origin, program=program), headers={"Accept": "application/json"}).json()
        entries = body.get(program) if isinstance(body, dict) else None
        if entries is None:
            raise ValueError(f"No program {program} in the answer for {url}")
        postings += [p for p in (to_posting(e, origin) for e in entries if isinstance(e, dict)) if p]
    return unique(postings)
