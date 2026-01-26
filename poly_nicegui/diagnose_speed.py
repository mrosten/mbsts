import time
import requests
import sys

def time_request(name, url):
    print(f"Testing {name}...", end=" ", flush=True)
    start = time.time()
    try:
        requests.get(url, timeout=5)
        print(f"OK ({time.time() - start:.2f}s)")
    except Exception as e:
        print(f"bFAILED ({time.time() - start:.2f}s) - {e}")

print("--- NETWORK SPEED TEST ---")
time_request("CoinCap Asset", "https://api.coincap.io/v2/assets/bitcoin")
time_request("CoinCap History", "https://api.coincap.io/v2/assets/bitcoin/history?interval=m1&start=1706227200000&end=1706227260000")
time_request("Binance Price", "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")
time_request("Binance Klines", "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=1")
time_request("CoinGecko Price", "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd")
print("--------------------------")
