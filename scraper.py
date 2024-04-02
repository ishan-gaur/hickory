import os
import code
import time
import json
import pprint
from pathlib import Path
from playwright.sync_api import sync_playwright # testing framework for interaction with a web-browser
from bs4 import BeautifulSoup # for html parsing
from jsonpath_ng import parse
from dotenv import load_dotenv
load_dotenv()


class FacebookScraper:
    
    def __init__(self, playwright_context):
        self.playwright_context = playwright_context
        self.browser = self.playwright_context.chromium.launch(headless=False)
        self.page = self.browser.new_page()
    

    def login(self):
        initial_url = "https://www.facebook.com/login/device-based/regular/login/"
        self.page.goto(initial_url)
        time.sleep(2)

        try: 
            email_input = self.page.wait_for_selector('input[name="email"]').fill(os.getenv("USERNAME"))
            password_input = self.page.wait_for_selector('input[name="pass"]').fill(os.getenv("PASSWORD"))
            time.sleep(2)
            login_button = self.page.wait_for_selector('button[name="login"]').click()
            time.sleep(2)

            # TODO: Handle MFA Forwarding for the user
            # time.sleep(20)
            # if page.get_by_text("The email or mobile number you entered isn't connected to an account.").is_visible():
            #     raise ValueError("Email or password is incorrect!")

        except TimeoutError:
            print("One of the email, password, or login-button elements did not appear within 30 seconds")
            if input("Try again?").lower() in ["y", "yes"]:
                self.handle_user_login()

        time.sleep(2)
        page.goto(marketplace_url)
        html = page.content()

        soup = BeautifulSoup(html, 'html.parser')
        item_result_tag = soup.find('script', string=lambda t: not t is None and 'marketplace_search' in t)
        item_result_json = json.loads(item_result_tag.string)  # or any required manipulation to isolate the JSON

        MARKETPLACE_LISTINGS_QUERY = "$..marketplace_search.*"
        jsonpath_expr = parse(MARKETPLACE_LISTINGS_QUERY)
        matches = [match.value for match in jsonpath_expr.find(item_result_json)]
        if len(matches) == 0:
            raise ValueError(f"The jsonpath_ng query for the listings ({MARKETPLACE_LISTINGS_QUERY}) was not found.")
        elif len(matches) > 1:
            raise ValueError(f"The jsonpath_ng query for listings ({MARKETPLACE_LISTINGS_QUERY}) returned multiple results.")

        listings_json = matches[0]
        listings = []
        for edge in listings_json['edges']:
            listing = edge['node']['listing']
            extracted = {
                'name': listing.get('marketplace_listing_title', 'N/A'),
                'price': listing['listing_price'].get('formatted_amount', 'N/A'),
                'location': listing['location']['reverse_geocode'].get('city', 'N/A'),
                'image_url': listing['primary_listing_photo']['image'].get('uri', 'N/A'),
                'delivery_options': listing.get('delivery_types', []),
                'seller': listing['marketplace_listing_seller'].get('name', 'N/A'),
                'item_id': listing['id']
            }
            listings.append(extracted)

        return {"listings": listings}

if __name__ == "__main__":
    pp = pprint.PrettyPrinter(indent=4)
    with sync_playwright() as p:
        scraper = FacebookScraper(p)
        scraper.login()
        output = None
        interpreter = code.InteractiveInterpreter(locals={
            'scraper': scraper,
            'pp': pp
        })
        cmd = input("> ")
        while cmd != "exit()":
            interpreter.runsource(f"pp.pprint(scraper.{cmd})")
            cmd = input("> ")