import os
import argparse
import asyncio
import json
import requests
import math
from dotenv import load_dotenv
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# Load environment variables
load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
HOST = "https://clob.polymarket.com"
CHAIN_ID = 137
GAMMA_API_BASE = "https://gamma-api.polymarket.com"

def get_market_data(slug):
    url = f"{GAMMA_API_BASE}/markets/slug/{slug}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None

def get_client():
    if not PRIVATE_KEY:
        print("Error: PRIVATE_KEY not found.")
        return None
    funder = PROXY_ADDRESS if PROXY_ADDRESS else Account.from_key(PRIVATE_KEY).address
    client = ClobClient(host=HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID, signature_type=1, funder=funder)
    try:
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
    except Exception as e:
        print(f"Error deriving API credentials: {e}")
        return None
    return client

async def buy_and_tp(args):
    """Buy shares and immediately set a Take Profit sell order."""
    url_parts = args.url.strip("/").split("?")[0].split("/")
    slug = url_parts[-1]
    
    print(f"Resolving market: {slug}")
    market_data = get_market_data(slug)
    if not market_data:
        print(f"Error: Could not find market for {slug}")
        return

    # 1. Setup Token and Prices
    token_ids = json.loads(market_data.get("clobTokenIds", "[]"))
    outcome_idx = 0 if args.outcome.lower() == "up" else 1
    target_token_id = token_ids[outcome_idx]
    
    # Calculate size if amount is given (shares takes precedence)
    buy_price = float(args.buy_price) if args.buy_price else 0.99 # 0.99 for market-like fill
    if args.shares:
        size = float(args.shares)
    else:
        size = round(float(args.amount) / buy_price, 2)

    print(f"Targeting: {args.outcome.upper()} | Size: {size} shares")
    
    client = get_client()
    if not client: return

    # 2. PLACE BUY ORDER
    print(f"Step 1: Placing BUY order at limit ${buy_price:.2f}...")
    buy_args = OrderArgs(
        price=buy_price,
        size=size,
        token_id=target_token_id,
        side="BUY"
    )
    
    try:
        buy_resp = client.post_order(client.create_order(buy_args))
        if not buy_resp.get("success"):
            print(f"Buy failed: {buy_resp}")
            return
        
        order_id = buy_resp.get("orderID")
        print(f"Buy Post Success! Order ID: {order_id}")
        
        # Wait for match (briefly)
        print("Waiting for match confirmation...")
        await asyncio.sleep(1.5) 
        
        # 3. PLACE TP SELL ORDER
        tp_price = float(args.tp_price)
        print(f"Step 2: Placing TAKE PROFIT SELL order for {size} shares at limit ${tp_price:.2f}...")
        
        sell_args = OrderArgs(
            price=tp_price,
            size=size,
            token_id=target_token_id,
            side="SELL"
        )
        
        sell_resp = client.post_order(client.create_order(sell_args))
        if sell_resp.get("success"):
            print(f"SUCCESS: Take Profit order placed at ${tp_price:.2f}")
            print(f"TP Order ID: {sell_resp.get('orderID')}")
        else:
            print(f"TP Sell failed: {sell_resp}")
            print("Note: You may need to manually sell if the buy matched but the sell failed.")

    except Exception as e:
        print(f"Error during automation: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Buy and set Take Profit.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--outcome", choices=["up", "down"], required=True)
    parser.add_argument("--shares", type=float, help="Number of shares to buy")
    parser.add_argument("--amount", type=float, help="USD amount to spend (if shares not specified)")
    parser.add_argument("--buy_price", type=float, help="Buy limit price (default 0.99 for market fill)")
    parser.add_argument("--tp_price", type=float, required=True, help="Take Profit limit sell price")

    args = parser.parse_args()
    asyncio.run(buy_and_tp(args))
