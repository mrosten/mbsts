"""
Manual test of tweet scraping with Selenium
"""
import asyncio
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

print("=== Manual Twitter Scraping Test ===\n")

# Setup Chrome
print("1. Setting up headless Chrome...")
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

driver = webdriver.Chrome(options=chrome_options)
print("✅ Chrome initialized\n")

# Navigate to Elon's profile
url = "https://twitter.com/elonmusk"
print(f"2. Loading {url}...")
driver.get(url)
print(f"✅ Page loaded. Title: {driver.title}\n")

# Wait for page to load
print("3. Waiting 8 seconds for content to load...")
time.sleep(8)

# Try to find tweets
print("4. Searching for tweet elements...")
tweet_selectors = [
    "article[data-testid='tweet']",
    "article",
    "div[data-testid='tweet']",
    "[data-testid='tweetText']"
]

for selector in tweet_selectors:
    elements = driver.find_elements(By.CSS_SELECTOR, selector)
    print(f"   Selector '{selector}': Found {len(elements)} elements")

# Save page source for inspection
print("\n5. Saving page source...")
with open("twitter_page_source.html", "w", encoding="utf-8") as f:
    f.write(driver.page_source)
print("✅ Saved to twitter_page_source.html")

# Try to find any text content
print("\n6. Looking for any text-heavy divs...")
all_divs = driver.find_elements(By.TAG_NAME, "div")
text_divs = [d for d in all_divs if d.text and len(d.text) > 50]
print(f"Found {len(text_divs)} divs with substantial text")

if text_divs:
    print("\nFirst few text snippets:")
    for i, div in enumerate(text_divs[:3]):
        text = div.text[:150].replace("\n", " ")
        print(f"  [{i+1}] {text}...")

driver.quit()
print("\n✅ Test complete!")
