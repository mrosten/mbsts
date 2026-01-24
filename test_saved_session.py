"""
Test if the saved Chrome profile can access Twitter without logging in again
"""
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

profile_dir = os.path.join(os.getcwd(), "chrome_profile")

if not os.path.exists(profile_dir):
    print("❌ Chrome profile not found! Run login_twitter_manual.bat first.")
    exit(1)

print("=== Testing Saved Twitter Session ===\n")

# Setup Chrome with saved profile (headless this time)
chrome_options = Options()
chrome_options.add_argument(f"user-data-dir={profile_dir}")
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

print("1. Opening Chrome with saved session (headless)...")
driver = webdriver.Chrome(options=chrome_options)

try:
    print("2. Navigating to @elonmusk...")
    driver.get("https://twitter.com/elonmusk")
    time.sleep(8)
    
    print("3. Looking for tweets...")
    tweet_elements = driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
    
    if len(tweet_elements) > 0:
        print(f"✅ SUCCESS! Found {len(tweet_elements)} tweets!")
        print("\n4. Sample tweet content:")
        for i, elem in enumerate(tweet_elements[:2]):
            try:
                text_elem = elem.find_element(By.CSS_SELECTOR, "[data-testid='tweetText']")
                print(f"\n   Tweet {i+1}: {text_elem.text[:100]}...")
            except:
                pass
        print("\n✅ The saved session works! The tracker is ready to run!")
    else:
        print("❌ No tweets found - might need to login again")
        print("   Try running login_twitter_manual.bat one more time")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    driver.quit()
    print("\n✅ Test complete!")
