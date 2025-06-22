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
        """
        Returns:
            - name: str
            - jobs: List[str]
            - link: str
        """
        pass
    
    @property
    def get_link(self):
        return self.base_link

class JPMorganScraper(CompanyScraper):
    def __init__(self):
        self.name = "JP Morgan Chase"
        self.base_link = "https://careers.jpmorgan.com/global/en/students/programs"
        self.job_links = [
            f"{self.base_link}/cadp-summer-analyst",
            f"{self.base_link}/software-engineer-summer",
            f"{self.base_link}/data-analytics-opportunities",
        ]
        self.selector = "programs-apply-now-btn"

    def get_jobs(self) -> Tuple[str, List[str], str]:
        driver = get_driver()
        prefix = self.base_link + "/"
        jobs = []

        try:
            for link in self.job_links:
                try:
                    driver.get(link)
                    elem = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, self.selector))
                    )
                    if elem.is_displayed():
                        jobs.append(link[len(prefix):].replace("-", " "))
                except TimeoutException:
                    print(f"❌ {self.name} - Timeout at {link}")
        finally:
            driver.quit()

        return self.name, jobs, self.base_link
