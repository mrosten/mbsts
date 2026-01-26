import os
import argparse
import asyncio
import json
import requests
from dotenv import load_dotenv
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType

# Load environment variables from .env file
load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
POLYGON_RPC_URL = os.getenv("POLYGON_RPC_URL")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
HOST = "https://clob.polymarket.com"
CHAIN_ID = 137  # Polygon Mainnet
GAMMA_API_BASE = "https://gamma-api.polymarket.com"

def get_market_data(slug):
    """Fetch market data from Gamma API using slug."""
    url = f"{GAMMA_API_BASE}/markets/slug/{slug}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching market data for slug '{slug}': {response.status_code}")
        return None

def get_client():
    """Initialize Polymarket CLOB client."""
    if not PRIVATE_KEY:
        print("Error: PRIVATE_KEY not found in environment variables.")
        return None

    if PROXY_ADDRESS:
        funder_address = PROXY_ADDRESS
    else:
        account = Account.from_key(PRIVATE_KEY)
        funder_address = account.address

    client = ClobClient(
        host=HOST,
        key=PRIVATE_KEY,
        chain_id=CHAIN_ID,
        signature_type=1,
        funder=funder_address
    )
    
    try:
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
    except Exception as e:
        print(f"Error deriving API credentials: {e}")
        return None
        
    return client

async def enquire_position(url):
    """Fetch market data and display position details."""
    # 1. Extract slug from URL
    url_parts = url.strip("/").split("?")[0].split("/")
    slug = url_parts[-1]
    
    print(f"\n--- Market Enquiry: {slug} ---")
    market_data = get_market_data(slug)
    if not market_data:
        return

    # 2. Get Token IDs and Market details
    token_ids = json.loads(market_data.get("clobTokenIds", "[]"))
    outcomes = json.loads(market_data.get("outcomes", "[]"))
    prices = json.loads(market_data.get("outcomePrices", "[]"))
    
    if not token_ids:
        print("Error: Could not find token IDs for this market.")
        return

    # 3. Initialize Client
    client = get_client()
    if not client:
        return

    # 4. Enquire Positions
    print(f"Question: {market_data.get('question')}\n")
    
    total_value = 0
    found_any = False

    for i, token_id in enumerate(token_ids):
        outcome_name = outcomes[i] if i < len(outcomes) else f"Outcome {i}"
        price = float(prices[i]) if i < len(prices) else 0.0
        
        try:
            params = BalanceAllowanceParams(
                asset_type=AssetType.CONDITIONAL,
                token_id=token_id
            )
            resp = client.get_balance_allowance(params)
            raw_balance = int(resp.get('balance', '0'))
            
            if raw_balance > 0:
                shares = raw_balance / 1_000_000
                value = shares * price
                print(f"BET ON: {outcome_name}")
                print(f"  Shares:  {shares:,.6f}")
                print(f"  Price:   ${price:.4f}")
                print(f"  Value:   ${value:,.2f}\n")
                total_value += value
                found_any = True
            else:
                # Still show price if they hold nothing
                pass
        except Exception as e:
            print(f"  Error checking {outcome_name}: {e}")

    if not found_any:
        print("You currently hold 0 shares in this market.")
    else:
        print(f"TOTAL POSITION VALUE: ${total_value:,.2f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enquire about Polymarket positions.")
    parser.add_argument("--url", required=True, help="Polymarket market URL")

    args = parser.parse_args()
    asyncio.run(enquire_position(args.url))
