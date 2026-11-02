"""Command line: ``python -m phlux.discovery`` checks every candidate; ``… detect <url>`` checks one site.

A full run gathers candidates from the sources, skips those ``companies.csv``
already has, detects each remaining company's board (at most :data:`MAX_WORKERS`
at a time, so no site or board API sees more than a few requests at once), and
writes ``discovery/candidates.json`` and ``discovery/README.md``.

``detect`` is the by-hand helper: give it a company's home page, careers page
or board URL and it prints the ``companies.csv`` row to paste.
"""
from __future__ import annotations

import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import requests

from ..adapters.base import get
from .crawl import PAGE_TIMEOUT, normalize_url, site_name
from .detect import Detection, detect
from .fingerprints import find_boards
from .names import domain_label, host
from .report import build, load, record, skipped_record, stamp, write
from .sources import Candidate, SeedFile, Source, YCSource, gather
from .tracked import Match, TrackedIndex

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO_ROOT / "discovery"
COMPANIES_CSV = REPO_ROOT / "companies.csv"
MAX_WORKERS = 8


def check(candidate: Candidate, tracked: TrackedIndex) -> Tuple[Optional[Detection], Optional[Match]]:
    """Detect one candidate's board; a board some ``companies.csv`` row already reads makes it tracked."""
    try:
        detection = detect(candidate.name, candidate.website, candidate.batch)
    except Exception as error:  # One odd site must not sink the weekly run.
        logger.exception("%s: detection failed", candidate.name)
        return Detection(reason=f"detection failed: {type(error).__name__}: {error}"[:200]), None
    if detection.found:
        match = tracked.match_board(detection.board, detection.slug)
        if match:
            return None, match
    return detection, None


def discover(candidates: Sequence[Candidate], tracked: TrackedIndex, today: str,
             workers: int = MAX_WORKERS) -> Tuple[List[dict], List[dict]]:
    """Return the records of the candidates checked and of those skipped as tracked."""
    skipped: List[dict] = []
    todo: List[Candidate] = []
    for candidate in candidates:
        match = tracked.match(candidate)
        if match:
            skipped.append(skipped_record(candidate, match))
        else:
            todo.append(candidate)
    logger.info("%d candidates, %d already tracked, checking %d", len(candidates), len(skipped), len(todo))
    records: List[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, MAX_WORKERS))) as pool:
        futures = {pool.submit(check, candidate, tracked): candidate for candidate in todo}
        for future in as_completed(futures):
            candidate, (detection, match) = futures[future], future.result()
            if match:
                skipped.append(skipped_record(candidate, match))
                logger.info("%s: already tracked as %s (%s)", candidate.name, match.tracked.name, match.why)
                continue
            rec = record(candidate, detection, today)
            similar = tracked.similar(candidate)
            if similar:
                rec["similar_to"] = similar.tracked.name
            records.append(rec)
            logger.info("%s: %s", candidate.name, _summary(detection))
    return records, skipped


def _summary(detection: Detection) -> str:
    if not detection.found:
        return f"no board ({detection.reason})"
    return f"{detection.board} {detection.link} ({detection.postings} postings, {detection.internships} internships)"


def run(sources: Sequence[Source], out_dir: Path = OUT_DIR, csv_path: Path = COMPANIES_CSV,
        workers: int = MAX_WORKERS, limit: Optional[int] = None, today: Optional[str] = None) -> dict:
    """Check every candidate from *sources* and write the report into *out_dir*; return its data."""
    today = today or date.today().isoformat()
    candidates = gather(sources)
    if limit:
        candidates = candidates[:limit]
    records, skipped = discover(candidates, TrackedIndex.load(csv_path), today, workers)
    stamp(records, load(out_dir / "candidates.json"))
    data = build(records, skipped, [source.name for source in sources], today)
    write(out_dir, data)
    return data


def default_name(url: str) -> str:
    """Return a company name for *url*: a board's slug, else the site's own name, else its domain."""
    hits = find_boards(url)
    if hits and hits[0].slug:
        return hits[0].slug.replace("-", " ").title()
    try:
        name = site_name(get(normalize_url(url), timeout=PAGE_TIMEOUT).text)
    except requests.RequestException:
        name = ""
    return name or domain_label(host(url)).capitalize()


def detect_one(url: str, name: str = "") -> int:
    """Print the board and ``companies.csv`` row for one URL; return the exit status."""
    name = name or default_name(url)
    detection = detect(name, url)
    if not detection.found:
        print(f"No board phlux can read: {detection.reason}")
        for note in detection.notes:
            print(f"  - {note}")
        return 1
    print(f"Board:       {detection.board} ({detection.evidence})")
    print(f"Link:        {detection.link}")
    print(f"Postings:    {detection.postings}, of which internships: {detection.internships}")
    for title in detection.internship_titles:
        print(f"             - {title}")
    for note in detection.notes:
        print(f"Note:        {note}")
    if not detection.verified:
        print("Unverified:  only the name matches; open the board to check it is this company's.")
    print(f"Row:         {detection.row(name)}")
    print("Remember to add the name to the active list (lists/robotics.json) too.")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m phlux.discovery", description=__doc__.splitlines()[0])
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help="parallel companies (at most 8)")
    parser.add_argument("--limit", type=int, help="check only the first N candidates (for trying it out)")
    parser.add_argument("--out", type=Path, default=OUT_DIR, help="where to write the report")
    parser.add_argument("--no-yc", action="store_true", help="skip the YC dataset (seeds only)")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command")
    one = sub.add_parser("detect", help="print the companies.csv row for one company or careers URL")
    one.add_argument("url")
    one.add_argument("--name", default="", help="company name for the row (default: from the domain)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO if args.verbose or args.command != "detect" else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    if args.command == "detect":
        return detect_one(args.url, args.name)
    sources: List[Source] = [] if args.no_yc else [YCSource()]
    sources.append(SeedFile(args.out / "seeds.txt"))
    stats = run(sources, args.out, workers=args.workers, limit=args.limit)["stats"]
    print(f"{stats['considered']} candidates: {stats['tracked']} tracked, {stats['with_board']} with a board "
          f"({stats['with_internships']} with internships), {stats['name_only']} matched by name only, "
          f"{stats['unresolved']} unresolved, {stats['new']} new")
    return 0
