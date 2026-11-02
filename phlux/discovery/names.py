"""Normalize company names, domains and board slugs so the same company compares equal.

Discovery has to recognize a company under several spellings: YC lists
"Relativity Space" while ``companies.csv`` says "Relativity", a Greenhouse
board calls itself "Welch’s " (curly apostrophe, trailing space), and a board
slug is "welchsinc". Three kinds of key cover this:

* :func:`name_key` drops case, accents and punctuation: "Welch’s" -> "welchs";
  :func:`legal_key` also drops a legal suffix (Inc, LLC…).
* :func:`core_key` also drops trailing generic words (Inc, Labs, AI, Robotics,
  Space…): "Relativity Space" -> "relativity". Short cores collide across
  different companies ("Path Robotics" and "PathAI" share "path"), so callers
  only compare cores of at least :data:`MIN_CORE` characters.
* :func:`registrable_domain` reduces a URL to the domain a company owns:
  ``https://careers.irobot.com/x`` -> ``irobot.com``.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, List
from urllib.parse import urlsplit

# Cores shorter than this are too likely to name several companies.
MIN_CORE = 5

# Trailing words that only give a company's legal form; dropping them is always safe.
LEGAL_WORDS = {"inc", "incorporated", "corp", "corporation", "co", "company", "llc", "ltd", "limited", "gmbh", "plc"}
# Trailing words that say what kind of company it is rather than which one.
GENERIC_WORDS = LEGAL_WORDS | {
    "technologies", "technology", "tech", "labs", "lab", "systems", "industries", "ai",
    "robotics", "robot", "robots", "autonomy", "aerospace", "space", "aviation", "motors",
    "automation", "hq", "the",
}

# Second-level suffixes under which companies register a third label (acme.co.uk).
_SECOND_LEVEL = {"co", "com", "org", "net", "ac", "gov", "edu", "ne", "or"}

# Words a startup puts around its name in a domain: getacme.com, acmehq.com.
_DOMAIN_PREFIXES = ("get", "try", "use", "join", "hello")
_DOMAIN_SUFFIXES = ("hq", "app", "inc", "team")
# Legal suffixes dropped from a display name: "Applied Electrodynamics, Inc."
_LEGAL_SUFFIX = re.compile(r"[,\s]+(?:inc|llc|ltd|corp|co|gmbh|plc)\.?$", re.IGNORECASE)


def words(name: str) -> List[str]:
    """Return *name*'s words, lowercased, without accents or punctuation."""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    text = text.replace("&", " and ")
    # Apostrophes join a word ("welch's" -> "welchs"); other punctuation splits.
    text = re.sub(r"['’`´]", "", text)
    return re.findall(r"[a-z0-9]+", text)


def name_key(name: str) -> str:
    """Return *name* without case, accents, punctuation or spaces."""
    return "".join(words(name))


def _strip(name: str, trailing: set) -> str:
    parts = words(name)
    while len(parts) > 1 and parts[-1] in trailing:
        parts.pop()
    while len(parts) > 1 and parts[0] == "the":
        parts.pop(0)
    return "".join(parts)


def legal_key(name: str) -> str:
    """Return :func:`name_key` without a legal suffix: "Ambi Robotics, Inc." -> "ambirobotics"."""
    return _strip(name, LEGAL_WORDS)


def core_key(name: str) -> str:
    """Return :func:`name_key` without trailing generic words (or all of it, if nothing else is left)."""
    return _strip(name, GENERIC_WORDS)


def name_variants(name: str) -> List[str]:
    """Return *name* and any alias in parentheses: "Flirtey (SkyDrop)" -> both."""
    variants = [re.sub(r"\s*\([^)]*\)", "", name).strip()]
    variants += [alias.strip() for alias in re.findall(r"\(([^)]*)\)", name)]
    return [v for v in variants if v]


def names_match(a: str, b: str) -> bool:
    """Return True if two company names are the same company by key or (long enough) core."""
    if legal_key(a) and legal_key(a) == legal_key(b):
        return True
    core = core_key(a)
    return len(core) >= MIN_CORE and core == core_key(b)


def display_name(name: str) -> str:
    """Return *name* as a ``companies.csv`` Name: no legal suffix or parenthetical alias."""
    name = (name_variants(name) or [name.strip()])[0]
    return _LEGAL_SUFFIX.sub("", name).strip() or name


def host(url: str) -> str:
    """Return *url*'s lowercase host without ``www.`` or a port; *url* may lack a scheme."""
    if "//" not in url:
        url = "//" + url
    netloc = urlsplit(url.strip()).netloc.lower().rsplit("@", 1)[-1].split(":")[0]
    return netloc.removeprefix("www.").rstrip(".")


def registrable_domain(url: str) -> str:
    """Return the domain a company registers for *url*: ``jobs.acme.co.uk`` -> ``acme.co.uk``."""
    labels = [label for label in host(url).split(".") if label]
    if len(labels) <= 2:
        return ".".join(labels)
    if labels[-2] in _SECOND_LEVEL and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def domain_label(domain: str) -> str:
    """Return the name part of a registrable domain: ``relativityspace.com`` -> ``relativityspace``."""
    return registrable_domain(domain).split(".")[0] if domain else ""


def slug_key(slug: str) -> str:
    """Return a board slug compared like a name: ``ispace-inc`` -> ``ispaceinc``."""
    return name_key(slug.replace("%20", " "))


def bare_label(label: str) -> str:
    """Return a domain label without startup affixes: ``getacme`` -> ``acme``, ``acmehq`` -> ``acme``."""
    for prefix in _DOMAIN_PREFIXES:
        if label.startswith(prefix) and len(label) - len(prefix) >= 4:
            label = label[len(prefix):]
            break
    for suffix in _DOMAIN_SUFFIXES:
        if label.endswith(suffix) and len(label) - len(suffix) >= 4:
            label = label[: -len(suffix)]
            break
    return label


def slug_guesses(name: str, domains: Iterable[str] = (), limit: int = 4) -> List[str]:
    """Return likely board slugs for a company, most specific first.

    "Relativity Space" at relativityspace.com gives ``relativityspace``,
    ``relativity-space`` and ``relativity``.
    """
    guesses: List[str] = []
    for variant in name_variants(name) or [name]:
        parts = words(variant)
        guesses += ["".join(parts), "-".join(parts)]
    for domain in domains:
        label = domain_label(domain)
        guesses += [label, bare_label(label)]
    guesses.append(core_key(name))
    unique: List[str] = []
    for guess in guesses:
        if len(guess) >= 2 and guess not in unique:
            unique.append(guess)
    return unique[:limit]
