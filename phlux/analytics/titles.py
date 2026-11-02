"""Step 3: pull structured fields out of a job title.

The scraper stores nothing but a title string, so season, target year, level,
degree and domain all have to be read back out of the text. Every rule here is a
regex over the lowercased title; the domain rules are ordered and the first match
wins, which is how "Machine Learning Software Engineer" lands in ``ml_ai`` rather
than ``software``.

The internship test is stricter than :func:`phlux.utils.is_internship`, which the
email alerts use: that one matches the bare substring ``"ship"`` and so also fires
on "Leadership", "Ownership" and "Shipping". Word boundaries are used here instead,
because a false positive that is harmless in an email digest would skew a chart.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple

# ── Seasons ───────────────────────────────────────────────────────────────────

_SEASON_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("summer", re.compile(r"\bsummer\b")),
    ("fall", re.compile(r"\b(?:fall|autumn)\b")),
    ("winter", re.compile(r"\bwinter\b")),
    ("spring", re.compile(r"\bspring\b")),
]

# ── Target year ───────────────────────────────────────────────────────────────

_YEAR_RE = re.compile(r"\b(20[2-3]\d)\b")

# ── Internship / level ────────────────────────────────────────────────────────

_INTERNSHIP_RE = re.compile(
    r"\bintern(?:s|ship|ships)?\b"
    r"|\bco-?ops?\b|\bco op\b"
    r"|\bapprentice(?:ship)?s?\b"
    r"|\btrainees?\b"
    r"|\bexternship\b"
    r"|\bpracticum\b"
    r"|\bsummer analyst\b"
    r"|\bstudent (?:researcher|worker|associate|assistant)\b"
    r"|\b(?:industrial )?placement student\b"
)

_NEW_GRAD_RE = re.compile(
    r"\bnew ?grad(?:uate)?s?\b"
    r"|\b(?:university|college|recent) grad(?:uate)?s?\b"
    r"|\bgrad(?:uate)? (?:program|hire|rotational|scheme)\b"
    r"|\bearly career\b"
    r"|\bentry[- ]level\b"
    r"|\bcampus hire\b"
    r"|\brotational program\b"
    r"|\bresidency\b"
    r"|\bassociate program\b"
)

# ── Degree ────────────────────────────────────────────────────────────────────

_DEGREE_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("phd", re.compile(r"\bph\.? ?d\.?\b|\bdoctoral\b|\bdoctorate\b")),
    ("masters", re.compile(r"\bm\.? ?s\.?\b|\bmaster'?s\b|\bmba\b|\bm\.? ?eng\b")),
    ("bachelors", re.compile(r"\bb\.? ?s\.?\b|\bbachelor'?s?\b|\bundergrad(?:uate)?\b")),
]

# Ranked most advanced first, so DEGREE_ORDER[0] wins when a title lists several
# ("Student Researcher, BS/MS" keeps both in `degrees` but reports "masters").
DEGREE_ORDER = ("phd", "masters", "bachelors")

# ── Domain ────────────────────────────────────────────────────────────────────

# Ordered: the first pattern that matches decides the domain. Specific fields come
# before the generic engineering catch-alls.
_DOMAIN_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("quant_finance", re.compile(
        r"\bquant(?:itative)?\b|\btrad(?:er|ing)\b|\bactuar(?:y|ial)\b"
        r"|\bportfolio\b|\bhedge\b|\bmarket mak|\bderivatives?\b"
        r"|\bequit(?:y|ies)\b|\bsecurities\b|\binvestment\b|\basset management\b"
        r"|\bfixed income\b|\bcommodit|\bexchange\b"
    )),
    ("ml_ai", re.compile(
        r"\bmachine learning\b|\bml\b|\bai\b|\bartificial intelligence\b"
        r"|\bdeep learning\b|\bnlp\b|\bnatural language\b|\bcomputer vision\b"
        r"|\bllms?\b|\bgenerative\b|\bperception\b|\breinforcement learning\b"
        r"|\bspeech\b|\brecommend(?:er|ation)\b"
    )),
    ("data", re.compile(
        r"\bdata (?:scien|engineer|analy|platform|infrastructure)"
        r"|\banalytics?\b|\bbusiness intelligence\b|\bstatistic(?:s|ian|al)\b"
        r"|\bdata scientist\b|\bdata (?:management|governance|quality|steward)"
    )),
    ("security", re.compile(
        r"\bsecurity\b|\bcryptograph|\binfosec\b|\bprivacy\b|\btrust (?:and|&) safety\b"
        r"|\bpenetration test|\bthreat\b"
    )),
    ("hardware", re.compile(
        r"\bhardware\b|\basic\b|\brtl\b|\bsilicon\b|\bfpga\b|\bembedded\b"
        r"|\bfirmware\b|\belectrical\b|\bmechanical\b|\bthermal\b|\bcircuits?\b"
        r"|\bsemiconductor\b|\bchip\b|\bphysical design\b|\bsignal (?:and power )?integrity\b"
        r"|\bpcb\b|\bmechatronic|\bvlsi\b|\bverification engineer\b|\banalog\b"
        r"|\bmanufactur|\bmaterials?\b|\brobotics?\b|\bmotor\b|\boptical\b"
    )),
    ("other_engineering", re.compile(
        r"\bchemical\b|\bcivil\b|\bbio ?(?:medical|engineer|logy|logical)\b"
        r"|\baerospace\b|\baeronautic|\bpropulsion\b|\bstructural\b"
        r"|\bindustrial engineer|\benvironmental\b|\bchemistry\b|\bphysics\b"
        r"|\bclinical\b|\bpharma|\bgeolog|\bnuclear\b|\bavionics\b"
    )),
    ("software", re.compile(
        r"\bsoftware\b|\bswe\b|\bdeveloper\b|\bdevelopment engineer\b"
        r"|\bback ?end\b|\bfront ?end\b|\bfull[- ]?stack\b|\bmobile\b|\bios\b"
        r"|\bandroid\b|\bplatform\b|\binfrastructure\b|\bdevops\b|\bsre\b"
        r"|\bsite reliability\b|\bcloud\b|\bsystems? engineer\b|\bweb\b"
        r"|\bcompiler\b|\bnetwork(?:ing)? engineer\b|\bqa\b|\btest engineer\b"
        r"|\binformation technology\b|\bit support\b|\bhelp ?desk\b|\bdatabase\b"
    )),
    ("product", re.compile(
        r"\bproduct manage|\bproduct management\b|\bapm\b|\bassociate product\b"
        r"|\btechnical program manage|\btpm\b|\bprogram manage"
    )),
    ("design", re.compile(
        r"\bdesigner\b|\bux\b|\bui\b|\buser experience\b|\buser research\b"
        r"|\bgraphic design\b|\bindustrial design\b|\bbrand design\b"
    )),
    ("research", re.compile(r"\bresearch|\bscientist\b|\bscience\b|\bscholar\b")),
    ("business", re.compile(
        r"\bfinance\b|\bfinancial\b|\baccounting\b|\bmarketing\b|\bsales\b"
        r"|\bbusiness\b|\boperations?\b|\bstrateg(?:y|ic)\b|\bconsult(?:ing|ant)\b"
        r"|\blegal\b|\bcounsel\b|\bhuman resources\b|\bpeople\b|\brecruit"
        r"|\bcommunications?\b|\bsupply chain\b|\blogistics\b|\bprocurement\b"
        r"|\baudit\b|\btax\b|\bcustomer\b|\bsupport\b|\badmin|\banalyst\b"
        r"|\bhr\b|\bcompliance\b|\bregulatory\b|\brisk\b|\btechnical writ"
        r"|\bdocumentation\b|\bwriter\b|\beditorial\b|\bcontent\b|\bmedia\b"
        r"|\bmerchandis|\bbuyer\b|\bbuying\b|\bretail\b|\bstore\b|\bpricing\b"
    )),
    # Last resort before "other": a title that says engineering but names no
    # discipline. Kept separate rather than folded into software, which would
    # overstate how much of the board is a software job.
    ("engineering_general", re.compile(
        r"\bengineer(?:ing|s)?\b|\bautomation\b|\bdft\b|\btechnician\b"
    )),
]

# A title with none of these reads as page furniture rather than a job (nav labels,
# blog headlines, location filters) and is flagged rather than silently classified.
_ROLE_WORD_RE = re.compile(
    r"engineer|intern|analyst|scientist|develop|design|research|manager|associate"
    r"|specialist|technician|coordinator|architect|consultant|program|co-?op"
    r"|apprentic|trainee|fellow|graduate|technolog|software|hardware|data|product"
    r"|quant|security|marketing|finance|account|sales|operation|business|legal"
    r"|human resource|recruit|support|admin|advisor|strateg|writer|editor|artist"
    r"|animator|counsel|nurse|therap|teach|instructor|professor|attorney|audit"
    r"|tax|actuar|underwrit|pilot|mechanic|electric|civil|chemical|biolog|physic"
    r"|math|statistic|assistant|lead\b|director|officer|clerk|buyer|planner"
)


@dataclass(frozen=True)
class ParsedTitle:
    """Structured fields read out of a job title.

    Attributes:
        season: First season named in the title, or None.
        seasons: Every season named, in the order they appear, pipe-joined.
        target_year: First 20xx year in the title, or None.
        is_internship: Whether the title names an internship, co-op or equivalent.
        level: ``"intern"``, ``"new_grad"`` or ``"unspecified"``.
        degree: Most advanced degree named, or None.
        degrees: Every degree named, pipe-joined in :data:`DEGREE_ORDER` order.
        domain: First matching entry in the ordered domain table, else ``"other"``.
        has_role_word: False when the text contains no job vocabulary at all,
            which usually means the scraper picked up page furniture.
    """

    season: Optional[str]
    seasons: str
    target_year: Optional[int]
    is_internship: bool
    level: str
    degree: Optional[str]
    degrees: str
    domain: str
    has_role_word: bool

    def as_dict(self) -> Dict[str, object]:
        """Return the fields as a plain dict, ready to become dataframe columns."""
        return asdict(self)


def _find_seasons(text: str) -> List[str]:
    """Return the seasons named in *text*, ordered by where they appear."""
    hits = []
    for name, pattern in _SEASON_PATTERNS:
        match = pattern.search(text)
        if match:
            hits.append((match.start(), name))
    return [name for _, name in sorted(hits)]


def _find_degrees(text: str) -> List[str]:
    """Return the degrees named in *text*, most advanced first."""
    found = {name for name, pattern in _DEGREE_PATTERNS if pattern.search(text)}
    return [name for name in DEGREE_ORDER if name in found]


def _find_domain(text: str) -> str:
    """Return the first matching domain, or ``"other"``."""
    for name, pattern in _DOMAIN_PATTERNS:
        if pattern.search(text):
            return name
    return "other"


def is_internship(title: str) -> bool:
    """Return True if *title* names an internship, co-op or equivalent.

    Stricter than :func:`phlux.utils.is_internship`: this one respects word
    boundaries, so "Leadership Program" and "Shipping Analyst" do not match.
    """
    return bool(_INTERNSHIP_RE.search(title.lower()))


def parse_title(title: str) -> ParsedTitle:
    """Read season, target year, level, degree and domain out of a job title.

    Args:
        title: Raw title string as scraped.

    Returns:
        A :class:`ParsedTitle` with whatever the text supports; fields the title
        does not mention come back as None or ``"unspecified"``.
    """
    text = title.lower()

    seasons = _find_seasons(text)
    degrees = _find_degrees(text)
    year_match = _YEAR_RE.search(text)
    intern = bool(_INTERNSHIP_RE.search(text))

    if intern:
        level = "intern"
    elif _NEW_GRAD_RE.search(text):
        level = "new_grad"
    else:
        level = "unspecified"

    return ParsedTitle(
        season=seasons[0] if seasons else None,
        seasons="|".join(seasons),
        target_year=int(year_match.group(1)) if year_match else None,
        is_internship=intern,
        level=level,
        degree=degrees[0] if degrees else None,
        degrees="|".join(degrees),
        domain=_find_domain(text),
        has_role_word=bool(_ROLE_WORD_RE.search(text)),
    )
