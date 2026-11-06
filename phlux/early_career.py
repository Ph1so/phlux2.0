"""Find job descriptions that say a role is open to new grads.

Most robotics postings never put a level in the title ("Controls Engineer"), so
the title test (:mod:`phlux.analytics.titles`) misses roles whose descriptions
say "recent graduates are encouraged to apply" or ask for 0-2 years. Greenhouse,
Lever and Ashby send each posting's description with the board, so the line that
shows a role is open to new grads can be found at no extra cost.

A description qualifies when it

* says new grad, recent graduate, entry-level, early-career, graduating in…,
  class of 20xx or no experience required (not negated: "not an entry-level
  role"), and asks for no more than 2 years of experience anywhere; or
* asks for 0 years of experience somewhere ("0-2 years of experience").

A line that the same board's senior postings also carry is company boilerplate
("we hire from entry level to staff engineers" on every posting) and doesn't count.
"""
from __future__ import annotations

import html
import re
from typing import Dict, Iterable, List, Optional, Tuple

from .analytics.titles import is_senior_title

# How much of a description to keep: enough to read why a role qualified.
LINE_CHARS = 220

_EXPLICIT = re.compile(
    r"\bnew ?grad(?:uate)?s?\b|\brecent(?:ly)? (?:college |university )?grad(?:uate[sd]?)?\b"
    r"|\bentry[- ]level\b|\bearly[- ]career\b|\bgraduating (?:in|by|between|from)\b|\bclass of 20\d\d\b"
    r"|\b(?:upcoming|university|college) graduates?\b|\b(?:will|expected to|plan to) graduate\b"
    r"|\bgraduation (?:date|between|in)\b"
    r"|\bno (?:prior |professional |industry )?(?:work )?experience (?:is )?(?:required|necessary|needed)\b",
    re.IGNORECASE,
)
# A negation just before the phrase: "this is not an entry-level role".
_NEGATED = re.compile(r"\b(?:not|no|isn't|is not)\b[^.]{0,40}$", re.IGNORECASE)
# "3+ years of experience", "0-2 years of relevant experience", "1 to 3 years' experience".
_YEARS = re.compile(
    r"(\d{1,2})\s*\+?\s*(?:(?:-|–|to)\s*\d{1,2}\s*)?\+?\s*years?(?:'|’)?(?: of)?[^.;]{0,60}?\bexperience",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\s+-\s+|\n")


def html_text(markup: Optional[str]) -> str:
    """Return the readable text of a description's HTML (Greenhouse escapes it twice)."""
    text = html.unescape(html.unescape(markup or ""))
    return " ".join(re.sub(r"<[^>]+>", " ", text).split())


def _sentence(text: str, start: int, end: int) -> str:
    """Return the sentence around ``text[start:end]``, at most :data:`LINE_CHARS` long.

    "…" marks a side cut short: no sentence break nearby, or the sentence is too long.
    """
    breaks = [m.end() for m in _SENTENCE_END.finditer(text, max(0, start - 300), start)]
    left = breaks[-1] if breaks else max(0, start - 120)
    after = _SENTENCE_END.search(text, end, end + 300)
    right = after.start() if after else min(len(text), end + 120)
    line = " ".join(text[left:right].split()).lstrip("-•* ")
    cut_left, cut_right = not breaks and left > 0, not after and right < len(text)
    if len(line) > LINE_CHARS - 2:
        line, cut_right = line[:LINE_CHARS - 2].rstrip(), True
    return ("…" if cut_left else "") + line + ("…" if cut_right else "")


def _min_years(text: str) -> Optional[int]:
    years = [int(m.group(1)) for m in _YEARS.finditer(text) if int(m.group(1)) <= 20]
    return min(years) if years else None


def early_career_line(description: str, boilerplate: str = "") -> str:
    """Return the line of *description* that shows the role is open to new grads, or "".

    Args:
        description: The posting's description as plain text.
        boilerplate: Text the line must not appear in (the board's senior
            postings, whitespace collapsed), so company-wide wording doesn't count.
    """
    least = _min_years(description)
    if least is None or least <= 2:
        for m in _EXPLICIT.finditer(description):
            if _NEGATED.search(description[max(0, m.start() - 45):m.start()]):
                continue
            line = _sentence(description, m.start(), m.end())
            if line.strip("…") not in boilerplate:
                return line
    if least == 0:
        m = next(m for m in _YEARS.finditer(description) if int(m.group(1)) == 0)
        return _sentence(description, m.start(), m.end())
    return ""


def early_career_lines(postings: Iterable[Tuple[str, str, str]]) -> Dict[str, str]:
    """Return ``{id: line}`` for the postings whose descriptions show they take new grads.

    Args:
        postings: ``(id, title, description)`` for a whole board, so lines its
            senior postings share can be told apart as boilerplate.
    """
    rows: List[Tuple[str, str, str]] = [p for p in postings if p[2]]
    boilerplate = " ".join(" ".join(desc.split()) for _, title, desc in rows if is_senior_title(title))
    lines = {}
    for posting_id, title, desc in rows:
        if is_senior_title(title):
            continue
        line = early_career_line(desc, boilerplate)
        if line:
            lines[posting_id] = line
    return lines
