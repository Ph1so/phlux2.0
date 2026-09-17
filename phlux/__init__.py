"""Core package for phlux scraping utilities.

The scraping stack (Selenium, undetected-chromedriver, webdriver-manager) is
imported lazily, so tools that only read ``companies.csv`` and ``lists/`` —
notably ``python -m phlux.picker`` — run without those packages installed.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .config import load_company_list_setting, load_config
from .lists import (
    CompanyList,
    available_lists,
    load_companies,
    load_company_list,
    select_companies,
)
from .models import Company, ScrapeResult

if TYPE_CHECKING:  # Keeps type checkers and editors aware of the lazy names.
    from .scraping import ScrapeManager
    from .utils import get_driver

# Attribute name -> submodule it lives in, resolved on first access.
_LAZY = {"ScrapeManager": ".scraping", "get_driver": ".utils"}

__all__ = [
    "load_config",
    "load_company_list_setting",
    "CompanyList",
    "available_lists",
    "load_companies",
    "load_company_list",
    "select_companies",
    "Company",
    "ScrapeResult",
    "ScrapeManager",
    "get_driver",
]


def __getattr__(name: str):
    """Import the scraping stack only when one of its names is first used."""
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module
    return getattr(import_module(module, __name__), name)


def __dir__() -> list[str]:
    return sorted(__all__)
