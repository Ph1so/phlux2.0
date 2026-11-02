"""Work out whose a job board is, and turn account leads into boards.

When a company's site links no board, discovery guesses its slug on the public
Greenhouse, Lever and Ashby APIs. A guess finds *a* board, not necessarily the
company's: names collide (navier.com is a different company from Navier the
boat maker at navierboat.com; Greenhouse "preload" is a tank builder, not
Preload at preload.ai). So :func:`corroborate` sorts a guessed board into:

* :data:`CONFIRMED`: a job id the company's site links is on it, it names the
  company's domain, or it names the company's YC batch ("Spaceium (YC S24)");
* :data:`NAME_ONLY`: nothing contradicts it and its name matches, which is
  how same-name companies slip through, so it is reported for a person to check;
* :data:`REJECTED`: it names another company's site, or nothing ties it to this one.

Each board says who it is differently (:class:`Identity`):

* Greenhouse gives the board's name, each job's ``absolute_url`` (on the
  company's own site when it hosts its careers page) and job descriptions.
* Ashby's GraphQL API (the one its board pages use) gives the organization's
  name and public website.
* Lever gives neither; only the postings' text can mention the company.

Leads that name an account rather than a board are resolved here too: a
CareerPuck board names the Greenhouse/Lever/Ashby account it mirrors (whose
slug can differ: Welch's CareerPuck ``welchs`` is Greenhouse ``welchsinc``),
a Workable embed names a numeric account whose slug its job links reveal, and
a Dover apply link names a client whose careers page gives the board slug.
"""
from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, Optional, Set, Tuple
from urllib.parse import urljoin

import requests

from ..adapters.base import get, post
from .fingerprints import (
    CAREERPUCK,
    DOVER_CLIENT,
    JOB_SYSTEM_DOMAINS,
    WORKABLE_ACCOUNT,
    WORKABLE_JOB,
    Hit,
    board_link,
)
from .names import core_key, display_name, domain_label, names_match, registrable_domain, slug_guesses

logger = logging.getLogger(__name__)

TIMEOUT = 20
# Text searched for domains and names, per board.
MAX_TEXT = 500_000

GREENHOUSE_BOARD = "https://boards-api.greenhouse.io/v1/boards/{slug}"
GREENHOUSE_JOBS = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
LEVER_POSTINGS = "https://api.lever.co/v0/postings/{slug}"
ASHBY_JOBS = "https://api.ashbyhq.com/posting-api/job-board/{slug}"
ASHBY_GRAPHQL = "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiOrganizationFromHostedJobsPageName"
_ASHBY_ORG_QUERY = """
query ApiOrganizationFromHostedJobsPageName($organizationHostedJobsPageName: String!) {
  organization: organizationFromHostedJobsPageName(organizationHostedJobsPageName: $organizationHostedJobsPageName) {
    name publicWebsite
  }
}"""
CAREERPUCK_API = "https://api.careerpuck.com/v1/public/job-boards/{slug}"
WORKABLE_WIDGET = "https://apply.workable.com/api/v1/widget/accounts/{account}"
WORKABLE_ACCOUNT_API = "https://apply.workable.com/api/v1/accounts/{slug}"
WORKABLE_JOB_URL = "https://apply.workable.com/j/{shortcode}"
DOVER_CAREERS_PAGE = "https://app.dover.com/api/v1/careers-page/{client}"

_DOMAIN = re.compile(r"(?<![\w.-])((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,})(?![\w-])", re.IGNORECASE)
_WORKABLE_SLUG = re.compile(r"apply\.workable\.com/([A-Za-z0-9_-]+)/j/")


@dataclass
class Identity:
    """What a job board says about whose it is.

    ``sites`` are domains the board gives as the company's own website;
    ``mentions`` are domains anywhere in its text; ``job_ids`` its jobs' ids.
    """

    name: str = ""
    sites: Set[str] = field(default_factory=set)
    mentions: Set[str] = field(default_factory=set)
    text: str = ""
    job_ids: Set[str] = field(default_factory=set)


def domains_in(text: str) -> Set[str]:
    """Return the registrable domains written in *text* (URLs, emails, bare ``acme.com``)."""
    return {registrable_domain(m.group(1)) for m in _DOMAIN.finditer(text[:MAX_TEXT])}


def company_domain(url: str) -> Optional[str]:
    """Return *url*'s registrable domain unless it belongs to a job system."""
    domain = registrable_domain(url) if url else ""
    return domain if domain and domain not in JOB_SYSTEM_DOMAINS else None


def _json_or_none(url: str, **kwargs):
    """GET *url* as JSON, or None if it is not found (404/410)."""
    try:
        return get(url, timeout=TIMEOUT, **kwargs).json()
    except requests.HTTPError as error:
        if error.response is not None and error.response.status_code in (404, 410):
            return None
        raise


def greenhouse_identity(slug: str) -> Optional[Identity]:
    board = _json_or_none(GREENHOUSE_BOARD.format(slug=slug))
    if board is None:
        return None
    jobs = (_json_or_none(GREENHOUSE_JOBS.format(slug=slug)) or {}).get("jobs", [])
    sites = {d for d in (company_domain(j.get("absolute_url", "")) for j in jobs) if d}
    name = (board.get("name") or (jobs[0].get("company_name", "") if jobs else "")).strip()
    # Descriptions come HTML-escaped; they often name the company's site.
    text = html.unescape("\n".join([board.get("content") or ""] + [j.get("content") or "" for j in jobs]))[:MAX_TEXT]
    return Identity(name=name, sites=sites, mentions=domains_in(text), text=text,
                    job_ids={str(j["id"]) for j in jobs if "id" in j})


def lever_identity(slug: str) -> Optional[Identity]:
    jobs = _json_or_none(LEVER_POSTINGS.format(slug=slug), params={"mode": "json"})
    if jobs is None:
        return None
    text = "\n".join(
        str(j.get(key) or "") for j in jobs
        for key in ("descriptionPlain", "openingPlain", "descriptionBodyPlain", "additionalPlain")
    )[:MAX_TEXT]
    return Identity(mentions=domains_in(text), text=text, job_ids={str(j["id"]) for j in jobs if "id" in j})


def ashby_identity(slug: str) -> Optional[Identity]:
    # The public posting API says whether the board exists; the GraphQL API,
    # which rate-limits quickly, is only asked about boards that do.
    board = _json_or_none(ASHBY_JOBS.format(slug=slug))
    if board is None:
        return None
    response = post(ASHBY_GRAPHQL, timeout=TIMEOUT, json={
        "operationName": "ApiOrganizationFromHostedJobsPageName",
        "variables": {"organizationHostedJobsPageName": slug},
        "query": _ASHBY_ORG_QUERY,
    })
    org = (response.json().get("data") or {}).get("organization") or {}
    site = company_domain(org.get("publicWebsite") or "")
    jobs = board.get("jobs") or []
    text = "\n".join(str(j.get("descriptionPlain") or "") for j in jobs)[:MAX_TEXT]
    return Identity(name=(org.get("name") or "").strip(), sites={site} if site else set(),
                    mentions=domains_in(text), text=text, job_ids={str(j["id"]) for j in jobs if "id" in j})


IDENTIFY: Dict[str, Callable[[str], Optional[Identity]]] = {
    "greenhouse": greenhouse_identity,
    "lever": lever_identity,
    "ashby": ashby_identity,
}


CONFIRMED = "confirmed"
NAME_ONLY = "name only"
REJECTED = "rejected"
_SEASONS = {"winter": "W", "spring": "X", "summer": "S", "fall": "F"}


def batch_code(batch: str) -> str:
    """Return YC's short code for a batch: "Summer 2024" -> "S24" ("" if it isn't one)."""
    match = re.match(r"(winter|spring|summer|fall)\s+(?:20)?(\d\d)$", batch.strip(), re.IGNORECASE)
    return f"{_SEASONS[match.group(1).lower()]}{match.group(2)}" if match else ""


def corroborate(identity: Identity, name: str, domains: Iterable[str],
                job_ids: Iterable[str] = (), batch: str = "") -> Tuple[str, str]:
    """Return whether a guessed board is the company's (:data:`CONFIRMED`, :data:`NAME_ONLY`
    or :data:`REJECTED`), and why.

    Strongest first: a job id the company's site links is on the board; the
    board names the company's domain; the board names another company's site
    (rejected); it names the company's YC batch; its name matches (or, on
    Lever, its postings name the company).
    """
    domains = {d for d in domains if d}
    if set(job_ids) & identity.job_ids:
        return CONFIRMED, "a job linked from the company's site is on it"
    named = (identity.sites | identity.mentions) & domains
    if named:
        return CONFIRMED, f"it names {sorted(named)[0]}"
    others = identity.sites - domains
    if others:
        return REJECTED, f"it belongs to {sorted(others)[0]}"
    core = core_key(name)
    # A domain named like the company but not its own: a same-name company's board.
    rivals = {d for d in identity.mentions - domains if len(core) >= 4 and domain_label(d).startswith(core)}
    if rivals:
        return REJECTED, f"it names {sorted(rivals)[0]}, not {sorted(domains)[0] if domains else 'the company site'}"
    code = batch_code(batch)
    if code and re.search(r"\b(?:YC|Y Combinator)\W{0,3}" + code + r"\b", identity.text, re.IGNORECASE):
        return CONFIRMED, f"it says YC {code}"
    if identity.name:
        if names_match(identity.name, name):
            return NAME_ONLY, f"only its name, {identity.name!r}, matches"
        return REJECTED, f"it is {identity.name!r}"
    label = display_name(name)
    if identity.text and re.search(r"\b" + re.escape(label) + r"\b", identity.text, re.IGNORECASE):
        return NAME_ONLY, "only the company's name appears in its postings"
    return REJECTED, "nothing on it names the company"


def resolve_careerpuck(slug: str) -> Tuple[Optional[Hit], str]:
    """Return the Greenhouse/Lever/Ashby board a CareerPuck board mirrors, or why not."""
    data = _json_or_none(CAREERPUCK_API.format(slug=slug))
    if data is None:
        return None, f"CareerPuck board {slug!r} not found"
    jobs = data.get("jobs") or []
    platform = (data.get("atsSourcePlatform") or "").lower()
    tokens = [(j.get("jobBoard") or {}).get("atsSourceId") for j in jobs]
    token = next((t for t in tokens if t), "")
    if platform in IDENTIFY and token:
        return Hit(platform, token, board_link(platform, token)), ""
    if platform == "greenhouse":
        # No job names its board token: guess it, and check a job id is on the board.
        profile = data.get("employerProfile") or {}
        ids = {str(j["atsSourceId"]) for j in jobs if j.get("atsSourceId")}
        domains = [profile["emailDomain"]] if profile.get("emailDomain") else []
        guesses = slug_guesses(profile.get("name") or slug, domains) + [slug, f"{slug}inc"]
        for guess in dict.fromkeys(guesses):
            identity = greenhouse_identity(guess)
            if identity and ids & identity.job_ids:
                return Hit("greenhouse", guess, board_link("greenhouse", guess)), ""
        return None, f"CareerPuck board {slug!r} mirrors a Greenhouse board that could not be found"
    return None, f"CareerPuck board {slug!r} mirrors {platform or 'an unknown system'}, which phlux cannot read"


def resolve_workable_job(shortcode: str) -> Optional[Hit]:
    """Return the Workable board of a ``apply.workable.com/j/<shortcode>`` job link, or None."""
    response = get(WORKABLE_JOB_URL.format(shortcode=shortcode), timeout=TIMEOUT, allow_redirects=False)
    match = _WORKABLE_SLUG.search(urljoin("https://apply.workable.com/", response.headers.get("Location", "")))
    return Hit("workable", match.group(1), board_link("workable", match.group(1))) if match else None


def resolve_workable_account(account: str) -> Tuple[Optional[Hit], str]:
    """Return the Workable board of a ``whr_embed(<account id>)`` widget, or why not.

    A job's short link redirects to the board's slug; with no jobs open, slugs
    guessed from the account's name are checked against the account id.
    """
    widget = _json_or_none(WORKABLE_WIDGET.format(account=account))
    if widget is None:
        return None, f"Workable account {account} not found"
    for job in (widget.get("jobs") or [])[:3]:
        if job.get("shortcode"):
            hit = resolve_workable_job(job["shortcode"])
            if hit:
                return hit, ""
    for guess in slug_guesses(widget.get("name") or ""):
        details = _json_or_none(WORKABLE_ACCOUNT_API.format(slug=guess))
        if details and str(details.get("id")) == account:
            return Hit("workable", guess, board_link("workable", guess)), ""
    return None, f"Workable account {account} ({widget.get('name') or 'unnamed'}) has no findable board slug"


def resolve_dover_client(client: str) -> Tuple[Optional[Hit], str]:
    """Return the Dover board of a client id from a job's apply link, or why not."""
    page = _json_or_none(DOVER_CAREERS_PAGE.format(client=client))
    slug = (page or {}).get("slug")
    if not slug:
        return None, f"Dover client {client} has no careers page"
    return Hit("dover", slug, f"https://app.dover.com/jobs/{slug}"), ""


def resolve_lead(hit: Hit) -> Tuple[Optional[Hit], str]:
    """Return the board a lead stands for (or *hit* itself if it is a board), or why there is none."""
    try:
        if hit.board == CAREERPUCK:
            return resolve_careerpuck(hit.slug)
        if hit.board == WORKABLE_ACCOUNT:
            return resolve_workable_account(hit.slug)
        if hit.board == DOVER_CLIENT:
            return resolve_dover_client(hit.slug)
        if hit.board == WORKABLE_JOB:
            board = resolve_workable_job(hit.slug)
            return board, "" if board else f"Workable job {hit.slug} names no board"
    except (requests.RequestException, ValueError, KeyError) as error:
        return None, f"could not resolve {hit.board} {hit.slug!r} ({type(error).__name__})"
    return hit, ""
