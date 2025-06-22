from __future__ import annotations

"""Custom scraper for JP Morgan."""
from abc import ABC, abstractmethod
from typing import List, Tuple

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

from ..utils import get_driver


class CompanyScraper(ABC):
    @abstractmethod
    def get_jobs(self) -> Tuple[str, List[str], str]:
        """Return the company name, job list, and link."""


class JPMorganScraper(CompanyScraper):
    def __init__(self) -> None:
        self._name = "JP Morgan Chase"
        self._base_link = "https://careers.jpmorgan.com/global/en/students/programs"
        self.job_links = [
            f"{self._base_link}/cadp-summer-analyst",
            f"{self._base_link}/software-engineer-summer",
            f"{self._base_link}/data-analytics-opportunities",
        ]
        self.selector = "programs-apply-now-btn"

    @property
    def name(self) -> str:
        return self._name

    @property
    def base_link(self) -> str:
        return self._base_link

    def get_jobs(self) -> Tuple[str, List[str], str]:
        jobs: List[str] = []
        prefix = self._base_link + "/"
        driver = get_driver()
        try:
            for link in self.job_links:
                try:
                    driver.get(link)
                    elem = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, self.selector))
                    )
                    if elem.is_displayed():
                        jobs.append(link[len(prefix):].replace("-", " ").title())
                except TimeoutException:
                    print(f"❌ {self._name} - Timeout at {link}")
        finally:
            driver.quit()
        return self._name, jobs, self._base_link

