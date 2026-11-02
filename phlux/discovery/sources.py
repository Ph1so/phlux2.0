"""Where candidate companies come from: the open YC dataset and a hand-kept seed file.

A source is anything with a ``name`` and a ``candidates()`` method returning
:class:`Candidate` objects, so another directory can be added without touching
the rest of discovery.

:class:`YCSource` reads `yc-oss <https://github.com/yc-oss/api>`_, a daily
mirror of YC's company directory, one JSON file per tag or industry. Only
companies whose status is ``Active`` are kept. Its tags were chosen by reading
what each one holds: :data:`ROBOTICS_TAGS` are robots and autonomy;
:data:`ADJACENT_TAGS` are the hardware, aerospace and EV companies that hire
the same students (the owner's list already has SpaceX, Joby, Rivian). Broader
tags were left out after reading them: "hardware" is mostly phones and
gadgets, "automation"/"robotic process automation" are office software, and
"defense"/"computer vision" are mostly software too.

:class:`SeedFile` reads ``discovery/seeds.txt``, where the owner drops
companies heard about elsewhere, one ``Name,website`` per line.
"""
from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Protocol, Tuple

from ..adapters.base import get
from .names import LEGAL_WORDS, name_key, registrable_domain

logger = logging.getLogger(__name__)

YC_API = "https://yc-oss.github.io/api/{path}.json"

# Lists under the API: "tags/…" are YC's tags, "industries/…" its industries.
ROBOTICS_TAGS: Tuple[str, ...] = (
    "tags/robotics", "tags/drones", "tags/autonomous-delivery", "tags/autonomous-trucking",
    "tags/autonomous-shipping", "tags/self-driving-vehicles", "tags/unmanned-vehicle",
    "tags/food-service-robots-and-machines", "tags/medical-robotics", "tags/robotic-surgery",
    "tags/swarm-robotics", "tags/lidar", "industries/manufacturing-and-robotics", "industries/drones",
)
ADJACENT_TAGS: Tuple[str, ...] = (
    "tags/hard-tech", "tags/aerospace", "tags/space-exploration", "tags/commercial-space-launch",
    "tags/electric-vehicles", "industries/aviation-and-space",
)


@dataclass
class Candidate:
    """A company that might be worth tracking.

    ``focus`` is "robotics" for companies in a robotics tag, "adjacent" for the
    rest; ``matched`` lists the source lists the company was found in.
    """

    name: str
    website: str
    source: str
    focus: str = "robotics"
    one_liner: str = ""
    tags: List[str] = field(default_factory=list)
    matched: List[str] = field(default_factory=list)
    batch: str = ""
    locations: str = ""
    hiring: Optional[bool] = None
    yc_url: str = ""
    former_names: List[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return candidate_key(self.name, self.website)


def candidate_key(name: str, website: str) -> str:
    """Return a company's identity across runs and sources: its website's domain, else its name."""
    domain = registrable_domain(website) if website else ""
    return domain or f"name:{name_key(name)}"


class Source(Protocol):
    name: str

    def candidates(self) -> List[Candidate]:
        ...


class YCSource:
    """Active companies in the chosen yc-oss tag and industry lists."""

    name = "yc"

    def __init__(self, robotics: Iterable[str] = ROBOTICS_TAGS, adjacent: Iterable[str] = ADJACENT_TAGS):
        self.lists = [(path, "robotics") for path in robotics] + [(path, "adjacent") for path in adjacent]

    def candidates(self) -> List[Candidate]:
        """Return each active company once, robotics focus winning over adjacent.

        Raises:
            requests.HTTPError: If a list can't be read; a partial run would
                drop companies from the report, so it is better not to run.
        """
        found: Dict[int, Candidate] = {}
        for path, focus in self.lists:
            for company in get(YC_API.format(path=path)).json():
                if company.get("status") != "Active":
                    continue
                label = path.split("/", 1)[1]
                candidate = found.get(company["id"])
                if candidate is None:
                    found[company["id"]] = candidate = self._candidate(company, focus)
                elif focus == "robotics":
                    candidate.focus = "robotics"
                if label not in candidate.matched:
                    candidate.matched.append(label)
        return list(found.values())

    @staticmethod
    def _candidate(company: dict, focus: str) -> Candidate:
        name = (company.get("name") or "").strip()
        return Candidate(
            name=name,
            website=(company.get("website") or "").strip(),
            source="yc",
            focus=focus,
            one_liner=(company.get("one_liner") or "").strip(),
            tags=list(company.get("tags") or []),
            batch=company.get("batch") or "",
            locations=company.get("all_locations") or "",
            hiring=company.get("isHiring"),
            yc_url=company.get("url") or "",
            # YC splits "Acme, Inc" into two former names; a bare "Inc" names nothing.
            former_names=[n for n in company.get("former_names") or []
                          if n and n != name and name_key(n) not in LEGAL_WORDS],
        )


class SeedFile:
    """Companies listed by hand in a ``Name,website`` file (``#`` starts a comment)."""

    name = "seeds"

    def __init__(self, path: Path):
        self.path = Path(path)

    def candidates(self) -> List[Candidate]:
        if not self.path.exists():
            return []
        lines = [line for line in self.path.read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.lstrip().startswith("#")]
        found = []
        for row in csv.reader(lines):
            name = row[0].strip() if row else ""
            if not name:
                continue
            website = row[1].strip() if len(row) > 1 else ""
            found.append(Candidate(name=name, website=website, source="seeds", focus="robotics"))
        return found


def gather(sources: Iterable[Source]) -> List[Candidate]:
    """Return every source's candidates, each company once (by domain, then name)."""
    seen: Dict[str, Candidate] = {}
    by_name: Dict[str, Candidate] = {}
    for source in sources:
        for candidate in source.candidates():
            twin = seen.get(candidate.key) or by_name.get(name_key(candidate.name))
            if twin is not None:
                if candidate.source not in twin.source.split("+"):
                    twin.source += f"+{candidate.source}"
                continue
            seen[candidate.key] = candidate
            by_name[name_key(candidate.name)] = candidate
    return list(seen.values())
