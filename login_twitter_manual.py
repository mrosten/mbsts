"""
Manual Twitter Login - Creates a persistent Chrome profile
Run this ONCE to login manually. The session will be saved for automated scraping.
"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import os

# Create profile directory
profile_dir = os.path.join(os.getcwd(), "chrome_profile")
os.makedirs(profile_dir, exist_ok=True)

print("=" * 60)
print("MANUAL TWITTER LOGIN")
print("=" * 60)
print()
print("A Chrome window will open. Please:")
print("1. Log into Twitter with your credentials")
print("2. Navigate to https://twitter.com/elonmusk")
print("3. Make sure you can see tweets")
print("4. Close this terminal or press Ctrl+C when done")
print()
print(f"Session will be saved to: {profile_dir}")
print("=" * 60)
print()

# Setup Chrome with visible window and persistent profile
chrome_options = Options()
chrome_options.add_argument(f"user-data-dir={profile_dir}")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1200,900")

# Anti-detection options to make Selenium look like regular Chrome
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option('useAutomationExtension', False)
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36")

print("Opening Chrome...")
driver = webdriver.Chrome(options=chrome_options)

# Remove webdriver property to avoid detection
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")


# Navigate to Twitter login
driver.get("https://twitter.com/i/flow/login")

print("\n✅ Chrome is open!")
print("Please log in manually in the browser window.")
print("Navigate to @elonmusk's profile to verify you can see tweets.")
print("\nPress Ctrl+C here when you're done (or just close this terminal).\n")

try:
    # Keep the browser open until user closes it
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n\n✅ Session saved! You can now run the automated tracker.")
    print("   The tracker will use this logged-in session.")
    driver.quit()
