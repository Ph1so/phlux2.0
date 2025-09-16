import json, time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from utils import get_driver  # your helper

def update_yc_jobs(storage_file="storage_yc.json"):
    driver = get_driver(headless=True)
    driver.get("https://www.ycombinator.com/jobs/role/software-engineer")

    wait = WebDriverWait(driver, 15)

    # Load or init storage
    try:
        with open(storage_file, "r") as f:
            storage = json.load(f)
    except FileNotFoundError:
        storage = {}

    # Wait for at least one card to exist
    # This container is the parent that holds name/title within each listing card
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".flex.flex-col.items-start.gap-y-1")))

    # Optionally, scroll a bit in case the list lazy-loads
    last_h = 0
    for _ in range(4):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.0)
        h = driver.execute_script("return document.body.scrollHeight")
        if h == last_h:
            break
        last_h = h

    cards = driver.find_elements(By.CSS_SELECTOR, ".flex.flex-col.items-start.gap-y-1")

    added, updated = 0, 0

    for card in cards:
        # Company name
        try:
            company = card.find_element(By.CSS_SELECTOR, "span.block").text.strip()
        except NoSuchElementException:
            continue  # skip malformed card

        # Job title
        try:
            title_el = card.find_element(By.CSS_SELECTOR, ".text-sm.font-semibold.leading-tight.text-linkColor")
            job_title = title_el.text.strip()
        except NoSuchElementException:
            job_title = ""

        # Link (prefer anchor under the title)
        link = ""
        try:
            link_el = title_el.find_element(By.TAG_NAME, "a")
            link = link_el.get_attribute("href") or ""
        except Exception:
            try:
                # Fallback: any anchor under the card
                link_el = card.find_element(By.CSS_SELECTOR, "a[href]")
                link = link_el.get_attribute("href") or ""
            except NoSuchElementException:
                pass

        # Logo (search in parent row, not just card)
        logo = ""
        try:
            row = card.find_element(By.XPATH, "./ancestor::li[1]")
            logo_el = row.find_element(By.CSS_SELECTOR, "img.rounded-full")
            logo = logo_el.get_attribute("src") or ""
        except NoSuchElementException:
            logo = ""



        # Merge into storage
        if company not in storage:
            storage[company] = {
                "logo": logo,
                "link": link,
                "job_title": []
            }
            added += 1
        else:
            # keep existing logo/link if new ones are blank; otherwise update
            if logo:
                storage[company]["logo"] = logo
            if link:
                storage[company]["link"] = link

        if job_title and job_title not in storage[company]["job_title"]:
            storage[company]["job_title"].append(job_title)
            updated += 1

    # Save
    with open(storage_file, "w") as f:
        json.dump(storage, f, indent=4)

    print(f"✅ Parsed {len(cards)} cards | New companies: {added} | Titles added: {updated}")
    driver.quit()

update_yc_jobs()