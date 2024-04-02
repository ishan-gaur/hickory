import os
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
    # TODO: Handle keeping a scraping session open so that we can interact with it inside a python class, helpful
    # for debugging
    # - Also to maintain an interactive user session, we don't want to request 

    def __init__(self, playwright_context):
        self.playwright_context = playwright_context
        self.browser = self.playwright_context.chromium.launch(headless=False)
        self.page = self.browser.new_page()
    

    def handle_user_login(self):
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


if __name__ == "__main__":
    
    # if Path('marketplace_search_results.html').exists():
    #     with open('marketplace_search_results.html', 'r', encoding='utf-8') as file:
    #         html = file.read()
    # else:
    #     html = search_fb_marketplace(city="san francisco", query="tv stand")
    # # html = search_fb_marketplace(city="houston", query="couch")
    # listings = extract_listings(html)

    # listings = extract_listings(html)
    # pp = pprint.PrettyPrinter(indent=4)
    # pp.pprint(listings)

    # import inspect
    # with sync_playwright() as p:
    #     scraper = FacebookScraper(p)
    #     cmd = input(">>")
    #     while cmd != "exit()":
    #         cmd = input(">>")
    #         method_name = cmd[:cmd.find('(')]
    #         prov_args = 
    #         try:
    #             method = getattr(scraper, method_name)
    #             method()
            
    with sync_playwright() as p:
        FacebookScraper(p).handle_user_login()