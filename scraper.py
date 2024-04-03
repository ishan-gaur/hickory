import os
import code
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

    async def login(self):
        try: 
            initial_url = "https://www.facebook.com/login/device-based/regular/login/"
            await self.page.goto(initial_url)
            email_input = await self.page.wait_for_selector('input[name="email"]')
            await email_input.fill(os.getenv("USERNAME"))
            password_input = await self.page.wait_for_selector('input[name="pass"]')
            await password_input.fill(os.getenv("PASSWORD"))
            await asyncio.sleep(2)
            login_button = await self.page.wait_for_selector('button[name="login"]')
            await login_button.click()

            # TODO: Handle MFA Forwarding for the user
            # time.sleep(20)

        except TimeoutError:
            print("One of the email, password, or login-button elements did not appear within 30 seconds")
            if input("Try again?").lower() in ["y", "yes"]:
                await self.login()
    
    async def search_fb_marketplace(self, city: str, query: str, max_price: int = None):
        # TODO: check somehow if this is a valid city or send that as a separate error at request time
        city = city.lower().replace(' ', '')
        if max_price is None:
            marketplace_url = f'https://www.facebook.com/marketplace/{city}/search/?query={query}'
        else:
            marketplace_url = f'https://www.facebook.com/marketplace/{city}/search/?query={query}&maxPrice={max_price}'

        await self.page.goto(marketplace_url)
        html = await self.page.content()
        soup = BeautifulSoup(html, 'html.parser')
        pretty_html = soup.prettify()
            
        # extract a simplified json for the listings instead of the one in the raw html
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
    
    async def get_listing_page(self, listing_id: int):
        listing_url = f'https://www.facebook.com/marketplace/item/{listing_id}'

        # TODO: Add a wrapper to handle all this json path crap, it's the same with most of this scraping logic
        # self.page.goto(listing_url)
        # time.sleep(2)

        # html = self.page.content()

        # soup = BeautifulSoup(html, 'html.parser')
        # item_result_tag = soup.find('script', string=lambda t: not t is None and 'marketplace_pdp' in t)
        # item_result_json = json.loads(item_result_tag.string)  # or any required manipulation to isolate the JSON
        # LISTING_DATA_QUERY = "$..marketplace_pdp.*"
        # jsonpath_expr = parse(LISTING_DATA_QUERY)
        # matches = [match.value for match in jsonpath_expr.find(item_result_json)]
        # if len(matches) == 0:
        #     raise ValueError(f"The jsonpath_ng query for the listing data ({LISTING_DATA_QUERY}) was not found.")
        # elif len(matches) > 1:
        #     raise ValueError(f"The jsonpath_ng query for listing data ({LISTING_DATA_QUERY}) returned multiple results.")
        # listing_data_json = matches[0]
        # listing_data = {
        #     'name': listing_data_json.get('marketplace_listing_title', 'N/A'),
        #     'price': listing_data_json['listing_price'].get('formatted_amount', 'N/A'),
        #     'location': listing_data_json['location']['reverse_geocode'].get('display_name', 'N/A'),
        #     'image_url': listing_data_json['primary_listing_photo']['image'].get('uri', 'N/A'),
        #     'delivery_options': listing_data_json.get('delivery_types', []),
        #     'seller': listing_data_json['marketplace_listing_seller'].get('name', 'N/A'),
        #     'item_id': listing_data_json['id']
        # }
        # return {"listing_data": listing_data}
        raise NotImplementedError("The get_listing_page method is not yet implemented.")


async def main():
    scraper = FacebookScraper()
    await scraper.start_session()
    await scraper.login()
    pp = pprint.PrettyPrinter(indent=4)
    interpreter = code.InteractiveInterpreter(locals={
        'scraper': scraper,
        'pp': pp,
        "asyncio": asyncio
    })
    cmd = input("> ")
    while cmd != "exit()":
        interpreter.runsource(f"pp.pprint(await scraper.{cmd})")
        cmd = input("> ")
    await scraper.end_session()

if __name__ == "__main__":
    asyncio.run(main())