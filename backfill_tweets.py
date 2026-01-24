"""
Backfill with VISIBLE progress - you can watch it work!
"""
import asyncio
import time
import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

sys.path.insert(0, '.')

from sprout.configuration import SproutConfiguration
from example_sprout_apps.elon_tweet_tracker.data import classes as db

def safe_print(text):
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'ignore').decode('ascii'))

def clean_text(text):
    if not text:
        return ""
    return text.replace('\x00', '').strip()

async def backfill_tweets():
    print("\n" + "=" * 60)
    print(" TWEET BACKFILL - VISIBLE MODE ".center(60))
    print("=" * 60)
    print("\n>>> Chrome will open - WATCH THE PROGRESS! <<<\n")
    
    # Initialize database
    config = SproutConfiguration(path='example_sprout_apps/elon_tweet_tracker/').config
    from sprout.database import initialize_database
    await initialize_database(config, config.db.sqlite.storage_file, db)
    print("✅ Database initialized\n")
    
    # Setup Chrome - VISIBLE window
    profile_dir = os.path.join(os.getcwd(), "chrome_profile")
    
    chrome_options = Options()
    chrome_options.add_argument(f"user-data-dir={profile_dir}")
    # NO headless mode - you can see it!
    chrome_options.add_argument("--window-size=1200,900")
    
    print("🌐 Opening Chrome (you'll see the window)...\n")
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Search
        search_query = "from:elonmusk since:2026-01-20"
        search_url = f"https://twitter.com/search?q={search_query}&f=live"
        
        print(f"🔍 Searching: {search_query}")
        print(f"📱 Loading: {search_url}\n")
        driver.get(search_url)
        
        print("⏳ Waiting 8 seconds for page load...")
        time.sleep(8)
        
        # Scroll to load tweets
        print("\n📜 Scrolling to load historical tweets...")
        print("    (Watch the Chrome window scroll!)\n")
        
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_count = 0
        max_scrolls = 30
        
        while scroll_count < max_scrolls:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2.5)
            
            new_height = driver.execute_script("return document.body.scrollHeight")
            scroll_count += 1
            print(f"   Scroll {scroll_count}/{max_scrolls}... ", end='', flush=True)
            
            if new_height == last_height:
                print("✅ Reached bottom!")
                break
            else:
                print(f"Loading more...")
            
            last_height = new_height
        
        # Extract tweets
        print(f"\n💾 Extracting tweets from page...")
        tweet_elements = driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
        print(f"✅ Found {len(tweet_elements)} tweet elements\n")
        
        print("💿 Saving to database...\n")
        saved = 0
        skipped = 0
        seen_texts = set()
        
        for i, elem in enumerate(tweet_elements, 1):
            try:
                text_els = elem.find_elements(By.CSS_SELECTOR, "[data-testid='tweetText']")
                if not text_els:
                    continue
                
                text = clean_text(text_els[0].text)
                if not text or text in seen_texts:
                    skipped += 1
                    continue
                
                seen_texts.add(text)
                
                time_els = elem.find_elements(By.TAG_NAME, "time")
                created_at = time_els[0].get_attribute("datetime") if time_els else ""
                
                tweet_id = f"backfill_{created_at}_{hash(text)}"
                
                tweet_obj = db.Tweet(tweet_id)
                await tweet_obj.set(
                    tweet_id=tweet_id,
                    text=text[:500],
                    created_at=created_at,
                    retweet_count=0,
                    favorite_count=0,
                    fetched_at=int(time.time())
                )
                
                saved += 1
                print(f"   [{saved:3d}] Saved: {text[:50]}...")
                
            except Exception as e:
                continue
        
        print(f"\n" + "=" * 60)
        print(f"✅ BACKFILL COMPLETE!")
        print(f"   💾 Saved: {saved} tweets")
        print(f"   ⏭️  Skipped: {skipped} duplicates")
        print("=" * 60 + "\n")
        
    finally:
        print("Closing Chrome in 5 seconds...")
        time.sleep(5)
        driver.quit()

if __name__ == "__main__":
    asyncio.run(backfill_tweets())
