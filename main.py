import os
import time
import json
import pandas as pd
import requests
import smtplib
from email.message import EmailMessage
from concurrent.futures import ProcessPoolExecutor, as_completed

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from tenacity import retry, wait_fixed, stop_after_attempt
from webdriver_manager.chrome import ChromeDriverManager

from apply import AutoApplyBot

GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
CHROME_DRIVER_PATH = ChromeDriverManager().install()

# Used for dynamically loaded jobs that require user interaction
CLICKABLE = {
    "Robinhood": {"text": "EARLY TALENT"},
    "DE Shaws": {"selector": "div.more-jobs.movable-underline"}
}
# Used for job pages that dont have a filter option
NEEDS_FILTER = {
    "X": "intern",
    "Verkada": "intern",
    "Neuralink": "intern"
}

@retry(wait=wait_fixed(5), stop=stop_after_attempt(5))
def get_jobs_headless(args):
    name, url, selector = args
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(service=Service(CHROME_DRIVER_PATH), options=options)
    try:
        driver.get(url)
        if needClick := CLICKABLE.get(name, False):
            try:
                print(f"🖱️ Attempting to click for {name}...")

                if "selector" in needClick:
                    print(f"🔍 Looking for element with selector: {needClick['selector']}")
                    click_target = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, needClick["selector"]))
                    )
                elif "text" in needClick:
                    print(f"🔍 Looking for element with text: {needClick['text']}")
                    try:
                        click_target = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable(
                                (By.XPATH, f"//*[normalize-space(text())='{needClick['text']}']")
                            )
                        )
                    except TimeoutException:
                        print("⚠️ Exact match failed, trying partial text match...")
                        click_target = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable(
                                (By.XPATH, f"//*[contains(normalize-space(), '{needClick['text']}')]")
                            )
                        )
                else:
                    raise ValueError(f"No valid click strategy defined for {name}")

                print("✅ Element found. Scrolling into view...")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", click_target)
                time.sleep(0.5)

                print("👆 Clicking element...")
                driver.execute_script("arguments[0].click();", click_target)
                time.sleep(2)
                print("✅ Click successful.")
            except Exception as e:
                print(f"❌ Failed to click for {name}: {e}")

        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
        )
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        for _ in range(10):
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                break
            time.sleep(1)
        jobs = [el.text.strip() for el in elements if el.text.strip()]
        if job_filter := NEEDS_FILTER.get(name, False):
            jobs = [job for job in jobs if job_filter.lower() in job.lower()]
        return jobs
    except TimeoutException:
        print(f"❌ {name} - Timeout: Could not find elements for selector '{selector}'")
        return []
    except Exception as e:
        print(f"❌ {name} - Error scraping: {e}")
        return []
    finally:
        driver.quit()

def load_company_data():
    df = pd.read_csv("companies.csv", keep_default_na=False)
    df["Link"] = df["Link"].str.strip('"\'')
    return list(zip(df["Name"], df["Link"], df["ClassName"]))


def update_storage(storage_path="storage.json"):
    if os.path.exists(storage_path):
        with open(storage_path, "r") as f:
            data = json.load(f)
    else:
        data = {"companies": {}}

    new_jobs_message = {"companies": {}}
    companies = load_company_data()

    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(get_jobs_headless, (name, link, selector)): (name, link)
            for name, link, selector in companies
        }

        for future in as_completed(futures):
            name, link = futures[future]
            jobs = future.result()
            existing = data["companies"].get(name, [])
            new_jobs = []
            for job in jobs:
                job = job.replace('\n', ' - ')
                if job not in existing:
                    new_jobs.append(job)

            if name in data["companies"]:   
                data["companies"][name].extend(new_jobs)
            else:
                data["companies"][name] = jobs

            if new_jobs:
                new_jobs_message["companies"][name] = {
                    "jobs": new_jobs,
                    "link": link
                }
                print(f"✅ New jobs at {name}!")
            else:
                print(f"💢 No new jobs at {name}.")

    with open(storage_path, "w") as f:
        json.dump(data, f, indent=2)

    return new_jobs_message

def format_message_html(message):
    lines = ["<h2>phi's little minion has found new internships</h2><br>"]
    try:
        response = requests.get("https://random-d.uk/api/random")
        if response.status_code == 200:
            duck_url = response.json().get("url")
            lines.append(f'<img src="{duck_url}" alt="Random Duck" width="300"><br>')
        
        response = requests.get("https://api.animechan.io/v1/quotes/random")
        if response.status_code == 200:
            data = response.json().get("data")
            quote = data.get("content", "")
            character = data.get("character", "Someone").get("name")
            anime = data.get("anime", "a show").get("name")
            lines.append(f'<p>As <strong>{character}</strong> from <em>{anime}</em> once said:<br>“{quote}”</p><br>')
        else:
            lines.append("<p><em>Couldn't fetch a quote this time</em></p><br>")
    except Exception as e:
        lines.append(f"<p><em>Error fetching content: {e}</em></p><br>")

    for company, info in message["companies"].items():
        lines.append(f"<h3>🔹 {company}</h3>")
        lines.append("<ul>")
        for job in info["jobs"]:
            lines.append(f"<li>{job}</li>")
        lines.append("</ul>")
        lines.append(f'<p>🔗 <a href="{info["link"]}">Apply Here</a></p><br>')

    lines.append('<a href="https://github.com/Ph1so/phlux2.0">All Jobs List</a>')

    return "\n".join(lines)

def send_email(message):
    msg = EmailMessage()
    msg['Subject'] = "🚀 New Internship Alerts!"
    msg['From'] = 'phiwe3296@gmail.com'
    msg['To'] = 'phiwe3296@gmail.com'
    msg['Cc'] = 'Nicolezcui@gmail.com, pham0579@umn.edu, ronak@ronakpjain.com'
    html_content = format_message_html(message)
    msg.set_content("This email contains HTML. Please view it in an HTML-compatible client.")
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login('phiwe3296@gmail.com', GMAIL_APP_PASSWORD)
        smtp.send_message(msg)

def main():
    new_jobs = update_storage()
    if new_jobs["companies"]:
        send_email(new_jobs)

if __name__ == "__main__":
    main()