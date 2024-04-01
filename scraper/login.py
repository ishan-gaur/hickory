from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService

browser = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
browser.implicitly_wait(5)

browser.get("https://www.facebook.com/login")

email_input = browser.find_element_by_id("email")
print(f"email: {email_input}")
password_input = browser.find_element_by_id("pass")

browser.implicitly_wait(5)
