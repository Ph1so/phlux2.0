"""Recognize job boards in a page's HTML (or in a URL) and turn them into ``companies.csv`` links.

A careers page shows which job system it uses in the URLs it links, embeds or
scripts: ``jobs.ashbyhq.com/<slug>``, a Greenhouse embed ``?for=<slug>``, a
``<slug>.bamboohr.com`` iframe… Each :class:`Fingerprint` matches one such URL
shape and builds the Link that phlux's reader for that board expects (see the
docstring of each module in :mod:`phlux.adapters`).

The text is searched raw, scripts included, because many sites (Next.js,
Framer, Webflow) put the board URL only in their page data. Escaped forms
(``https:\\/\\/jobs.lever.co\\/acme``, ``%2F``) are unescaped first.

Some matches name an account rather than a board and need an API call to
resolve (:data:`CAREERPUCK`, :data:`WORKABLE_ACCOUNT`, :data:`WORKABLE_JOB`,
:data:`DOVER_CLIENT`; see :mod:`phlux.discovery.identify`). Job systems phlux cannot read are
reported by :func:`find_unsupported`, so the owner learns which adapter would
unlock which companies.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple

from .names import domain_label, host

# Leads that need an API call to become a board (see phlux.discovery.identify).
CAREERPUCK = "careerpuck"
WORKABLE_ACCOUNT = "workable-account"
WORKABLE_JOB = "workable-job"
DOVER_CLIENT = "dover-client"
LEADS = (CAREERPUCK, WORKABLE_ACCOUNT, WORKABLE_JOB, DOVER_CLIENT)


@dataclass(frozen=True)
class Hit:
    """A job board found in a page: phlux's board name, its account slug, and the Link to read."""

    board: str
    slug: str
    link: str


Builder = Callable[[re.Match], Optional[Tuple[str, str]]]


@dataclass(frozen=True)
class Fingerprint:
    """One URL shape of a job board; *build* turns a match into ``(slug, link)``, or None to skip it.

    *needle* is a lowercase string every match contains: pages without it are
    not searched, which keeps a 200 KB page from costing a regex scan per board.
    """

    board: str
    needle: str
    pattern: re.Pattern
    build: Builder


def _slug_link(template: str, reserved: Set[str] = frozenset(), group: int = 1) -> Builder:
    """Build ``(slug, template.format(slug=…))`` from a match, skipping *reserved* path words."""

    def build(match: re.Match) -> Optional[Tuple[str, str]]:
        slug = match.group(group).rstrip(".")
        if not slug or slug.lower() in reserved:
            return None
        return slug, template.format(slug=slug)

    return build


def _lever(match: re.Match) -> Optional[Tuple[str, str]]:
    eu, slug = match.group(1) or "", match.group(2)
    return (slug, f"https://jobs.{eu}lever.co/{slug}") if slug.lower() not in {"api", "v0"} else None


def _workday(match: re.Match) -> Optional[Tuple[str, str]]:
    tenant, pod, site = match.groups()
    if site.lower() in {"wday", "job", "jobs"}:
        return None
    return tenant, f"https://{tenant}.{pod}.myworkdayjobs.com/{site}"


def _workday_site(match: re.Match) -> Optional[Tuple[str, str]]:
    pod, tenant, site = match.groups()
    return tenant, f"https://{pod}.myworkdaysite.com/recruiting/{tenant}/{site}"


def _paylocity(match: re.Match) -> Optional[Tuple[str, str]]:
    guid, name = match.group(1), match.group(2) or ""
    return guid, f"https://recruiting.paylocity.com/recruiting/jobs/All/{guid}/{name}".rstrip("/")


def _dover_client(match: re.Match) -> Optional[Tuple[str, str]]:
    name, client = match.groups()
    return name, f"https://app.dover.com/{name}/careers/{client}"


def _icims(match: re.Match) -> Optional[Tuple[str, str]]:
    sub = match.group(1)
    if sub in {"www", "developer", "community", "help"}:
        return None
    return re.sub(r"^(?:careers|jobs|uscareers)-", "", sub), f"https://{sub}.icims.com/jobs/search?ss=1"


def _taleo(match: re.Match) -> Optional[Tuple[str, str]]:
    pod, path, org, cws = match.groups()
    return org, f"https://{pod}.tbe.taleo.net/{path}/ats/careers/v2/searchResults?org={org}&cws={cws}"


def _oracle(match: re.Match) -> Optional[Tuple[str, str]]:
    host_, lang, site = match.groups()
    return host_.split(".")[0], f"https://{host_}/hcmUI/CandidateExperience/{lang}/sites/{site}/jobs"


def _lead(match: re.Match) -> Optional[Tuple[str, str]]:
    return match.group(1), ""


SLUG = r"([A-Za-z0-9_-]+)"
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
# A subdomain that is not itself the tail of a longer host name.
SUB = r"(?<![\w.-])([a-z0-9][a-z0-9-]*)"
# Subdomains of job systems that are the vendor's own pages, not a customer's board.
VENDOR_SUBDOMAINS = {
    "www", "api", "app", "apply", "jobs", "help", "support", "status", "blog", "resources",
    "marketplace", "partners", "community", "assets", "static", "cdn", "careers", "marketing",
    "developers", "docs", "info", "go", "get",
}


def _fp(board: str, needle: str, pattern: str, build: Builder, flags: int = re.IGNORECASE) -> Fingerprint:
    return Fingerprint(board, needle, re.compile(pattern, flags), build)


FINGERPRINTS: List[Fingerprint] = [
    # Greenhouse: the embed script/iframe, the board API, and hosted boards.
    _fp("greenhouse", "greenhouse.io",
        r"(?:boards|job-boards)\.greenhouse\.io/embed/job_(?:board|app)(?:/js)?\?(?:[^\"'\s<>]*?&)?for=" + SLUG,
        _slug_link("https://job-boards.greenhouse.io/{slug}")),
    _fp("greenhouse", "greenhouse.io", r"(?<![\w.])(?:boards-api|api)\.greenhouse\.io/v1/boards/" + SLUG,
        _slug_link("https://job-boards.greenhouse.io/{slug}")),
    _fp("greenhouse", "greenhouse.io", r"(?<![\w.])(?:boards|job-boards)\.greenhouse\.io/" + SLUG,
        _slug_link("https://job-boards.greenhouse.io/{slug}", {"embed", "v1", "static", "assets", "api"})),
    _fp("lever", "lever.co", r"(?<![\w.])(?:jobs|api)\.(eu\.)?lever\.co/(?:v0/postings/)?" + SLUG, _lever),
    _fp("ashby", "ashbyhq.com", r"(?<![\w.])jobs\.ashbyhq\.com/([A-Za-z0-9_.%-]+)",
        _slug_link("https://jobs.ashbyhq.com/{slug}", {"api", "embed"})),
    _fp("ashby", "ashbyhq.com", r"api\.ashbyhq\.com/posting-api/job-board/([A-Za-z0-9_.%-]+)",
        _slug_link("https://jobs.ashbyhq.com/{slug}")),
    _fp(WORKABLE_JOB, "workable.com", r"apply\.workable\.com/j/([A-Za-z0-9]+)", _lead),
    _fp(WORKABLE_ACCOUNT, "whr_embed", r"whr_embed\(\s*(\d+)", _lead),
    _fp("workable", "workable.com", r"apply\.workable\.com/" + SLUG,
        _slug_link("https://apply.workable.com/{slug}/", {"api", "j", "static", "assets"})),
    _fp("workable", "workable.com", SUB + r"\.workable\.com",
        _slug_link("https://apply.workable.com/{slug}/", VENDOR_SUBDOMAINS | {"workablehr", "careers-page"})),
    _fp("rippling", "rippling.com", r"ats\.rippling\.com/(?:[a-z]{2}-[A-Z]{2}/)?" + SLUG,
        _slug_link("https://ats.rippling.com/{slug}/jobs", {"api", "static"}), flags=0),
    _fp("rippling", "rippling.com", r"api\.rippling\.com/platform/api/ats/v\d/board/" + SLUG,
        _slug_link("https://ats.rippling.com/{slug}/jobs")),
    _fp("bamboohr", "bamboohr.com", SUB + r"\.bamboohr\.com",
        _slug_link("https://{slug}.bamboohr.com/careers", VENDOR_SUBDOMAINS)),
    _fp("dover", "app.dover.", r"app\.dover\.(?:com|io)/" + SLUG + r"/careers/(" + UUID + ")", _dover_client),
    _fp("dover", "app.dover.", r"app\.dover\.(?:com|io)/jobs/" + SLUG, _slug_link("https://app.dover.com/jobs/{slug}")),
    # A job's apply link names the client, not the board slug.
    _fp(DOVER_CLIENT, "app.dover.", r"app\.dover\.(?:com|io)/apply/(" + UUID + ")/", _lead),
    _fp("gem", "gem.com", r"(?:jobs\.gem\.com|api\.gem\.com/job_board/v0)/" + SLUG,
        _slug_link("https://jobs.gem.com/{slug}", {"api", "static"})),
    _fp("jazzhr", "applytojob.com", SUB + r"\.applytojob\.com", _slug_link("https://{slug}.applytojob.com/apply", VENDOR_SUBDOMAINS)),
    _fp("workday", "myworkdayjobs.com",
        SUB + r"\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}[-_][A-Za-z]{2}/)?" + SLUG, _workday),
    _fp("workday", "myworkdaysite.com",
        r"(wd\d+)\.myworkdaysite\.com/(?:[a-z]{2}[-_][A-Za-z]{2}/)?recruiting/" + SLUG + "/" + SLUG, _workday_site),
    _fp("eightfold", "eightfold.ai", SUB + r"\.eightfold\.ai/careers",
        _slug_link("https://{slug}.eightfold.ai/careers", VENDOR_SUBDOMAINS)),
    _fp("paylocity", "paylocity.com", r"recruiting\.paylocity\.com/recruiting/jobs/all/(" + UUID + r")(?:/([A-Za-z0-9_-]+))?",
        _paylocity),
    _fp("gusto", "jobs.gusto.com", r"jobs\.gusto\.com/boards/([A-Za-z0-9-]+?-" + UUID + ")",
        _slug_link("https://jobs.gusto.com/boards/{slug}")),
    _fp("kula", "kula.ai", r"careers\.kula\.ai/" + SLUG, _slug_link("https://careers.kula.ai/{slug}", {"api", "assets"})),
    _fp("smartrecruiters", "smartrecruiters.com", r"(?:careers|jobs)\.smartrecruiters\.com/" + SLUG,
        _slug_link("https://careers.smartrecruiters.com/{slug}", {"oneclick-ui", "api", "static", "js", "css"})),
    _fp("icims", "icims.com", SUB + r"\.icims\.com/jobs", _icims),
    _fp("paycom", "paycomonline.net", r"paycomonline\.net/v4/ats/web\.php/portal/([A-Za-z0-9]+)",
        _slug_link("https://www.paycomonline.net/v4/ats/web.php/portal/{slug}/career-page")),
    _fp("paycor", "recruitingbypaycor.com", r"recruitingbypaycor\.com/career/CareerHome\.action\?(?:[^\"'\s<>]*?&)?clientId=([0-9a-fA-F]+)",
        _slug_link("https://recruitingbypaycor.com/career/CareerHome.action?clientId={slug}")),
    _fp("taleo", "taleo.net",
        r"([a-z0-9]+)\.tbe\.taleo\.net/(\w+)/ats/careers/v2/\w+\?(?:[^\"'\s<>]*?&)?org=([A-Za-z0-9]+)&(?:amp;)?cws=(\d+)",
        _taleo),
    _fp("oraclehcm", "oraclecloud.com",
        r"([a-z0-9.-]+\.oraclecloud\.com)/hcmUI/CandidateExperience/([a-z]{2}(?:-[A-Z]{2})?)/sites/(\w+)", _oracle),
    _fp(CAREERPUCK, "careerpuck.com", r"app\.careerpuck\.com/job-board/" + SLUG, _lead),
    _fp(CAREERPUCK, "careerpuck.com", SUB + r"\.careerpuck\.com", _slug_link("", VENDOR_SUBDOMAINS | {"public", "unfurl"})),
]

# The Teamio/LMC widget names no board in a URL: the careers page itself is the Link.
TEAMIO_MARKER = "__LMC_CAREER_WIDGET__"

# Links for a board known only by its account slug (a guess, or a CareerPuck/Workable lead).
BOARD_LINKS = {
    "greenhouse": "https://job-boards.greenhouse.io/{slug}",
    "lever": "https://jobs.lever.co/{slug}",
    "ashby": "https://jobs.ashbyhq.com/{slug}",
    "workable": "https://apply.workable.com/{slug}/",
}

# Domains of job systems and career-site hosts: a link there says nothing about
# which domain the company itself owns.
JOB_SYSTEM_DOMAINS = {
    "greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "rippling.com", "bamboohr.com",
    "dover.com", "dover.io", "gem.com", "applytojob.com", "myworkdayjobs.com", "myworkdaysite.com",
    "eightfold.ai", "paylocity.com", "gusto.com", "kula.ai", "smartrecruiters.com", "icims.com",
    "careerpuck.com", "paycomonline.net", "recruitingbypaycor.com", "taleo.net", "oraclecloud.com",
    "jobvite.com", "recruitee.com", "breezy.hr", "teamtailor.com", "personio.de", "personio.com",
    "pinpointhq.com", "wellfound.com", "angel.co", "ycombinator.com", "workatastartup.com", "adp.com",
    "ultipro.com", "successfactors.com", "zohorecruit.com", "freshteam.com", "homerun.co", "comeet.com",
    "join.com", "polymer.co", "trakstar.com", "jobscore.com", "applicantpro.com", "trinethire.com",
    "careers-page.com", "avature.net", "phenompeople.com", "factorialhr.com", "linkedin.com",
}


def board_link(board: str, slug: str) -> str:
    """Return the Link for a *board* account known by its *slug* (Greenhouse, Lever, Ashby, Workable)."""
    return BOARD_LINKS[board].format(slug=slug)

# Job systems phlux has no reader for, so a company using one can't be added yet:
# (name, needle, pattern), the needle as in :class:`Fingerprint`.
UNSUPPORTED: List[Tuple[str, str, re.Pattern]] = [
    (name, needle, re.compile(pattern, re.IGNORECASE))
    for name, needle, pattern in [
        ("Greenhouse EU", "eu.greenhouse.io", r"(?:job-)?boards\.eu\.greenhouse\.io/"),
        ("Jobvite", "jobvite.com", r"jobs\.jobvite\.com/"),
        ("Recruitee", "recruitee.com", r"[a-z0-9-]+\.recruitee\.com"),
        ("Breezy HR", "breezy.hr", r"[a-z0-9-]+\.breezy\.hr"),
        ("Teamtailor", "teamtailor.com", r"[a-z0-9-]+\.teamtailor\.com"),
        ("Personio", "personio.", r"\.jobs\.personio\.(?:de|com)"),
        ("Pinpoint", "pinpointhq.com", r"[a-z0-9-]+\.pinpointhq\.com"),
        ("Wellfound", "/company/", r"(?:wellfound\.com|angel\.co)/company/[\w-]+/jobs"),
        ("YC Work at a Startup", "/companies/", r"ycombinator\.com/companies/[\w-]+/jobs"),
        ("YC Work at a Startup", "workatastartup.com", r"workatastartup\.com/"),
        ("ADP", "adp.com", r"workforcenow\.adp\.com|myjobs\.adp\.com"),
        ("UKG", "ultipro.com", r"recruiting2?\.ultipro\.com"),
        ("SuccessFactors", "successfactors", r"career\d*\.successfactors\.(?:com|eu)"),
        ("Zoho Recruit", "zohorecruit.", r"[a-z0-9-]+\.zohorecruit\.(?:com|eu|in)"),
        ("Freshteam", "freshteam.com", r"[a-z0-9-]+\.freshteam\.com/jobs"),
        ("Homerun", "homerun.co", r"[a-z0-9-]+\.homerun\.co"),
        ("Comeet", "comeet.co", r"comeet\.(?:com|co)/jobs/"),
        ("JOIN", "join.com/companies/", r"join\.com/companies/"),
        ("Polymer", "jobs.polymer.co", r"jobs\.polymer\.co/"),
        ("Trakstar Hire", "hire.trakstar.com", r"[a-z0-9-]+\.hire\.trakstar\.com"),
        ("JobScore", "careers.jobscore.com", r"careers\.jobscore\.com/"),
        ("ApplicantPro", "applicantpro.com", r"[a-z0-9-]+\.applicantpro\.com"),
        ("TriNet Hire", "trinethire.com", r"app\.trinethire\.com"),
        ("Manatal", "careers-page.com", r"careers-page\.com/"),
        ("Avature", "avature.net", r"[a-z0-9-]+\.avature\.net"),
        ("Phenom", "phenompeople.com", r"cdn\.phenompeople\.com"),
        ("Factorial", "factorialhr.com", r"[a-z0-9-]+\.factorialhr\.com"),
    ]
]

# A board's hosts, named by pages that build its URLs in script (``'…?for=' + BOARD``),
# so the slug is not in the text but the board is: board -> (needles, pattern).
BOARD_HOSTS = {
    "greenhouse": (("greenhouse", "gh_jid"), re.compile(
        r"(?<![\w.])(?:boards|job-boards|boards-api|api)\.greenhouse\.io\b|\bgh_jid\b", re.I)),
    "ashby": (("ashby",), re.compile(r"(?<![\w.])(?:jobs|api)\.ashbyhq\.com\b|\bashby_jid\b", re.I)),
    "lever": (("lever.co",), re.compile(r"(?<![\w.])(?:jobs|api)\.lever\.co\b", re.I)),
}
# Job ids that custom careers pages put in their links to a board's job pages.
JOB_IDS = {
    "greenhouse": re.compile(r"[?&]gh_jid=(\d+)"),
    "ashby": re.compile(r"[?&]ashby_jid=(" + UUID + ")", re.IGNORECASE),
}

_ESCAPES = (("\\/", "/"), ("\\u002F", "/"), ("\\u002f", "/"), ("&amp;", "&"),
            ("%2F", "/"), ("%2f", "/"), ("%3A", ":"), ("%3a", ":"))


def unescape(text: str) -> str:
    """Undo the escapes that hide URLs in JSON, HTML attributes and query strings."""
    for old, new in _ESCAPES:
        text = text.replace(old, new)
    return text


def find_boards(text: str, page_url: str = "") -> List[Hit]:
    """Return the boards (and leads) *text* names, in the order they first appear, without repeats.

    *page_url* is the page *text* came from; a Teamio widget's Link is that page.
    """
    text = unescape(text)
    lowered = text.lower()
    found: List[Tuple[int, Hit]] = []
    for fp in FINGERPRINTS:
        if fp.needle not in lowered:
            continue
        for match in fp.pattern.finditer(text):
            built = fp.build(match)
            if built:
                found.append((match.start(), Hit(fp.board, built[0], built[1])))
    if page_url and TEAMIO_MARKER in text:
        found.append((text.index(TEAMIO_MARKER), Hit("teamio", domain_label(host(page_url)), page_url)))
    hits: List[Hit] = []
    for _, hit in sorted(found, key=lambda pair: pair[0]):
        if hit not in hits and not any(_same_board(hit, h) for h in hits):
            hits.append(hit)
    return hits


def _same_board(a: Hit, b: Hit) -> bool:
    """Return True for two hits naming one account (e.g. its embed and its hosted board)."""
    return a.board == b.board and a.board not in LEADS and a.slug.lower() == b.slug.lower()


def find_unsupported(text: str) -> List[str]:
    """Return the names of job systems in *text* that phlux has no reader for."""
    text = unescape(text)
    lowered = text.lower()
    found = [name for name, needle, pattern in UNSUPPORTED if needle in lowered and pattern.search(text)]
    return list(dict.fromkeys(found))


def find_hints(text: str) -> Dict[str, Set[str]]:
    """Return the boards *text* mentions even without a slug, each with the job ids it links.

    A custom careers page may build its board URL in script, or link jobs as
    ``?gh_jid=<id>``; either way the page says which board to guess slugs on,
    and a job id proves a guessed slug right.
    """
    text = unescape(text)
    lowered = text.lower()
    hints = {board: set() for board, (needles, pattern) in BOARD_HOSTS.items()
             if any(n in lowered for n in needles) and pattern.search(text)}
    for board, pattern in JOB_IDS.items():
        ids = set(pattern.findall(text))
        if ids:
            hints.setdefault(board, set()).update(ids)
    return hints
