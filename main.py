import os
import time
import json
import pandas as pd
import requests
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
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

GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]

# Install ChromeDriver once globally
CHROME_DRIVER_PATH = ChromeDriverManager().install()

@retry(wait=wait_fixed(5), stop=stop_after_attempt(5))
def get_jobs_headless(args):
    url, selector, needClick = args
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
        if needClick and needClick.strip() != "None":
            try:
                print(f"🖱️ Clicking '{needClick.strip()}' to reveal jobs...")
                click_target = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, f"//p[text()='{needClick.strip()}']"))
                )
                click_target.click()
                time.sleep(2)
            except Exception as e:
                print(f"⚠️ Failed to click '{needClick}': {e}")
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
        return [el.text.strip() for el in elements if el.text.strip()]
    except TimeoutException:
        print(f"❌ Timeout: Could not find elements for selector '{selector}' at {url}")
        return []
    except Exception as e:
        print(f"❌ Error scraping {url}: {e}")
        return []
    finally:
        driver.quit()

def load_company_data():
    df = pd.read_csv("companies.csv", keep_default_na=False)
    df["Link"] = df["Link"].str.strip('"\'')
    return list(zip(df["Name"], df["Link"], df["ClassName"], df["needClick"]))


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
            executor.submit(get_jobs_headless, (link, selector, needClick)): (name, link)
            for name, link, selector, needClick in companies
        }

        for future in as_completed(futures):
            name, link = futures[future]
            jobs = future.result()
            existing = data["companies"].get(name, [])
            new_jobs = [job.replace('\n', ' - ') for job in jobs if job not in existing]

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
            data = response.json()
            quote = data.get("quote", "")
            character = data.get("character", "Someone")
            anime = data.get("anime", "an anime")
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
    # url = "https://www.spacex.com/careers/jobs/?type=intern"
    # selector = "table tbody tr td a"
    # needClick = "None"
    # print(get_jobs_headless((url,selector, needClick)))

if __name__ == "__main__":
    main()
