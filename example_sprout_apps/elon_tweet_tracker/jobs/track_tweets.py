

import asyncio
import time
import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from example_sprout_apps.elon_tweet_tracker.data import classes as db

_config = None
_driver = None

def init_config(config):
    global _config
    _config = config

def safe_print(text):
    """Print text safely, handling Unicode errors on Windows"""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback: print with ASCII representation
        print(text.encode('ascii', 'ignore').decode('ascii'))

def clean_text(text):
    """Clean text for safe storage - keep Unicode but remove problematic chars"""
    if not text:
        return ""
    # Replace common problematic characters but keep most Unicode
    text = text.replace('\x00', '')  # Remove null bytes
    text = text.strip()
    return text

def get_driver():
    """Get or create Chrome driver using persistent profile"""
    global _driver
    if _driver is None:
        safe_print("[ElonTracker] Setting up Chrome driver with persistent profile...")
        
        # Use the saved Chrome profile from manual login
        profile_dir = os.path.join(os.getcwd(), "chrome_profile")
        
        if not os.path.exists(profile_dir):
            safe_print("[ElonTracker] ❌ ERROR: Chrome profile not found!")
            safe_print("[ElonTracker] Please run 'login_twitter_manual.bat' first to login.")
            raise Exception("Chrome profile not found. Run login_twitter_manual.bat first.")
        
        chrome_options = Options()
        chrome_options.add_argument(f"user-data-dir={profile_dir}")
        chrome_options.add_argument("--headless=new")  # Run headless using saved session
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36")
        
        safe_print("[ElonTracker] Initializing Chrome with saved session...")
        _driver = webdriver.Chrome(options=chrome_options)
        safe_print("[ElonTracker] ✅ Chrome driver ready with logged-in session!")
        
    return _driver

async def track_tweets_job():
    safe_print("[ElonTracker] Checking for new tweets via Selenium...")
    
    try:
        driver = get_driver()
        
        # Navigate to Elon's profile
        url = "https://twitter.com/elonmusk"
        safe_print(f"[ElonTracker] Loading {url}...")
        driver.get(url)
        
        # Wait for tweets to load
        await asyncio.sleep(5)  # Give page time to load
        
        # Find tweet elements (Twitter/X uses article tags for tweets)
        tweet_elements = driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
        
        safe_print(f"[ElonTracker] Found {len(tweet_elements)} tweet elements")
        
        count_new = 0
        for i, tweet_elem in enumerate(tweet_elements[:5]):  # Process first 5
            try:
                # Extract tweet text
                text_elements = tweet_elem.find_elements(By.CSS_SELECTOR, "[data-testid='tweetText']")
                if not text_elements:
                    safe_print(f"[ElonTracker] Tweet {i}: No text element found")
                    continue
                    
                text = text_elements[0].text
                text = clean_text(text)
                
                if not text:
                    safe_print(f"[ElonTracker] Tweet {i}: Empty text after cleaning")
                    continue
                
                # Extract timestamp
                time_elem = tweet_elem.find_elements(By.TAG_NAME, "time")
                created_at = time_elem[0].get_attribute("datetime") if time_elem else ""
                
                # Use timestamp + index as unique ID
                tweet_id = f"selenium_{int(time.time())}_{i}"
                
                safe_print(f"[ElonTracker] Saving tweet {i}: ID={tweet_id}, text_len={len(text)}")
                
                # Save to DB
                t_obj = db.Tweet(tweet_id)
                await t_obj.set(
                    tweet_id=tweet_id,
                    text=text[:500],  # Limit to 500 chars
                    created_at=created_at,
                    retweet_count=0,
                    favorite_count=0,
                    fetched_at=int(time.time())
                )
                count_new += 1
                safe_print(f"[ElonTracker] ✅ Saved tweet {i}")
                # Show preview with safe printing
                preview = text[:100] if len(text) > 100 else text
                safe_print(f"   Preview: {preview}...")
                
            except Exception as e:
                safe_print(f"[ElonTracker] ❌ Error processing tweet {i}: {e}")
                import traceback
                traceback.print_exc()
                continue
            
        safe_print(f"[ElonTracker] Processed {count_new} tweets successfully.")
            
    except Exception as e:
        safe_print(f"[ElonTracker] Job failed: {e}")
        import traceback
        traceback.print_exc()
