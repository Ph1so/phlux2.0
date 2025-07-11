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
url = "https://jobs.comcast.com/search-jobs?acm=ALL&alrpm=ALL&ascf=[%7B%22key%22:%22custom_fields.InternRotational%22,%22value%22:%22Intern%22%7D]"
instructions = "CSS:a h2"

headless=True

jobs = get_jobs_headless(name=name, urls=url, instructions=instructions, headless=headless, test = True)
print(f"jobs found: {len(jobs)}\njobs: {jobs}")