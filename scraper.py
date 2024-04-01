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

# Get listings of particular item in a particular city for a particular price.
def search_fb_marketplace(city: str, query: str, max_price: int = None):
    city = city.lower().replace(' ', '')
    # TODO: check somehow if this is a valid city or send that as a separate error at request time
        
    # Define the URL to scrape.
    if max_price is None:
        marketplace_url = f'https://www.facebook.com/marketplace/{city}/search/?query={query}'
    else:
        marketplace_url = f'https://www.facebook.com/marketplace/{city}/search/?query={query}&maxPrice={max_price}'
    initial_url = "https://www.facebook.com/login/device-based/regular/login/"

    with sync_playwright() as p:
        # Initialize the session, go to the login page, and wait for it to load
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(initial_url)
        time.sleep(2)

        # try logging in
        try:
            print(os.getenv("USER_EMAIL"))
            email_input = page.wait_for_selector('input[name="email"]').fill(os.getenv("USER_EMAIL"))
            time.sleep(2)
            password_input = page.wait_for_selector('input[name="pass"]').fill(os.getenv("USER_PASS"))
            time.sleep(2)
            login_button = page.wait_for_selector('button[name="login"]').click()
            time.sleep(2)
            if page.get_by_text("The email or mobile number you entered isn't connected to an account.").is_visible():
                raise ValueError("Email or password is incorrect!")
        except TimeoutError:
            print("One of the email, password, or login-button elements did not appear within 30 seconds")
            if input("Try again?").lower() in ["y", "yes"]:
                search_fb_marketplace(city, query, max_price)

        time.sleep(2)
        page.goto(marketplace_url)

        html = page.content()
        input()
    return html
    
def extract_listings(html: str):
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
            'seller': listing['marketplace_listing_seller'].get('name', 'N/A')
        }
        listings.append(extracted)
    return listings

if __name__ == "__main__":
    if Path('marketplace_search_results.html').exists():
        with open('marketplace_search_results.html', 'r', encoding='utf-8') as file:
            html = file.read()
    else:
        html = search_fb_marketplace(city="houston", query="couch")
    # html = search_fb_marketplace(city="houston", query="couch")
    listings = extract_listings(html)

    listings = extract_listings(html)
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(listings)
