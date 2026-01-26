import os
import argparse
import asyncio
import json
import requests
from dotenv import load_dotenv
from eth_account import Account
from py_clob_client.client import ClobClient

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

async def check_balance(url):
    """Parse URL, fetch market data, and check balances."""
    # 1. Extract slug from URL
    url_parts = url.strip("/").split("?")[0].split("/")
    slug = url_parts[-1]
    
    print(f"Resolving market slug: {slug}")
    market_data = get_market_data(slug)
    if not market_data:
        return

    # 2. Get Token IDs and Market details
    token_ids = json.loads(market_data.get("clobTokenIds", "[]"))
    outcomes = json.loads(market_data.get("outcomes", "[]"))
    
    if not token_ids:
        print("Error: Could not find token IDs for this market.")
        return

    # 3. Initialize Client
    client = get_client()
    if not client:
        return

    from py_clob_client.clob_types import BalanceAllowanceParams, AssetType

    # 4. Check Balances
    print(f"Checking balances for {len(token_ids)} outcomes...")
    for i, token_id in enumerate(token_ids):
        outcome_name = outcomes[i] if i < len(outcomes) else f"Outcome {i}"
        try:
            params = BalanceAllowanceParams(
                asset_type=AssetType.CONDITIONAL,
                token_id=token_id
            )
            resp = client.get_balance_allowance(params)
            bal_val = resp.get('balance', '0')
            print(f"  {outcome_name}: {bal_val} shares")
        except Exception as e:
            print(f"  Error checking balance for {outcome_name}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check Polymarket share balances.")
    parser.add_argument("--url", required=True, help="Polymarket market URL")

    args = parser.parse_args()
    asyncio.run(check_balance(args.url))
