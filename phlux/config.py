"""Configuration loader for phlux."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Load JSON configuration from *path*."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

