from phlux.scraping import get_jobs_headless
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webelement import WebElement
from tenacity import retry, wait_fixed, stop_after_attempt
from utils import get_driver
import time
name="Duolingo"
url="https://careers.duolingo.com/?type=Intern#careers->https://careers.duolingo.com/?type=Thrive+Program#careers->https://careers.duolingo.com/?type=New+Grad#careers"
instructions="CSS:a.A9xxT"
headless=False
# name="Scale AI"
# url="https://scale.com/careers#open-roles"
# instructions="CLICK:'All Departments'->CLICK:'University'"
# headless=False
driver = get_driver(headless=headless)

jobs = get_jobs_headless(name=name, urls=url, instructions=instructions, headless=headless)
print(f"jobs found: {len(jobs)}\njobs: {jobs}")
# try:
#     driver.get(url)
#     industry_opt = WebDriverWait(driver, 5).until(
#         EC.element_to_be_clickable((By.XPATH, "//*[normalize-space(text())='All Departments']"))
#     )
#     driver.execute_script("arguments[0].click();", industry_opt)
#     print(f"industury: {industry_opt}")
#     industry_opt = WebDriverWait(driver, 5).until(
#         EC.element_to_be_clickable((By.XPATH, "//*[normalize-space(text())='University']"))
#     )
#     driver.execute_script("arguments[0].click();", industry_opt)
#     print(f"industury: {industry_opt}")
# except TimeoutException:
#     print(f"❌ {name} - Timeout")
# finally:
#     print("Done")
#     time.sleep(60)
#     driver.quit() 

# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.common.exceptions import TimeoutException
# import time

# name = "Duolingo"
# url = "https://careers.duolingo.com/#careers"
# driver.get(url)

# try:
#     time.sleep(3)  # Let JS/animations load

#     dropdown_btn = WebDriverWait(driver, 15).until(
#         EC.presence_of_element_located((By.CSS_SELECTOR, ".Ku9oD.CCR1m"))
#     )

#     driver.execute_script("arguments[0].click();", dropdown_btn)
    
#     industry_opt = WebDriverWait(driver, 10).until(
#         EC.element_to_be_clickable((By.XPATH, "//*[normalize-space(text())='Industry']"))
#     )
#     driver.execute_script("arguments[0].click();", industry_opt)
#     print(f"✅ Clicked 'Industry' option: {industry_opt.text}")

# except TimeoutException:
#     print(f"❌ {name} - Timeout")

#     # Dump page to debug
#     with open("debug.html", "w", encoding="utf-8") as f:
#         f.write(driver.page_source)

# finally:
#     print("Done")
#     time.sleep(60)
#     driver.quit()

# print(get_jobs_headless(name = "Optiver" , url = "https://optiver.com/working-at-optiver/career-opportunities/page/2/?search=internship&_gl=1*rb345g*_gcl_au*Mjk2MDM5OTE1LjE3NDg5MTM5ODQ.&numberposts=10&level=internship&paged=1" , instructions="CLICK:'Load more'->CSS:h5", headless=False))