from phlux.scraping import get_jobs_headless
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webelement import WebElement
from tenacity import retry, wait_fixed, stop_after_attempt
from utils import get_driver
import time
import json

import undetected_chromedriver as uc

name = "Tesla"
url = "https://www.tesla.com/careers/search/?type=intern&site=US&department=ai-robotics"
instructions = "UNDETECTED->CSS:.style_TitleLink__PepSM.tds-text--h4.tds-link.tds-link--secondary"

headless=False

jobs = get_jobs_headless(name=name, urls=url, instructions=instructions, headless=headless, test = True)
print(f"jobs found: {len(jobs)}\njobs: {jobs}")