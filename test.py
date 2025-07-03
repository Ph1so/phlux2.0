from phlux.scraping import get_jobs_headless
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webelement import WebElement
from tenacity import retry, wait_fixed, stop_after_attempt
from utils import get_driver
import time
# name="Duolingo"
# url="https://careers.duolingo.com/#careers"
# instructions="CLICK:.Ku9oD.CCR1m->CLICK:'Industry'"
# headless=False
# name="Scale AI"
# url="https://scale.com/careers#open-roles"
# instructions="CLICK:'All Departments'->CLICK:'University'"
# headless=False
# driver = get_driver(headless=headless)

# name="JP Morgan Chase"
# url="https://careers.jpmorgan.com/global/en/students/programs/software-engineer-summer->https://careers.jpmorgan.com/global/en/students/programs/data-analytics-opportunities#careers-section7->https://careers.jpmorgan.com/global/en/students/programs/tfsg-hackathons->https://careers.jpmorgan.com/global/en/students/programs/quant-fin-programs->https://careers.jpmorgan.com/global/en/students/programs/design-dev-summer->https://careers.jpmorgan.com/global/en/students/programs/et-experience"
# instructions="CLICK:'Apply now'->CSS:.program-title"
headless=False
driver = get_driver(headless=headless)
driver.get("https://careers.sig.com/global-susquehanna-jobs")
try:
    element = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.XPATH,
    "//a[.//div[contains(@class, 'job-title')]/span[normalize-space() = 'Equity Analyst Internship: Summer 2026']]"))
    )
    print("✅ Found element")
    print(driver.execute_script("return arguments[0].outerHTML;", element))
except TimeoutException:
    print("❌ Element not found after waiting")
# Get specific attributes
print("Tag name:", element.tag_name)
print("Text:", element.text)
print("Job SeqNo:", element.get_attribute("data-ph-at-job-seqno-text"))

# Get all attributes using JavaScript
attrs = driver.execute_script("""
    var items = {}; 
    for (index = 0; index < arguments[0].attributes.length; ++index) {
        items[arguments[0].attributes[index].name] = arguments[0].attributes[index].value
    }; 
    return items;
""", element)

print("All attributes:")
for k, v in attrs.items():
    print(f"  {k} = {v}")

# Optional: get inner HTML
inner_html = driver.execute_script("return arguments[0].innerHTML;", element)
print("Inner HTML:", inner_html)

# Optional: outer HTML
outer_html = driver.execute_script("return arguments[0].outerHTML;", element)
print("Outer HTML:", outer_html)

# Navigate to apply page
job_seqno = attrs.get("data-ph-at-job-seqno-text")
if job_seqno:
    driver.get(f"https://careers.sig.com/apply?jobSeqNo={job_seqno}")

# print(get_jobs_headless(name=name, urls=url, instructions=instructions, headless=headless))
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

# try:
#     driver.get(url)
#     dropdown_btn = driver.find_element(By.CSS_SELECTOR, ".Ku9oD.CCR1m")
#     dropdown_btn.click()
#     industry_opt = WebDriverWait(driver, 5).until(
#         EC.element_to_be_clickable((By.XPATH, "//*[normalize-space(text())='Industry']"))
#     )
#     driver.execute_script("arguments[0].click();", industry_opt)
#     print(f"industury: {industry_opt}")
# except TimeoutException:
#     print(f"❌ {name} - Timeout")
# finally:
#     print("Done")
#     time.sleep(60)
#     driver.quit() 

# print(get_jobs_headless(name = "Optiver" , url = "https://optiver.com/working-at-optiver/career-opportunities/page/2/?search=internship&_gl=1*rb345g*_gcl_au*Mjk2MDM5OTE1LjE3NDg5MTM5ODQ.&numberposts=10&level=internship&paged=1" , instructions="CLICK:'Load more'->CSS:h5", headless=False))