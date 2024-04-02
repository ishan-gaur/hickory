import os
import time
import json
import pprint
from pathlib import Path
from playwright.sync_api import sync_playwright # testing framework for interaction with a web-browser
from playwright.async_api import async_playwright

from bs4 import BeautifulSoup # for html parsing
from jsonpath_ng import parse
from dotenv import load_dotenv
import asyncio

load_dotenv()


class FacebookScraper:
    # TODO: Handle keeping a scraping session open so that we can interact with it inside a python class, helpful
    # for debugging
    # - Also to maintain an interactive user session, we don't want to request 

    def __init__(self):
        self.playwright_context = None
        self.browser = None
        self.page = None
    
    async def start_session(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.page = await self.browser.new_page()

    async def end_session(self):
        await self.browser.close()
        await self.playwright.__aexit__(None, None, None) 

    # def __enter__(self):
        self.playwright_context = sync_playwright().__enter__()
        self.browser = self.playwright_context.chromium.launch(headless=False)
        self.page = self.browser.new_page()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.browser.close()
        self.playwright_context.__exit__(None, None, None)
    

    async def handle_user_login(self):
        try: 
            print("inside user login method...")
            initial_url = "https://www.facebook.com/login/device-based/regular/login/"
            await self.page.goto(initial_url)
            email_input = await self.page.wait_for_selector('input[name="email"]')
            await email_input.fill(os.getenv("USERNAME"))
            print("Successfully went to page ")
            await asyncio.sleep(2)
            password_input = await self.page.wait_for_selector('input[name="pass"]')
            await password_input.fill(os.getenv("PASSWORD"))
            await asyncio.sleep(2)
            login_button = await self.page.wait_for_selector('button[name="login"]')
            await login_button.click()

            # TODO: Handle MFA Forwarding for the user
            await asyncio.sleep(20)

        except TimeoutError:
            print("One of the email, password, or login-button elements did not appear within 30 seconds")
            if input("Try again?").lower() in ["y", "yes"]:
                await self.handle_user_login()
    
    # kdef handle_user_login(self):
    # k    try: 
    # k        print("inside user login method...")
    # k        initial_url = "https://www.facebook.com/login/device-based/regular/login/"
    # k        self.page.goto(initial_url)
    # k        email_input = self.page.wait_for_selector('input[name="email"]').fill(os.getenv("USERNAME"))
    # k        print("Successfully went to page ")
    # k        time.sleep(2)
    # k        password_input = self.page.wait_for_selector('input[name="pass"]').fill(os.getenv("PASSWORD"))
    # k        time.sleep(2)
    # k        login_button = self.page.wait_for_selector('button[name="login"]').click()

    # k        # TODO: Handle MFA Forwarding for the user
    # k        time.sleep(20)

    # k    except TimeoutError:
    # k        print("One of the email, password, or login-button elements did not appear within 30 seconds")
    # k        if input("Try again?").lower() in ["y", "yes"]:
    # k            self.handle_user_login()

    
    def search_fb_marketplace(self, city: str, query: str, max_price: int = None):
        city = city.lower().replace(' ', '')
        # TODO: check somehow if this is a valid city or send that as a separate error at request time
            
        # Define the URL to scrape.
        if max_price is None:
            marketplace_url = f'https://www.facebook.com/marketplace/{city}/search/?query={query}'
        else:
            marketplace_url = f'https://www.facebook.com/marketplace/{city}/search/?query={query}&maxPrice={max_price}'

        self.page.goto(marketplace_url)
        html = self.page.content()
        return html

        # with sync_playwright() as p:
        #     # Initialize the session, go to the login page, and wait for it to load
        #     browser = p.chromium.launch(headless=False)
        #     page = browser.new_page()
        #     page.goto(initial_url)
        #     time.sleep(2)

        #     # try logging in
        #     try:
        #         email_input = page.wait_for_selector('input[name="email"]').fill(os.getenv("USERNAME"))
        #         time.sleep(2)
        #         password_input = page.wait_for_selector('input[name="pass"]').fill(os.getenv("PASSWORD"))
        #         time.sleep(2)
        #         login_button = page.wait_for_selector('button[name="login"]').click()

        #         # TODO: Handle call to grab user MFA credential
        #         time.sleep(20)
        #         if page.get_by_text("The email or mobile number you entered isn't connected to an account.").is_visible():
        #             raise ValueError("Email or password is incorrect!")
        #     except TimeoutError:
        #         print("One of the email, password, or login-button elements did not appear within 30 seconds")
        #         if input("Try again?").lower() in ["y", "yes"]:
        #             search_fb_marketplace(city, query, max_price)

        #     time.sleep(2)
        #     page.goto(marketplace_url)

        #     html = page.content()
        #     input()
        # return html
    
    def extract_listings(self, html: str):
        soup = BeautifulSoup(html, 'html.parser')
        pretty_html = soup.prettify()
        with open('marketplace_search_results.html', 'w', encoding='utf-8') as file:
            file.write(pretty_html)
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
                'location': listing['location']['reverse_geocode'].get('display_name', 'N/A'),
                'image_url': listing['primary_listing_photo']['image'].get('uri', 'N/A'),
                'delivery_options': listing.get('delivery_types', []),
                'seller': listing['marketplace_listing_seller'].get('name', 'N/A'),
                'item_id': listing['id']
            }
            listings.append(extracted)
        return {"listings": listings}
    
    def get_listing_page(self, listing_id: int):
        listing_url = f'https://www.facebook.com/marketplace/item/{listing_id}'

        # TODO: Add a wrapper to handle all this json path crap, it's the same with most of this scraping logic
        self.page.goto(listing_url)
        time.sleep(2)

        html = self.page.content()

        soup = BeautifulSoup(html, 'html.parser')
        item_result_tag = soup.find('script', string=lambda t: not t is None and 'marketplace_pdp' in t)
        item_result_json = json.loads(item_result_tag.string)  # or any required manipulation to isolate the JSON
        LISTING_DATA_QUERY = "$..marketplace_pdp.*"
        jsonpath_expr = parse(LISTING_DATA_QUERY)
        matches = [match.value for match in jsonpath_expr.find(item_result_json)]
        if len(matches) == 0:
            raise ValueError(f"The jsonpath_ng query for the listing data ({LISTING_DATA_QUERY}) was not found.")
        elif len(matches) > 1:
            raise ValueError(f"The jsonpath_ng query for listing data ({LISTING_DATA_QUERY}) returned multiple results.")
        listing_data_json = matches[0]
        listing_data = {
            'name': listing_data_json.get('marketplace_listing_title', 'N/A'),
            'price': listing_data_json['listing_price'].get('formatted_amount', 'N/A'),
            'location': listing_data_json['location']['reverse_geocode'].get('display_name', 'N/A'),
            'image_url': listing_data_json['primary_listing_photo']['image'].get('uri', 'N/A'),
            'delivery_options': listing_data_json.get('delivery_types', []),
            'seller': listing_data_json['marketplace_listing_seller'].get('name', 'N/A'),
            'item_id': listing_data_json['id']
        }
        return {"listing_data": listing_data}


# kif __name__ == "__main__":
# k
# k    
# k    # kif Path('marketplace_search_results.html').exists():
# k    # k    with open('marketplace_search_results.html', 'r', encoding='utf-8') as file:
# k    # k        html = file.read()
# k    # kelse:
# k    # k    html = search_fb_marketplace(city="san francisco", query="tv stand")
# k    # k# html = search_fb_marketplace(city="houston", query="couch")
# k    # klistings = extract_listings(html)
# k
# k    # klistings = extract_listings(html)
# k    # kpp = pprint.PrettyPrinter(indent=4)
# k    # kpp.pprint(listings)
