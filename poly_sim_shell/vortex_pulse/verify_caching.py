
import sys
import os
import time

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from market import MarketDataManager

def test_caching():
    # Use a dummy logger to capture logs
    logs = []
    def logger(msg):
        logs.append(str(msg))
        print(msg)

    print("Initializing MarketDataManager...")
    mdm = MarketDataManager(logger_func=logger)
    
    # Wait a bit for initialization but we don't really need the WS
    slug = f"btc-updown-5m-{int(time.time() // 300 * 300)}"
    
    print(f"\n--- First Call for {slug} ---")
    res1 = mdm.fetch_polymarket(slug)
    
    print(f"\n--- Second Call for {slug} (Should be cached) ---")
    res2 = mdm.fetch_polymarket(slug)
    
    scrape_logs = [l for l in logs if "Audit: P2B scraped from web" in l]
    print(f"\nScrape log count: {len(scrape_logs)}")
    
    if len(scrape_logs) == 1:
        print("Success: Price was only scraped once!")
    else:
        print(f"Failure: Price was scraped {len(scrape_logs)} times.")
    
    # Force exit because of background threads
    os._exit(0)

if __name__ == "__main__":
    try:
        test_caching()
    except Exception as e:
        print(f"Test crashed: {e}")
        os._exit(1)
