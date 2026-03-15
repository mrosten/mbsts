
import sys
import os

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from market import MarketDataManager

def test_extraction():
    mdm = MarketDataManager()
    slug = "btc-updown-5m-1773334200" # Current window from previous test
    print(f"Testing extraction for slug: {slug}")
    price = mdm._extract_price_to_beat_from_web(slug)
    if price:
        print(f"Successfully extracted: ${price:,.2f}")
    else:
        print("Failed to extract price using market.py method")

if __name__ == "__main__":
    test_extraction()
