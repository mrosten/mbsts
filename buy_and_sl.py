import os
import argparse
import asyncio
import json
import requests
import time
from dotenv import load_dotenv
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
HOST = "https://clob.polymarket.com"
CHAIN_ID = 137
GAMMA_API_BASE = "https://gamma-api.polymarket.com"

def get_market_data(slug):
    url = f"{GAMMA_API_BASE}/markets/slug/{slug}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def get_client():
    if not PRIVATE_KEY: return None
    funder = PROXY_ADDRESS if PROXY_ADDRESS else Account.from_key(PRIVATE_KEY).address
    client = ClobClient(host=HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID, signature_type=1, funder=funder)
    try:
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
    except:
        return None
    return client

async def buy_and_watch_sl(args):
    url_parts = args.url.strip("/").split("?")[0].split("/")
    slug = url_parts[-1]
    
    print(f"Resolving market: {slug}")
    market_data = get_market_data(slug)
    if not market_data: return

    token_ids = json.loads(market_data.get("clobTokenIds", "[]"))
    outcome_idx = 0 if args.outcome.lower() == "up" else 1
    target_token_id = token_ids[outcome_idx]
    
    client = get_client()
    if not client: return

    # 1. Buy
    buy_price = 0.99 
    size = round(float(args.amount) / 0.16, 2) # Est. size based on current price approx, corrected below
    
    # We need current price to estimate size correctly for the Buy
    prices = json.loads(market_data.get("outcomePrices", "[]"))
    curr_price = float(prices[outcome_idx])
    size = round(float(args.amount) / curr_price, 2)

    print(f"Step 1: BUYING {size} shares at market (current ~{curr_price})...")
    buy_args = OrderArgs(price=0.99, size=size, token_id=target_token_id, side="BUY")
    
    buy_resp = client.post_order(client.create_order(buy_args))
    if not buy_resp.get("success"):
        print(f"Buy failed: {buy_resp}")
        return
    print(f"Buy Success! Order ID: {buy_resp.get('orderID')}")

    # 2. Watch Loop for Stop Loss
    sl_price = float(args.sl_price)
    print(f"Step 2: WATCHING price. If it drops BELOW {sl_price}, will SELL immediately.")
    
    try:
        while True:
            # Refresh price
            md = get_market_data(slug) 
            if md:
                ps = json.loads(md.get("outcomePrices", "[]"))
                now_price = float(ps[outcome_idx])
                print(f"  Current: ${now_price:.3f} | SL Trigger: ${sl_price:.3f}", end="\r")
                
                if now_price <= sl_price:
                    print(f"\nSTOP LOSS TRIGGERED! Price {now_price} <= {sl_price}. SELLING NOW...")
                    
                    sell_args = OrderArgs(
                        price=0.01, # Market sell to exit ASAP
                        size=size, # Assuming filled size, ideally fetch balance but for speed using orig size
                        token_id=target_token_id,
                        side="SELL"
                    )
                    sell_resp = client.post_order(client.create_order(sell_args))
                    print(f"Sell Response: {sell_resp}")
                    break
            
            await asyncio.sleep(2) # Check every 2s

    except KeyboardInterrupt:
        print("\nStopped watching.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--amount", type=float, required=True)
    parser.add_argument("--sl_price", type=float, required=True)
    parser.add_argument("--outcome", default="up")
    
    args = parser.parse_args()
    asyncio.run(buy_and_watch_sl(args))
