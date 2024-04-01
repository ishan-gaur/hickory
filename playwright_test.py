import re
import time
from playwright.sync_api import sync_playwright, Page, expect

def test_has_title(page: Page):
    page.goto("https://playwright.dev/")
    time.sleep(2)

    # Expect a title "to contain" a substring.
    expect(page).to_have_title(re.compile("Playwright"))

def test_get_started_link(page: Page):
    page.goto("https://playwright.dev/")
    time.sleep(2)

    # Click the get started link.
    page.get_by_role("link", name="Get started").click()
    time.sleep(2)

    # Expects page to have a heading with the name of Installation.
    expect(page.get_by_role("heading", name="Installation")).to_be_visible()

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        test_has_title(page)
        time.sleep(2)
        test_get_started_link(page)