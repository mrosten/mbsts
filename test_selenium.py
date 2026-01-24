"""Quick test to verify Selenium setup works"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

print("Testing Selenium setup...")
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

print("Creating Chrome driver (will auto-download driver if needed)...")
driver = webdriver.Chrome(options=chrome_options)

print("Navigating to example.com...")
driver.get("https://example.com")

print(f"Page title: {driver.title}")
print(f"✅ Selenium is working! Chrome version detected and driver loaded successfully.")

driver.quit()
print("Test complete!")
