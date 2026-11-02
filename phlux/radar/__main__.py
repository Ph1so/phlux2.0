"""Build the site: ``python -m phlux.radar [--out site] [--fragment]``."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .build import build_site


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m phlux.radar", description="Build the Robotics Intern Radar page.")
    parser.add_argument("--out", type=Path, default=Path("site"), help="Output directory (default: site/).")
    parser.add_argument("--storage", type=Path, help="Storage file to read (default: the repo's storage.json).")
    parser.add_argument("--fragment", action="store_true",
                        help="Write the page body without <html>/<head>, for a claude.ai artifact preview.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("phlux.radar").setLevel(logging.INFO)
    kwargs = {"storage_path": args.storage} if args.storage else {}
    print(build_site(args.out, document=not args.fragment, **kwargs))


if __name__ == "__main__":
    main()
