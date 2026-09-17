"""Local web app for building company lists by swiping through ``companies.csv``.

Run it with ``python -m phlux.picker``. It serves a card UI on localhost, one
card per company, and writes the resulting list straight into ``lists/``.

The server is deliberately bound to the loopback interface: it writes files into
the repository, so it must never be reachable from the network.
"""
from __future__ import annotations

import csv
import errno
import json
import logging
import threading
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlparse

from ..config import DEFAULT_CONFIG_PATH, load_config
from ..lists import (
    DEFAULT_LISTS_DIR,
    REPO_ROOT,
    CompanyList,
    available_lists,
    load_companies,
    load_company_list,
    resolve_list_path,
    save_company_list,
    slugify,
)

logger = logging.getLogger(__name__)

INDEX_PATH = Path(__file__).resolve().parent / "index.html"
MAX_BODY_BYTES = 1 << 20  # A list of names never approaches 1 MB.


def _load_json_file(path: Path) -> Dict[str, Any]:
    """Return the parsed JSON at *path*, or ``{}`` if it is missing or invalid."""
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _load_industries(path: Path) -> Dict[str, Dict[str, str]]:
    """Return ``industries.csv`` keyed by company name, or ``{}`` if absent."""
    try:
        with path.open(newline="", encoding="utf-8") as f:
            return {
                row["Name"].strip(): {
                    "sector": (row.get("Sector") or "").strip(),
                    "tier": (row.get("RoboticsTier") or "").strip(),
                    "segment": (row.get("RoboticsSegment") or "").strip(),
                }
                for row in csv.DictReader(f)
                if (row.get("Name") or "").strip()
            }
    except (OSError, KeyError):
        return {}


def build_session(
    csv_path: Path,
    icons_path: Path,
    industries_path: Path,
    lists_dir: Path,
    config_path: Path,
) -> Dict[str, Any]:
    """Assemble everything the UI needs for one swiping session.

    Args:
        csv_path: Path to ``companies.csv``.
        icons_path: Path to ``icons.json`` (logos; optional).
        industries_path: Path to ``industries.csv`` (sector labels; optional).
        lists_dir: Directory holding saved lists.
        config_path: Path to ``config.json``, read for the active list.

    Returns:
        A dict with ``companies``, existing ``lists``, and the ``active`` list.
    """
    icons = _load_json_file(icons_path)
    industries = _load_industries(industries_path)

    companies = []
    for company in load_companies(csv_path):
        meta = industries.get(company.name, {})
        icon = icons.get(company.name, "")
        companies.append(
            {
                "name": company.name,
                "link": company.link,
                "icon": icon if isinstance(icon, str) else icon.get("email", ""),
                "sector": meta.get("sector", ""),
                "tier": meta.get("tier", ""),
                "segment": meta.get("segment", ""),
            }
        )

    saved = []
    for path in available_lists(lists_dir):
        try:
            company_list = load_company_list(path, lists_dir)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Skipping unreadable list %s: %s", path, exc)
            continue
        saved.append(
            {
                "stem": path.stem,
                "name": company_list.name,
                "description": company_list.description,
                "companies": company_list.companies,
            }
        )

    return {
        "companies": companies,
        "lists": saved,
        "active": load_config(config_path).get("COMPANY_LIST") or "",
    }


def save_list_payload(payload: Dict[str, Any], lists_dir: Path) -> Dict[str, Any]:
    """Validate a save request from the UI and write the list file.

    Args:
        payload: Decoded request body with ``name``, ``companies``, and
            optionally ``description`` and ``stem``.
        lists_dir: Directory to write into.

    Returns:
        A dict describing the saved list.

    Raises:
        ValueError: If the payload is malformed or names an unsafe file.
    """
    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValueError("A list name is required.")

    names = payload.get("companies")
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise ValueError("'companies' must be a list of company names.")

    stem = slugify(str(payload.get("stem") or name))
    # slugify() already strips separators, but re-check so a future change to it
    # can never turn a request into a write outside lists_dir.
    if stem in {"", ".", ".."} or "/" in stem or "\\" in stem:
        raise ValueError(f"Unsafe list file name: {stem!r}")

    company_list = CompanyList(
        name=name,
        companies=[n.strip() for n in names if n.strip()],
        description=str(payload.get("description", "")).strip(),
        created=date.today().isoformat(),
    )
    path = save_company_list(company_list, stem, lists_dir)
    return {
        "stem": stem,
        "name": name,
        "count": len(company_list.companies),
        "path": str(path),
        "relpath": _display_path(path),
    }


def activate_list(stem: str, config_path: Path, lists_dir: Path) -> Dict[str, Any]:
    """Point ``COMPANY_LIST`` in ``config.json`` at *stem*.

    An empty *stem* clears the setting, which scrapes every company.

    Args:
        stem: List file stem, or ``""`` to scrape all companies.
        config_path: Path to ``config.json``.
        lists_dir: Directory holding saved lists.

    Returns:
        A dict with the value written.

    Raises:
        ValueError: If *stem* does not name an existing list.
    """
    config = load_config(config_path)
    if stem:
        stem = slugify(stem)
        if not resolve_list_path(stem, lists_dir).is_file():
            raise ValueError(f"No such list: {stem}")
        config["COMPANY_LIST"] = stem
    else:
        config.pop("COMPANY_LIST", None)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return {"active": stem}


def _display_path(path: Path) -> str:
    """Return *path* relative to the repo root when it lives inside it."""
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def make_handler(
    csv_path: Path,
    icons_path: Path,
    industries_path: Path,
    lists_dir: Path,
    config_path: Path,
) -> type[BaseHTTPRequestHandler]:
    """Build the request handler class bound to these file locations."""

    class PickerHandler(BaseHTTPRequestHandler):
        server_version = "phlux-picker"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
            logger.debug("%s - %s", self.address_string(), fmt % args)

        # ── helpers ──────────────────────────────────────────────────────────
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, status: int, data: Dict[str, Any]) -> None:
            self._send(status, json.dumps(data).encode("utf-8"), "application/json; charset=utf-8")

        def _read_json(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY_BYTES:
                raise ValueError("Missing or oversized request body.")
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"Invalid JSON body: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            return payload

        # ── routes ───────────────────────────────────────────────────────────
        def do_GET(self) -> None:  # noqa: N802
            route = urlparse(self.path).path
            if route in ("/", "/index.html"):
                self._send(200, INDEX_PATH.read_bytes(), "text/html; charset=utf-8")
            elif route == "/api/session":
                self._send_json(
                    200,
                    build_session(csv_path, icons_path, industries_path, lists_dir, config_path),
                )
            else:
                self._send_json(404, {"error": "Not found"})

        def do_POST(self) -> None:  # noqa: N802
            route = urlparse(self.path).path
            try:
                if route == "/api/save":
                    self._send_json(200, save_list_payload(self._read_json(), lists_dir))
                elif route == "/api/activate":
                    stem = str(self._read_json().get("stem", "")).strip()
                    self._send_json(200, activate_list(stem, config_path, lists_dir))
                elif route == "/api/quit":
                    self._send_json(200, {"ok": True})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                else:
                    self._send_json(404, {"error": "Not found"})
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
            except OSError as exc:
                logger.exception("Failed handling %s", route)
                self._send_json(500, {"error": str(exc)})

    return PickerHandler


def serve(
    csv_path: Path = REPO_ROOT / "companies.csv",
    lists_dir: Path = DEFAULT_LISTS_DIR,
    config_path: Path = DEFAULT_CONFIG_PATH,
    icons_path: Path = REPO_ROOT / "icons.json",
    industries_path: Path = REPO_ROOT / "industries.csv",
    port: int = 8777,
    open_browser: bool = True,
) -> None:
    """Serve the picker UI until the browser tab says it is done, or Ctrl-C.

    Args:
        csv_path: Path to ``companies.csv``.
        lists_dir: Directory to read and write lists in.
        config_path: Path to ``config.json``.
        icons_path: Path to ``icons.json``.
        industries_path: Path to ``industries.csv``.
        port: Port to bind on localhost; ``0`` picks a free one.
        open_browser: Whether to open the UI automatically.
    """
    lists_dir.mkdir(parents=True, exist_ok=True)
    handler = make_handler(csv_path, icons_path, industries_path, lists_dir, config_path)

    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError as exc:
        if exc.errno != errno.EADDRINUSE:
            raise
        # Usually another picker is already open. Take a free port instead of
        # dying, so the second window still works.
        print(f"⚠️  Port {port} is already in use — is a picker already running?")
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)

    with httpd:
        url = f"http://127.0.0.1:{httpd.server_address[1]}/"
        total = len(load_companies(csv_path))
        print(f"🃏 phlux list picker — {total} companies from {_display_path(csv_path)}")
        print(f"   Open {url}  (Ctrl-C to stop)")
        if open_browser:
            threading.Timer(0.4, webbrowser.open, args=(url,)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Picker stopped.")
