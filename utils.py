import requests
import json
from typing import List
import os

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from phlux.models import Company

import undetected_chromedriver as uc

CHROME_DRIVER_PATH = ChromeDriverManager().install()

def get_driver(headless=True, use_undetected=False):
    if use_undetected:
        options = uc.ChromeOptions()
        if headless:
            options.headless = True
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920x1080")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
        )
        return uc.Chrome(options=options)

    else:
        options = Options()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920x1080")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
        )
        return webdriver.Chrome(service=Service(CHROME_DRIVER_PATH), options=options)

def update_icons(companies: List[Company]):
    ICONS_ID = os.environ["ICONS_ID"]
    # ICONS_API = os.environ["ICONS_API"]
    try:
        with open("icons.json", "r", encoding="utf-8") as f:
            icons = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        icons = {}

    for company in companies:
        name = company.name
        try:
            if name not in icons:
                response = requests.get(f"https://api.brandfetch.io/v2/search/{name}?c={ICONS_ID}")
                response.raise_for_status()
                domain = response.json()[0]["domain"]
                icons[name] = f"https://cdn.brandfetch.io/{domain}/w/400/h/400?c={ICONS_ID}"

                # brandID = response.json()[0]["brandId"]
                # headers = {
                #     "Authorization": f"Bearer {ICONS_API}"
                # }
                # response = requests.get(f"https://api.brandfetch.io/v2/brands/{brandID}", headers=headers)
                # response.raise_for_status()
                # response: List[dict] = response.json()["logos"]
                # for logo in response:
                #     if logo["type"] == "symbol" or logo["type"] == "logo":
                #         for format in logo["formats"]:
                #             if format["format"] == "svg":
                #                 readme = format["src"]
                #             elif format["format"] == "png":
                #                 email = format["src"]
                #         icons[name] = {"email": email, "readme": readme}
                #         if logo["type"] == "symbol":
                #             break

        except Exception as e:
            print(f"❌ Failed to get icon for {name}: {e}")

    with open("icons.json", "w", encoding="utf-8") as f:
        json.dump(icons, f, indent=2)