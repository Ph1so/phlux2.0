"""Any job list that is plain server-rendered HTML: ``@html:<css selector>``.

For a careers page that needs no browser (no ATS, no JSON behind it), the
row's selector names the job title elements, as a ``CSS:`` action would:
``@html:.publication-source h2 a``. Everything after ``@html:`` is the selector,
colons included.

Each posting's id is the absolute URL of the link the title is, or sits in.
For pages where the link sits beside the title rather than around it, the
selector can name the job's container too, Selenium-style:
``@html:.b-job-item >> .b-job-item__title`` takes the title from the first
``.b-job-item__title`` in each ``.b-job-item`` and, failing a link around the
title, the first link in that container. A title with no link at all is keyed
by its text (:func:`~phlux.adapters.base.title_id`).
"""
from __future__ import annotations

import logging
from typing import List, Optional
from urllib.parse import urljoin

from ..models import Posting
from .base import adapter, get, soup, text, title_id, unique

logger = logging.getLogger(__name__)

NAME = "html"
HEADERS = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
# Webflow collection lists stop at 100 items, silently.
WEBFLOW_CAP = 100


def _link(node) -> Optional[str]:
    """Return the href of *node* if it is a link, else of the link around it."""
    anchor = node if node.name == "a" else node.find_parent("a")
    return anchor.get("href") if anchor is not None and anchor.get("href") else None


def postings(html: str, base_url: str, selector: str) -> List[Posting]:
    """Return the postings whose titles *selector* matches in *html*."""
    container, _, title_selector = (part.strip() for part in selector.partition(">>"))
    page = soup(html)
    pairs = []
    if title_selector:
        for item in page.select(container):
            title = item.select_one(title_selector)
            if title is not None:
                inner = item.select_one("a[href]")
                pairs.append((title, _link(title) or (inner.get("href") if inner is not None else None)))
    else:
        pairs = [(title, _link(title)) for title in page.select(container)]

    found = []
    for node, href in pairs:
        title = text(node)
        if not title:
            continue
        key = f"{NAME}:{urljoin(base_url, href)}" if href else title_id(NAME, title)
        found.append(Posting(key, title))
    return unique(found)


@adapter("html")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return the postings on the page at *url* whose titles match the selector *arg*."""
    if not arg:
        raise ValueError("@html needs a CSS selector: @html:<selector>")
    response = get(url, headers=HEADERS)
    found = postings(response.text, response.url, arg)
    if not found:
        logger.warning("No elements match %r at %s", arg, url)
    elif len(found) == WEBFLOW_CAP and "data-wf-site" in response.text:
        logger.warning("Exactly %d jobs at %s: a Webflow list may be cutting off the rest", WEBFLOW_CAP, url)
    return found
