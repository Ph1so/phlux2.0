"""Keep a small copy of each company's logo in ``logos/`` for the site to embed.

``icons.json`` holds logo URLs (Brandfetch, else Google's favicon service), but
the site can't point at them: Brandfetch only serves pages it recognizes, and
the claude.ai preview of the site blocks every outside image. So each logo is
downloaded once at :data:`SIZE` pixels (under a kilobyte as WebP) and embedded
in the page as a data URI.

``logos/sources.json`` records the URL each file came from, so a logo is
fetched again only when its ``icons.json`` entry changes, and the bot commits
``logos/`` only when a company is added or its icon is fixed.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path
from typing import Dict, Iterable, Optional

from phlux.adapters.base import get
from phlux.lists import REPO_ROOT, slugify

logger = logging.getLogger(__name__)

LOGO_DIR = REPO_ROOT / "logos"
SOURCES = "sources.json"
# Twice the largest size the page shows (32px), for sharp logos on dense screens.
SIZE = 64
MAX_BYTES = 100_000
EXTENSIONS = {
    "image/webp": "webp", "image/png": "png", "image/jpeg": "jpg", "image/gif": "gif",
    "image/svg+xml": "svg", "image/x-icon": "ico", "image/vnd.microsoft.icon": "ico",
}
TYPES = {ext: mime for mime, ext in EXTENSIONS.items()}


def icon_url(icons: Dict, name: str) -> str:
    """Return *name*'s logo URL from ``icons.json`` (whose values are a URL or per-use URLs)."""
    icon = icons.get(name, "")
    if isinstance(icon, dict):
        icon = icon.get("readme") or icon.get("email") or ""
    return icon


def sized(url: str, size: int = SIZE) -> str:
    """Ask the logo service for a *size*-pixel image instead of the large default."""
    url = re.sub(r"/w/\d+/h/\d+", f"/w/{size}/h/{size}", url)
    return re.sub(r"([?&]sz=)\d+", rf"\g<1>{size}", url)


def _load_sources(logo_dir: Path) -> Dict[str, str]:
    try:
        return json.loads((logo_dir / SOURCES).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _file(logo_dir: Path, slug: str) -> Optional[Path]:
    return next((p for p in sorted(logo_dir.glob(f"{slug}.*")) if p.name != SOURCES), None)


def fetch_missing(names: Iterable[str], icons: Dict, logo_dir: Path = LOGO_DIR) -> int:
    """Download the logos *names* lack, or whose ``icons.json`` URL changed.

    A logo that fails to download is skipped (the page shows initials) and
    tried again on the next run.

    Returns:
        How many logos were written.
    """
    logo_dir.mkdir(parents=True, exist_ok=True)
    sources = _load_sources(logo_dir)
    written = 0
    for name in names:
        url, slug = icon_url(icons, name), slugify(name)
        if not url or (sources.get(slug) == url and _file(logo_dir, slug)):
            continue
        try:
            response = get(sized(url), headers={"Accept": "image/avif,image/webp,image/png,image/*"})
        except Exception as error:  # noqa: BLE001 - one bad logo mustn't stop the rest
            logger.warning("No logo for %s: %s", name, error)
            continue
        mime = response.headers.get("content-type", "").split(";")[0].strip().lower()
        if mime not in EXTENSIONS or not response.content or len(response.content) > MAX_BYTES:
            logger.warning("No logo for %s: got %s, %d bytes", name, mime or "no type", len(response.content))
            continue
        old = _file(logo_dir, slug)
        if old:
            old.unlink()
        (logo_dir / f"{slug}.{EXTENSIONS[mime]}").write_bytes(response.content)
        sources[slug] = url
        written += 1
    (logo_dir / SOURCES).write_text(json.dumps(dict(sorted(sources.items())), indent=2) + "\n", encoding="utf-8")
    return written


def data_uri(name: str, logo_dir: Path = LOGO_DIR) -> str:
    """Return *name*'s cached logo as a ``data:`` URI, or ``""`` if there is none."""
    path = _file(logo_dir, slugify(name))
    if path is None or path.suffix[1:] not in TYPES:
        return ""
    return f"data:{TYPES[path.suffix[1:]]};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
