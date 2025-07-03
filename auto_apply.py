from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
import time
import sys
from phlux.utils import get_driver
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("AutoApplyBot")

class AutoApplyBot:
    def __init__(self, job_list: list = None, personal_info: dict = None):
        """
        jobs = [
            {
                "company": "AMD",
                "url": "...",
                "titles": ["Software Test Engineering Intern/Co-Op (Undergraduate | Fall 2025 | Hybrid)"]
            }
        ]
        """
        self.job_list = job_list if job_list is not None else []
        self.personal_info = personal_info if personal_info is not None else {}

    def apply_to_sus(self, url: str):
        log.info(f"Starting auto-apply for URL: {url}")

        ADDRESS = os.environ["ADDRESS"]
        CITY = os.environ["CITY"]
        ZIP = os.environ["ZIP"]
        STATE = os.environ["STATE"]

        driver = get_driver(headless=True)
        driver.get(url)
        log.info("Loaded application page.")

        time.sleep(2)
        file_input = driver.find_element(By.CSS_SELECTOR, "input.dz-hidden-input")
        resume_path = os.path.join(os.getcwd(), "public", "Resume___Phi_Nguyen.pdf")
        file_input.send_keys(resume_path)
        log.info(f"Uploaded resume: {resume_path}")

        WebDriverWait(driver, 5).until(EC.alert_is_present())
        alert = driver.switch_to.alert
        alert_text = alert.text
        alert.accept()
        log.info(f"Accepted alert: {alert_text}")

        def fill_input(id, value):
            input_elem = driver.find_element(By.ID, id)
            input_elem.clear()
            input_elem.send_keys(value)
            log.info(f"Filled {id} with '{value}'")

        fill_input("address", ADDRESS)
        fill_input("city", CITY)
        fill_input("zipCode", ZIP)

        def select_dropdown(id, value):
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, id)))
            select_elem = Select(driver.find_element(By.ID, id))
            select_elem.select_by_visible_text(value)
            log.info(f"Selected '{value}' from dropdown '{id}'")

        select_dropdown("country", "United States")
        select_dropdown("state", STATE)
        select_dropdown("source", "Online Search/Job Posting")
        select_dropdown("applicable", "Google")

        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "sbtButton"))).click()
        log.info("Clicked submit button.")
        driver.save_screenshot("screenshot.png")
        time.sleep(10)

        driver.quit()
        log.info("Application submitted and browser closed.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
        bot = AutoApplyBot()
        bot.apply_to_sus(url)
    else:
        print("❌ No URL provided. Usage: python auto_apply.py <application_url>")
