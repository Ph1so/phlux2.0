"""Read ADP career sites: Workforce Now career centers and MyJobs sites.

A row's Link is the page a person opens; its host picks the flavour.

**Workforce Now** (``https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid=<cid>&ccId=19000101_000001&lang=en_US``).
The page lists its open jobs from public JSON at
``…/mascsr/default/careercenter/public/events/staffing/v1/job-requisitions``,
sent the Link's ``cid``, ``ccId`` and ``lang`` and paged with ``$skip``; the
server returns at most 20 jobs a request, whatever ``$top`` asks for, and
gives the total in ``meta.totalNumber`` (the first page sometimes holds one
fewer than 20, so pages are walked until the total or an empty page). Each
job has an ``itemID`` and the id people see, ``customFieldGroup.stringFields``
``ExternalJobID``, the key here. A job's page is the career center page with
``&jobId=<ExternalJobID>``, the link the site's Share button builds.

**MyJobs** (``https://myjobs.adp.com/<site>/cx/job-listing``). The page is a
shell; ``https://myjobs.adp.com/public/staffing/v1/career-site/<site>`` gives
the site's settings, its API host (``properties.myadpUrl``) and a public
``myJobsToken``. The job list is then
``<myadpUrl>/myadp_prefix/mycareer/public/staffing/v1/job-requisitions``
(``…/apply-custom-filters`` on sites with ``customJobFilters``, as the page
does), sent the token as a ``myJobsToken`` header and ``$select``/``$top``/
``$skip``. Three quirks: the server answers an empty list unless
``Accept-Language`` is one plain locale ("en-US"); it leaves out
``publishedJobTitle`` unless ``postingDate`` is selected too; and its order
isn't stable between requests, so pages of one search overlap and miss jobs.
This module asks for everything in one request (``$top`` up to 1000; the
response ``count`` says how many there are). Each job's ``reqId`` is its key; its title is
``publishedJobTitle`` (``jobTitle`` is a job code like "050202-Engineer"), and
its page is ``https://myjobs.adp.com/<site>/cx/job-details?reqId=<reqId>``.

Both give ``requisitionLocations`` with an ``address`` (``cityName``,
``countrySubdivisionLevel1.codeValue``, MyJobs also ``country.codeValue``
"USA"/"CAN"), written "Houston, TX" or "Mississauga, Canada"; a job in
several places is "Houston, TX +2".
"""
from __future__ import annotations

import logging
from typing import Dict, List
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

from ..models import Posting
from .base import adapter, first, format_place, get, paged, path_slug, place, query, tidy_place, title_id

logger = logging.getLogger(__name__)

NAME = "adp"

# ── Workforce Now ─────────────────────────────────────────────────────────────

API_PATH = "/mascsr/default/careercenter/public/events/staffing/v1/job-requisitions"
PAGE_PATH = "/mascsr/default/mdf/recruitment/recruitment.html"
# The most the server returns per request.
PAGE_SIZE = 20
# Seconds between pages.
DELAY = 0.5


def _string_field(job: dict, name: str) -> str:
    for field in (job.get("customFieldGroup") or {}).get("stringFields") or []:
        if (field.get("nameCode") or {}).get("codeValue") == name:
            return str(field.get("stringValue") or "").strip()
    return ""


def job_id(job: dict) -> str:
    """Return a Workforce Now job's public id (its ``ExternalJobID``), else its ``itemID``."""
    return _string_field(job, "ExternalJobID") or str(job.get("itemID") or "")


def job_url(url: str, external_id: str) -> str:
    """Return the page of job *external_id* on the Workforce Now career center at *url*."""
    parts = urlsplit(url)
    params = query(url)
    fields = [("cid", first(params, "cid")), ("ccId", first(params, "ccId")), ("jobId", external_id),
              ("lang", first(params, "lang", "en_US"))]
    return urlunsplit((parts.scheme or "https", parts.netloc, PAGE_PATH,
                       urlencode([(k, v) for k, v in fields if v]), ""))


def _place(where: dict) -> str:
    """Return one ``requisitionLocations`` entry as "City, ST" (or the site's wording)."""
    address = where.get("address") or {}
    short = " ".join(str((where.get("nameCode") or {}).get("shortName") or "").split())
    city = str(address.get("cityName") or "").strip()
    region = str((address.get("countrySubdivisionLevel1") or {}).get("codeValue") or "").strip()
    country = (str((address.get("country") or {}).get("codeValue") or address.get("countryCode") or "").strip()
               or (short.rsplit(",", 1)[-1].strip() if "," in short else ""))
    if city or region:
        return format_place(city, region, country)
    return tidy_place(short)


def location(job: dict) -> str:
    """Return a job's location, plus a count of any more places."""
    return place(None, [_place(w) for w in job.get("requisitionLocations") or []
                        if w.get("postingIndicator") is not False])


def parse_jobs(url: str, jobs: List[dict]) -> List[Posting]:
    """Return Workforce Now *jobs* as postings, linked to the career center at *url*."""
    postings = []
    for job in jobs:
        title = " ".join(str(job.get("requisitionTitle") or "").split())
        if not title:
            continue
        key = job_id(job)
        external = _string_field(job, "ExternalJobID")
        postings.append(Posting(f"{NAME}:{key}" if key else title_id(NAME, title), title, location(job),
                                job_url(url, external) if external else ""))
    return postings


def api_params(url: str, skip: int) -> Dict[str, str]:
    params = query(url)
    cid = first(params, "cid")
    if not cid:
        raise ValueError(f"No cid in ADP Workforce Now URL {url}")
    lang = first(params, "lang", "en_US")
    out = {"cid": cid, "lang": lang, "locale": lang, "$top": str(PAGE_SIZE), "$skip": str(skip)}
    if first(params, "ccId"):
        out["ccId"] = first(params, "ccId")
    return out


def workforce_now(url: str) -> List[Posting]:
    """Return every job on the Workforce Now career center at *url*."""
    api = f"https://{urlsplit(url).netloc}{API_PATH}"
    total: List[int] = []

    def page(number: int) -> List[Posting]:
        skip = number * PAGE_SIZE
        if total and skip >= total[0]:
            return []
        data = get(api, params=api_params(url, skip), headers={"Accept": "application/json"}).json()
        count = (data.get("meta") or {}).get("totalNumber")
        if isinstance(count, int) and not total:
            total.append(count)
        return parse_jobs(url, data.get("jobRequisitions") or [])

    postings = paged(page, delay=DELAY)
    if total and len(postings) < total[0] - 1:
        logger.warning("%s lists %d jobs; read %d", url, total[0], len(postings))
    return postings


# ── MyJobs ────────────────────────────────────────────────────────────────────

MYJOBS_HOST = "https://myjobs.adp.com"
MYJOBS_SITE = MYJOBS_HOST + "/public/staffing/v1/career-site/{site}"
MYJOBS_SEARCH = "/myadp_prefix/mycareer/public/staffing/v1/job-requisitions"
MYJOBS_DEFAULT_API = "https://my.adp.com"
# The server leaves out publishedJobTitle unless postingDate is selected too.
MYJOBS_FIELDS = "reqId,jobTitle,publishedJobTitle,postingDate,requisitionLocations"
# Jobs per request: all of them, since the server's order isn't stable between requests.
MYJOBS_PAGE_SIZE = 1000
MYJOBS_MAX_PAGES = 5
# The server returns nothing for a weighted list like "en-US,en;q=0.9".
MYJOBS_LANGUAGE = "en-US"


def myjobs_job_url(site: str, req_id: str) -> str:
    return f"{MYJOBS_HOST}/{quote(site)}/cx/job-details?reqId={quote(req_id)}"


def parse_myjobs(site: str, jobs: List[dict]) -> List[Posting]:
    """Return MyJobs *jobs* (a search's ``jobRequisitions``) as postings."""
    postings = []
    for job in jobs:
        title = " ".join(str(job.get("publishedJobTitle") or job.get("jobTitle") or "").split())
        req_id = str(job.get("reqId") or "").strip()
        if not title:
            continue
        postings.append(Posting(f"{NAME}:{req_id}" if req_id else title_id(NAME, title), title, location(job),
                                myjobs_job_url(site, req_id) if req_id else ""))
    return postings


def myjobs(url: str) -> List[Posting]:
    """Return every job on the MyJobs career site at *url* (``myjobs.adp.com/<site>/cx/…``)."""
    site = path_slug(url)
    config = get(MYJOBS_SITE.format(site=quote(site)), headers={"Accept": "application/json"}).json()
    token = config.get("myJobsToken")
    if not token:
        raise ValueError(f"No myJobsToken for ADP MyJobs site {site!r}")
    api = ((config.get("properties") or {}).get("myadpUrl") or MYJOBS_DEFAULT_API).rstrip("/")
    features = (config.get("settings") or {}).get("enabledFeatures") or {}
    search = api + MYJOBS_SEARCH + ("/apply-custom-filters" if features.get("customJobFilters") else "")
    headers = {"Accept": "application/json", "Accept-Language": MYJOBS_LANGUAGE, "myJobsToken": token}
    postings: List[Posting] = []
    seen: set = set()
    count = None
    for _ in range(MYJOBS_MAX_PAGES):
        data = get(search, headers=headers, params={
            "$select": MYJOBS_FIELDS, "$top": str(MYJOBS_PAGE_SIZE), "$skip": str(len(postings)),
        }).json()
        jobs = data.get("jobRequisitions") or []
        count = data.get("count") if isinstance(data.get("count"), int) else count
        fresh = [p for p in parse_myjobs(site, jobs) if p.id not in seen]
        seen.update(p.id for p in fresh)
        postings.extend(fresh)
        if not fresh or count is None or len(postings) >= count:
            break
    if count and len(postings) < count:
        logger.warning("%s lists %d jobs; read %d", url, count, len(postings))
    return postings


@adapter(NAME)
def fetch(url: str, arg: str = "") -> List[Posting]:
    """Return every job on the ADP career site at *url* (Workforce Now or MyJobs)."""
    host = urlsplit(url).netloc.lower()
    if host == "myjobs.adp.com":
        return myjobs(url)
    return workforce_now(url)
