import os
import argparse
import asyncio
import json
import requests
import datetime
import sys
from dotenv import load_dotenv
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, BalanceAllowanceParams, AssetType

load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
HOST = "https://clob.polymarket.com"
CHAIN_ID = 137
GAMMA_API_BASE = "https://gamma-api.polymarket.com"

def get_market_data(slug):
    try:
        url = f"{GAMMA_API_BASE}/markets/slug/{slug}"
        response = requests.get(url, timeout=5)
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

async def watch_and_sell(args):
    url_parts = args.url.strip("/").split("?")[0].split("/")
    slug = url_parts[-1]
    
    print(f"\n--- STOP LOSS WATCHER ---")
    print(f"Market: {slug}")
    
    market_data = get_market_data(slug)
    if not market_data:
        print("Error: Could not find market.")
        return

    # Identify Token
    token_ids = json.loads(market_data.get("clobTokenIds", "[]"))
    outcome_idx = 0 if args.outcome.lower() == "up" else 1
    target_token_id = token_ids[outcome_idx]
    
    client = get_client()
    if not client: 
        print("Error: Could not initialize client.")
        return

    # Check initial balance
    params = BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, token_id=target_token_id)
    resp = client.get_balance_allowance(params)
    raw_bal = int(resp.get('balance', '0'))
    shares = raw_bal / 1_000_000
    
    if shares == 0:
        print("Warning: You currently have 0 shares in this outcome.")
        return

    # PRE-FLIGHT CHECK
    md = get_market_data(slug)
    if md:
        ps = json.loads(md.get("outcomePrices", "[]"))
        curr_price = float(ps[outcome_idx])
        print(f"Current Market Price: ${curr_price:.4f}")
        
        if args.price > 1.0:
            print(f"\n[ERROR] Trigger Price (${args.price}) cannot be greater than $1.00.")
            print("Polymarket share prices are between 0 and 1. Did you mean 0.10?")
            return

        if args.price >= curr_price:
            print(f"\n[WARNING] Your Trigger Price (${args.price:.4f}) is HIGHER than Current Price (${curr_price:.4f}).")
            print("If you proceed, this will TRIGGER AN IMMEDIATE SELL.")
            confirm = input("Are you sure? Type 'YES' to proceed: ")
            if confirm != "YES":
                print("Aborted.")
                return

    print(f"Monitoring {shares:,.2f} shares for STOP LOSS at ${args.price}")
    print("Watcher is ACTIVE. Press Ctrl+C to stop.\n")
    
    try:
        while True:
            # Heartbeat & Check
            md = get_market_data(slug)
            if md:
                ps = json.loads(md.get("outcomePrices", "[]"))
                curr_price = float(ps[outcome_idx])
                
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                sys.stdout.write(f"\r[{timestamp}] Current: ${curr_price:.3f} | Trigger: ${args.price:.3f} | Status: WATCHING  ")
                sys.stdout.flush()
                
                # SAFETY CHECK ON STARTUP (first run only)
                # We need to make sure we don't trigger immediately if user typed wrong price
                # We can do this by checking if it triggers immediately in the first few iterations
                # But better: Check before the loop!
                
                if curr_price <= args.price:
                    print(f"\n\n!!! STOP LOSS TRIGGERED !!!")
                    print(f"Price ${curr_price} dropped below limit ${args.price}")
                    
                    # Re-check balance to be sure
                    resp = client.get_balance_allowance(params)
                    curr_raw = int(resp.get('balance', '0'))
                    
                    if curr_raw > 0:
                        sell_size = curr_raw / 1_000_000
                        print(f"SELLING {sell_size} shares IMMEDIATELY...")
                        
                        sell_args = OrderArgs(
                            price=0.01, # Dump at any price
                            size=sell_size,
                            token_id=target_token_id,
                            side="SELL"
                        )
                        sell_resp = client.post_order(client.create_order(sell_args))
                        print(f"Sell Order Result: {sell_resp}")
                        break
                    else:
                        print("Error: No shares found to sell!")
                        break
            
            await asyncio.sleep(2)

    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n\nWatcher stopped by user.")
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--price", type=float, required=True, help="Stop Loss Trigger Price")
    parser.add_argument("--outcome", default="up", choices=["up", "down"])
    
    args = parser.parse_args()
    asyncio.run(watch_and_sell(args))
