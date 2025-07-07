from phlux.scraping import get_jobs_headless
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webelement import WebElement
from tenacity import retry, wait_fixed, stop_after_attempt
from utils import get_driver
import time
# f"//*[contains(normalize-space(), '{xpath_text}')]"

name = "Amentum"
url = "https://www.amentumcareers.com/jobs/search?page=1&country_codes%5B%5D=US&query=%22Intern%22"
instructions = "CLICK:.btn.btn-success.consent-agree->CSS:td.job-search-results-title"


headless=False
driver = get_driver(headless=headless)

jobs = get_jobs_headless(name=name, urls=url, instructions=instructions, headless=headless, test = True)
print(f"jobs found: {len(jobs)}\njobs: {jobs}")
# driver.get(url)
# try:
#     time.sleep(3)

#     try:
#         cookie_btn = WebDriverWait(driver, 10).until(
#             EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept Cookies')]"))
#         )
#         driver.execute_script("arguments[0].click();", cookie_btn)
#         print("✅ Cookies accepted")
#     except:
#         print("⚠️ No cookies prompt")

#     # Simulate pointer events for dropdown
#     driver.execute_script("""
#     const btn = [...document.querySelectorAll("button")].find(b => b.textContent.includes("All Departments"));
#     if (btn) {
#         btn.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true }));
#         btn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
#         btn.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
#         btn.dispatchEvent(new MouseEvent('click', { bubbles: true }));
#     }
#     """)
#     print("✅ Simulated pointer events on 'All Departments'")

#     # Wait for the dropdown menu to appear and click 'University'
#     try:
#         university_opt = WebDriverWait(driver, 10).until(
#             EC.element_to_be_clickable((By.XPATH, "//div[@role='menu']//div[text()='University']"))
#         )
#         driver.execute_script("arguments[0].click();", university_opt)
#         print("✅ Clicked 'University'")
#     except:
#         print("❌ Couldn't find 'University' option")
#     time.sleep(2)
#     job_title_el = driver.find_elements(By.CSS_SELECTOR, "a[href*='/careers/'] > p.p-6")
#     print(job_title_el.text)
# except TimeoutException:
#     print(f"❌ {name} - Timeout")
# finally:
#     print("Done")
#     time.sleep(60)
#     driver.quit() 