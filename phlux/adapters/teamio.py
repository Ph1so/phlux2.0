"""Teamio / LMC career widgets embedded in a company's own careers page.

The page sets ``window.__LMC_CAREER_WIDGET__ = {"apiKey": ..., "widgetId": ...}``
and the widget reads its jobs from LMC's GraphQL API. Both values are public
and read from the page on every run, since the site may re-embed the widget
with new ones. A widget may group its jobs (``groups[].jobAds``) or not
(``jobAds``); both are read.

A job ad has no page of its own: the widget opens it in place, on the careers
page, routed by the query (``?r=detail&id=<ad id>``; its links also carry
paging and tracking parameters, left out here). That URL is the job's link,
unless the widget is set to route otherwise (``legacyRouting``, or a separate
detail page when ``onePage`` is off), where no link is given.

An ad's ``locations`` give its city, region and country in the widget's
language ("Bratislava-Ružinov", "Bratislavský", "Slovensko"). Ads in the US
often name only the country there and put the town in the title
("Technical Warehouse Operator [Austin, TX]"), which is then the location.
"""
from __future__ import annotations

import json
import re
from typing import List
from urllib.parse import urlencode, urlsplit, urlunsplit

from ..models import Posting
from .base import adapter, format_place, get, place, post, tidy_place, unique, us_state

WIDGET = re.compile(r"__LMC_CAREER_WIDGET__\s*=\s*")
API = "https://api.capybara.lmc.cz/api/graphql/widget"
PAGE_SIZE = 100
MAX_PAGES = 20
JOB_ADS_QUERY = """
query WidgetJobAds($widgetId: ID!, $page: Int!, $rps: Int!) {
  widget(id: $widgetId) {
    jobAdList(page: $page, filters: [], rps: $rps) {
      groupedJobAds {
        jobAds { id title locations { city region country } }
        groups { jobAds { id title locations { city region country } } }
      }
      paginator { currentPage lastPage }
    }
  }
}"""


# The United States as the widget names it (Czech, Slovak, English).
UNITED_STATES = {"spojené státy americké", "spojené štáty americké", "usa", "united states", "us"}
# "[Austin, TX]" ending a title.
TITLE_PLACE = re.compile(r"\[([^\[\]]+)\]\s*$")


def location(ad: dict) -> str:
    """Return an ad's first location and how many more, or the US town its title names."""
    names, cities, us = [], False, False
    for loc in ad.get("locations") or []:
        if not isinstance(loc, dict):
            continue
        country = " ".join(str(loc.get("country") or "").split())
        if country.casefold() in UNITED_STATES:
            country, us = "US", True
        cities = cities or bool(loc.get("city"))
        names.append(format_place(loc.get("city"), loc.get("region"), country))
    match = TITLE_PLACE.search(ad.get("title") or "")
    if match and not cities and (us or not names):
        town, _, state = tidy_place(match.group(1)).rpartition(", ")
        if town and us_state(state):
            return f"{town}, {us_state(state)}"
    return place(None, names)


def job_url(page_url: str, config: dict, ad_id: str) -> str:
    """Return the careers page at *page_url* opened on ad *ad_id*, as the widget links it."""
    if config.get("legacyRouting") or config.get("onePage") is False:
        return ""
    parts = urlsplit(page_url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", urlencode([("r", "detail"), ("id", ad_id)]), ""))


def widget_config(html: str) -> dict:
    """Return the ``__LMC_CAREER_WIDGET__`` settings embedded in a careers page."""
    match = WIDGET.search(html)
    if not match:
        raise ValueError("No __LMC_CAREER_WIDGET__ in careers page")
    config, _ = json.JSONDecoder().raw_decode(html, match.end())
    return config


@adapter("teamio")
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every posting in the Teamio widget on a careers page."""
    config = widget_config(get(url).text)
    headers = {"X-Api-Key": config["apiKey"]}
    postings: List[Posting] = []
    page = last = 1
    while page <= min(last, MAX_PAGES):
        data = post(API, headers=headers, json={
            "query": JOB_ADS_QUERY,
            "variables": {"widgetId": config["widgetId"], "page": page, "rps": PAGE_SIZE},
        }).json()
        if data.get("errors"):
            raise RuntimeError(f"Teamio widget error: {data['errors']}")
        ads = data["data"]["widget"]["jobAdList"]
        grouped = ads["groupedJobAds"]
        jobs = list(grouped.get("jobAds") or [])
        for group in grouped.get("groups") or []:
            jobs.extend(group.get("jobAds") or [])
        postings.extend(Posting(f"teamio:{j['id']}", j["title"], location(j), job_url(url, config, j["id"]))
                        for j in jobs)
        last = (ads.get("paginator") or {}).get("lastPage") or 1
        page += 1
    return unique(postings)
