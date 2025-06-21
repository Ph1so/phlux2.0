from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import time
from utils import get_driver

class AutoApplyBot:
    def __init__(self, job_list: list, personal_info: dict):
        """
        jobs = [
            {
                "company": "AMD",
                "url": "...",
                "titles": ["Software Test Engineering Intern/Co-Op (Undergraduate | Fall 2025 | Hybrid)"]
            }
        ]
        """
        self.job_list = job_list
        self.personal_info = personal_info

    def apply_to_amd(self, job: dict, personal_info: dict):
        company = job["company"]
        url = job["url"]
        titles = job["titles"]
        
        driver = get_driver()
        
        for title in titles:
            driver.get(url)
            time.sleep(3)

            self.element_click("ID", "onetrust-accept-btn-handler", driver, title)
            self.element_click("XPATH", f"//a[contains(@class, 'job-title-link') and span[normalize-space(text())='{title}']]", driver, title)
            self.element_click("XPATH", f"//a[contains(@class, 'apply') and contains(@class, '__button') and contains(@class, 'btn-primary') and contains(@class, 'primary-bg-color')]", driver, "Apply")

            # Give time for iframe to load
            WebDriverWait(driver, 10).until(
                EC.frame_to_be_available_and_switch_to_it((By.ID, "icims_content_iframe"))
            )
            print("🔄 Switched to iframe.")

            # Optional: wait for the form to render fully
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "enterEmailForm"))
            )

            # Optional: take screenshot for debugging
            driver.save_screenshot("debug_before_typing.png")

            # Type into email field inside iframe
            self.element_type("ID", "email", driver, personal_info["email"], label="Email Field")

            time.sleep(5)
        
        driver.quit()


    def run(self):
        for job in self.job_list:
            if job["company"] == "AMD" and self.is_eligible(job):
                self.apply_to_amd(job, self.personal_info)

    def is_eligible(self, job):
        return True  # Placeholder for future filtering logic
    
    def element_click(self, by, selector, driver, title):
        time.sleep(1)
        try:
            if by == "XPATH":
                element = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
            elif by == "ID":
                element = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, selector))
                )
            else:
                print(f"❌ Unsupported selector type: {by}")
                return

            # Scroll into view and click
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.5)
            element.click()
            print(f"✅ Clicked element ({by}): {title}")
        except Exception as e:
            print(f"❌ Failed to click element ({by}) for {title}:", e)

    def element_type(self, by, selector, driver, text, label=""):
        try:
            if by == "XPATH":
                locator = (By.XPATH, selector)
            elif by == "ID":
                locator = (By.ID, selector)
            elif by == "CSS":
                locator = (By.CSS_SELECTOR, selector)
            else:
                print(f"❌ Unsupported selector type: {by}")
                return

            # Get the actual element once
            input_elem = WebDriverWait(driver, 15).until(EC.element_to_be_clickable(locator))

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", input_elem)
            time.sleep(0.5)
            input_elem.clear()
            input_elem.send_keys(text)
            print(f"✅ Typed into {label or selector}")

        except Exception as e:
            inputs = driver.find_elements(By.TAG_NAME, "input")
            print(f"🔍 Found {len(inputs)} input elements:")
            for i, inp in enumerate(inputs):
                print(f"  [{i}] id='{inp.get_attribute('id')}', name='{inp.get_attribute('name')}', type='{inp.get_attribute('type')}'")
            
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            print(f"🖼️ Found {len(iframes)} iframe(s):")
            for i, frame in enumerate(iframes):
                print(f"  [{i}] name='{frame.get_attribute('name')}', id='{frame.get_attribute('id')}'")


            print(f"❌ Failed to type into {label or selector}:", e)





