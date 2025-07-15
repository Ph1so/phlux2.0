import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
from phlux.scraping import get_jobs_headless
from phlux.utils import get_driver
from phlux.config import load_config
import logging
logging.getLogger().setLevel(logging.ERROR)

CONFIG = load_config()
driver = get_driver(headless=False)

def get_tag_chain_selector(el):
    path = []
    current = el
    try:
        while current.tag_name.lower() != "html":
            tag = current.tag_name
            class_attr = current.get_attribute("class")
            if class_attr:
                class_selector = "." + ".".join(class_attr.strip().split())
                path.insert(0, f"{tag}{class_selector}")
                break 
            else:
                path.insert(0, tag)
            current = current.find_element(By.XPATH, "..")
    except:
        return None
    return " > ".join(path)

def get_specific_css_selector(driver, job_title, name, link):
    elements = driver.find_elements(By.XPATH, f"//*[normalize-space(text())='{job_title}']")
    
    if not elements:
        print("❌ No elements found with that exact text.")
        return None

    for el in elements:
        candidate_selectors = []

        # Strategy 1: Go up 4 levels to get tag + class combo
        parent = el
        for _ in range(4):
            parent = parent.find_element(By.XPATH, "..")
            class_attr = parent.get_attribute("class")
            if class_attr:
                class_selector = "." + ".".join(class_attr.strip().split())
                candidate_selectors.append(f"{parent.tag_name}{class_selector}")

        # Strategy 2: Tag chain path like div > div > a > span
        chain_selector = get_tag_chain_selector(el)
        if chain_selector:
            candidate_selectors.append(chain_selector)

        for selector in candidate_selectors:
            try:
                jobs = get_jobs_headless(name, link, selector, CONFIG)
                print(f"\n🔍 Candidate Selector: `{selector}`")
                print(f"⚙️ Total elements matched: {len(jobs)}")
                for job in jobs:
                    print(f"  • {job.strip().splitlines()[0] if job.strip() else 'EMPTY'}")
                confirm = input("Use this selector? (y/n): ").strip().lower()
                if confirm == 'y':
                    return selector
            except Exception as e:
                print(f"⚠️ Failed to use selector `{selector}`: {e}")

    print("⚠️ Could not find an acceptable selector automatically.")
    return None

def main():
    name = input("Company name: ").strip()
    link = input("Company careers page URL: ").strip()
    job_title = input("Example job title (exact match): ").strip()

    driver.get(link)
    time.sleep(2)

    css_selector = get_specific_css_selector(driver, job_title, name, link)
    confirm = "y"
    while not css_selector or confirm == "n":
        css_selector = input("Enter a CSS selector manually: ").strip()
        jobs = get_jobs_headless(name, link, css_selector, CONFIG)
        print(f"\n🔍 Candidate Selector: `{css_selector}`")
        print(f"⚙️ Total elements matched: {len(jobs)}")
        for job in jobs:
            print(f"  • {job.strip().splitlines()[0] if job.strip() else 'EMPTY'}")
        confirm = input("Use this selector? (y/n): ").strip().lower()

    with open("companies.csv", mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([name, link, css_selector])
    
    print(f"✅ Saved: {name}, {link}, {css_selector}")

if __name__ == "__main__":
    main()
