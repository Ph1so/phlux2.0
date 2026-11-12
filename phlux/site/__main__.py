"""Build the site, or refresh its logos.

``python -m phlux.site [--out site] [--storage FILE] [--fragment]`` builds the page;
``python -m phlux.site logos`` downloads the logos the scraped companies lack;
``python -m phlux.site geo`` refreshes the US map data (rarely needed).
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from phlux.lists import REPO_ROOT, scraped_companies

from . import geo, logos
from .build import build_site


def refresh_logos() -> None:
    companies = scraped_companies()
    try:
        icons = json.loads((REPO_ROOT / "icons.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        icons = {}
    print(f"Fetched {logos.fetch_missing([c.name for c in companies], icons)} logo(s)")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m phlux.site", description="Build the Phlux page.")
    parser.add_argument("command", nargs="?", choices=("build", "logos", "geo"), default="build")
    parser.add_argument("--out", type=Path, default=Path("site"), help="Output directory (default: site/).")
    parser.add_argument("--storage", type=Path, help="Storage file to read (default: the repo's storage.json).")
    parser.add_argument("--fragment", action="store_true",
                        help="Write the page body without <html>/<head>, for a claude.ai artifact preview.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("phlux.site").setLevel(logging.INFO)
    if args.command == "logos":
        refresh_logos()
        return
    if args.command == "geo":
        print("Wrote %d state outlines and %d places" % geo.refresh())
        return
    kwargs = {"storage_path": args.storage} if args.storage else {}
    print(build_site(args.out, document=not args.fragment, **kwargs))


if __name__ == "__main__":
    main()
