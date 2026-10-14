"""Built-in custom scrapers."""
from .jpmorgan import JPMorganScraper, CompanyScraper
from .tesla import tesla_jobs

# Site-specific extractors for the ``API:<name>[:<arg>]`` action.
API_SCRAPERS = {"tesla": tesla_jobs}

__all__ = ["JPMorganScraper", "CompanyScraper", "API_SCRAPERS"]

