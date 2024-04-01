from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By

from dotenv import load_dotenv
import os

import time

import logging

load_dotenv()

browser = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
# browser.implicitly_wait(5)

browser.get("https://www.facebook.com/login")

time.sleep(1)

username = os.getenv('USERNAME')
password = os.getenv('PASSWORD')

time.sleep(1)

username_input = browser.find_element(By.ID, "email")
password_input = browser.find_element(By.ID, "pass")

username_input.send_keys(username)
password_input.send_keys(password)

time.sleep(1)

login_button = browser.find_element(By.NAME, "login")
login_button.click()

time.sleep(30)

# Now logged in 

