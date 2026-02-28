import asyncio
from playwright.async_api import async_playwright
import json
import re

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # We want to catch ANY response that contains a number looking like a BTC price (e.g. 68000 to 70000)
        # Or better yet, just dump all JSON responses to find "priceToBeat" or similar fields.
        
        async def handle_response(response):
            try:
                if response.ok and "json" in response.headers.get("content-type", ""):
                    url = response.url
                    # Ignore purely analytics/image stuff if any
                    data = await response.json()
                    data_str = json.dumps(data)
                    
                    if "priceToBeat" in data_str or "68" in data_str or "69" in data_str:
                        # try to find the actual price to beat field
                        if "price" in data_str.lower() or "beat" in data_str.lower():
                            print(f"[MATCH in URL] {url}")
                            # Let's check keys
                            if isinstance(data, dict):
                                print(f"Keys: {list(data.keys())}")
                            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                                print(f"Array[0] Keys: {list(data[0].keys())}")
                                
                            # specifically search for priceToBeat
                            if "priceToBeat" in data_str:
                                print(f"FOUND priceToBeat string in {url}")
            except Exception:
                pass

        page.on("response", handle_response)
        
        print("Navigating...")
        await page.goto("https://polymarket.com/event/btc-updown-5m-1772045400", wait_until="networkidle")
        print("Done navigating, waiting 5 seconds...")
        await page.wait_for_timeout(5000)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
