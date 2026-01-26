import market_analysis
import sys

url = "https://polymarket.com/event/btc-updown-15m-1769381100" # Use a likely expired but valid slug format
print(f"Testing analysis for: {url}")

try:
    result = market_analysis.analyze_market_data(url)
    print("Result keys:", result.keys())
    print("Result:", result)
except Exception as e:
    print(f"FATAL ERROR: {e}")
    import traceback
    traceback.print_exc()
