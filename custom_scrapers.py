from abc import ABC, abstractmethod
from typing import Tuple, List
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from utils import get_driver

class CompanyScraper(ABC):
    @abstractmethod
    def get_jobs(self) -> Tuple[str, List[str], str]:
        pass

    @property
    def name(self):
        return self._name

    @property
    def base_link(self):
        return self._base_link

class JPMorganScraper(CompanyScraper):
    def __init__(self):
        self._name = "JP Morgan Chase"
        self._base_link = "https://careers.jpmorgan.com/global/en/students/programs"
        self.job_links = [
            f"{self._base_link}/cadp-summer-analyst",
            f"{self._base_link}/software-engineer-summer",
            f"{self._base_link}/data-analytics-opportunities",
        ]
        self.selector = "programs-apply-now-btn"

    def get_jobs(self) -> Tuple[str, List[str], str]:
        driver = get_driver()
        prefix = self._base_link + "/"
        jobs = []

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