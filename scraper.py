import os
import code
import time
import json
import pprint
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright # testing framework for interaction with a web-browser
from bs4 import BeautifulSoup # for html parsing
from jsonpath_ng import parse
from dotenv import load_dotenv
load_dotenv()


class FacebookScraper:

    SLEEP_DURATION = 2
    USERNAME_ENV_VAR = "USERNAME"
    PASSWORD_ENV_VAR = "PASSWORD"

    INITIAL_URL = "https://www.facebook.com/login/device-based/regular/login/"
    EMAIL_SELECTOR = 'input[name="email"]'
    PASSWORD_SELECTOR = 'input[name="pass"]'
    LOGIN_BUTTON_SELECTOR = 'button[name="login"]'

    MARKETPLACE_URL_PREFIX = "https://www.facebook.com/marketplace"
    SEARCH_RESULT_JSON_ENTITY = 'marketplace_search'
    MARKETPLACE_LISTINGS_QUERY = "$..marketplace_search.*"

    LISTING_ID_QUERY = "base_marketplace_listing_title"
    PRODUCT_DETAILS_QUERY = "$..marketplace_product_details_page.*"
    
    def __init__(self, playwright_context):
        self.playwright_context = playwright_context
        self.browser = self.playwright_context.chromium.launch(headless=False)
        self.page = self.browser.new_page()
    

    def login(self):
        self.page.goto(self.INITIAL_URL)
        time.sleep(self.SLEEP_DURATION)

        try: 
            email_input = self.page.wait_for_selector(self.EMAIL_SELECTOR).fill(os.getenv(self.USERNAME_ENV_VAR))
            password_input = self.page.wait_for_selector(self.PASSWORD_SELECTOR).fill(os.getenv(self.PASSWORD_ENV_VAR))
            time.sleep(self.SLEEP_DURATION)
            login_button = self.page.wait_for_selector(self.LOGIN_BUTTON_SELECTOR).click()
            time.sleep(self.SLEEP_DURATION)

            # TODO: Handle MFA Forwarding for the user
            # time.sleep(20)
            # if page.get_by_text("The email or mobile number you entered isn't connected to an account.").is_visible():
            #     raise ValueError("Email or password is incorrect!")

        except TimeoutError:
            print("One of the email, password, or login-button elements did not appear within 30 seconds")
            if input("Try again?").lower() in ["y", "yes"]:
                self.handle_user_login()

    def search_marketplace(self, city: str, query: str, max_price: int = None):
        # TODO: check somehow if this is a valid city or send that as a separate error at request time
        city = city.lower().replace(' ', '')
        if max_price is None:
            marketplace_url = f'{self.MARKETPLACE_URL_PREFIX}/{city}/search/?query={query}'
        else:
            marketplace_url = f'{self.MARKETPLACE_URL_PREFIX}/{city}/search/?query={query}&maxPrice={max_price}'
        self.page.goto(marketplace_url)
        html = self.page.content()

        soup = BeautifulSoup(html, 'html.parser')
        item_result_tag = soup.find('script', string=lambda t: not t is None and self.SEARCH_RESULT_JSON_ENTITY in t)
        item_result_json = json.loads(item_result_tag.string)  # or any required manipulation to isolate the JSON

        jsonpath_expr = parse(self.MARKETPLACE_LISTINGS_QUERY)
        matches = [match.value for match in jsonpath_expr.find(item_result_json)]
        if len(matches) == 0:
            raise ValueError(f"The jsonpath_ng query for the listings ({self.MARKETPLACE_LISTINGS_QUERY}) was not found.")
        elif len(matches) > 1:
            raise ValueError(f"The jsonpath_ng query for listings ({self.MARKETPLACE_LISTINGS_QUERY}) returned multiple results.")

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
    
    def get_listing(self, listing_id: int):
        # TODO: Experiment with multiple listing ids to verify data presence

        url = f"https://www.facebook.com/marketplace/item/{listing_id}"
        self.page.goto(url)
        html = self.page.content()

        soup = BeautifulSoup(html, 'html.parser')

        item_result_tag = soup.find('script', string=lambda t: not t is None and self.LISTING_ID_QUERY in t)
        item_result_json = json.loads(item_result_tag.string)  # or any required manipulation to isolate the JSON

        jsonpath_expr = parse(self.PRODUCT_DETAILS_QUERY)
        match_dict = {str(match.full_path).split(".")[-1]: match.value for match in jsonpath_expr.find(item_result_json)}

        if len(match_dict) == 0:
            raise Exception(f"The listing details were not found for the listing id: {listing_id}")

        detail = {
            "listing_title": match_dict.get("marketplace_listing_renderable_target", {}).get("base_marketplace_listing_title", 'N/A'),
            "description": match_dict.get("target", {}).get("redacted_description", 'N/A'),
            "location": match_dict.get("target", {}).get("location_text", {}).get("text", 'N/A'),
            "creation_time": match_dict.get("target", {}).get("creation_time", 'N/A'),
            "delivery_types": match_dict.get("target", {}).get("delivery_types", 'N/A'),
            "current_listing_price": match_dict.get("target", {}).get("listing_price", {}).get("formatted_amount_zeros_stripped", 'N/A'),
            "listing_details": match_dict.get("target", {}).get("attribute_data", 'N/A'),
            "seller_name": match_dict.get("target", {}).get("marketplace_listing_seller", {}).get("name", 'N/A'),
            "seller_rating_average": match_dict.get("target", {}).get("marketplace_listing_seller", {}).get("marketplace_ratings_stats_by_role", {}).get("seller_stats", {}).get("five_star_ratings_average", 'N/A'),
            "seller_rating_count": match_dict.get("target", {}).get("marketplace_listing_seller", {}).get("marketplace_ratings_stats_by_role", {}).get("seller_stats", {}).get("five_star_total_rating_count_by_role", 'N/A'),
            "primary_listing_photo_url": match_dict.get("target", {}).get("primary_listing_photo", {}).get("listing_image", {}).get("uri", 'N/A'),
            "location_coordinates": match_dict.get("target", {}).get("item_location", 'N/A')
        }

        return detail


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