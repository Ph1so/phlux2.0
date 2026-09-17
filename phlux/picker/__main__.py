"""CLI entry point: ``python -m phlux.picker``."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from ..config import DEFAULT_CONFIG_PATH
from ..lists import DEFAULT_LISTS_DIR, REPO_ROOT
from . import serve


def main() -> None:
    """Parse arguments and start the picker server."""
    parser = argparse.ArgumentParser(
        prog="python -m phlux.picker",
        description="Swipe through companies.csv to build a company list JSON file.",
    )
    parser.add_argument("--csv", type=Path, default=REPO_ROOT / "companies.csv",
                        help="Path to companies.csv (default: repo root).")
    parser.add_argument("--lists-dir", type=Path, default=DEFAULT_LISTS_DIR,
                        help="Directory to read and write list files (default: lists/).")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH,
                        help="Path to config.json (default: repo root).")
    parser.add_argument("--port", type=int, default=8777,
                        help="Port to bind on localhost; 0 picks a free one.")
    parser.add_argument("--no-browser", action="store_true",
                        help="Don't open a browser tab automatically.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Log every request.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    serve(
        csv_path=args.csv,
        lists_dir=args.lists_dir,
        config_path=args.config,
        port=args.port,
        open_browser=not args.no_browser,
    )


if __name__ == "__main__":
    main()
