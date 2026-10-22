"""Browser-free readers for job systems and company career sites.

Each module registers its fetchers with :func:`phlux.adapters.base.adapter`;
importing this package imports them all and exposes the registry as
:data:`ADAPTERS` (name → ``fetch(url) -> List[Posting]``).
"""
from __future__ import annotations

import importlib
import pkgutil

from .base import ADAPTERS

for _module in pkgutil.iter_modules(__path__):
    if _module.name != "base":
        importlib.import_module(f"{__name__}.{_module.name}")

__all__ = ["ADAPTERS"]
