"""
Fix API Keys: Regenerate API credentials specifically for Proxy (sig_type=1).
This bypasses any potential "wrong sig type" issues with existing derived keys.
"""
import os
import sys
import json
import asyncio
from dotenv import load_dotenv, set_key
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
HOST = "https://clob.polymarket.com"
CHAIN_ID = 137

def main():
    print("=" * 65)
    print("  REGENERATING API KEYS FOR PROXY TRADING")
    print("=" * 65)
    print(f"  Proxy: {PROXY_ADDRESS}")
    print(f"  Sig Type: 1 (POLY_PROXY)")
    print()

    # 1. Initialize Client with sig_type=1
    client = ClobClient(
        host=HOST,
        key=PRIVATE_KEY,
        chain_id=CHAIN_ID,
        signature_type=1,  # IMPORTANT: Force type 1
        funder=PROXY_ADDRESS
    )

    try:
        # 2. Force Create New Keys (don't specificy existing ones)
        print("[1] Creating NEW API Keys...")
        creds = client.create_or_derive_api_creds()
        print("  [OK] Credentials generated successfully!")
        print(f"  API Key:    {creds.api_key}")
        print(f"  API Secret: {creds.api_secret[:10]}...")
        print(f"  Passphrase: {creds.api_passphrase[:10]}...")
        
        # 3. Set the creds on the client
        client.set_api_creds(creds)
        
        # 4. Verify they work with a balance check
        print("\n[2] Verifying Keys with Balance Check...")
        bal_resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type="COLLATERAL"))
        usdc_bal = float(bal_resp.get('balance', 0)) / 10**6
        print(f"  [OK] Balance check succeeded.")
        print(f"  Proxy Balance: ${usdc_bal:.4f}")
        
        if usdc_bal > 0:
            print("  ✅ Funds are visible to the API!")
        else:
            print("  ⚠️ Balance is zero/low (this might be expected if funds are in USDC.e on-chain)")

        # 5. Output for .env
        print("\n" + "=" * 65)
        print("  SUCCESS! ADD THESE TO YOUR .env FILE:")
        print("=" * 65)
        print(f"POLYMARKET_API_KEY={creds.api_key}")
        print(f"POLYMARKET_API_SECRET={creds.api_secret}")
        print(f"POLYMARKET_API_PASSPHRASE={creds.api_passphrase}")
        print("=" * 65)
        
        # Update .env programmatically if possible
        update = input("\nDo you want me to update .env automatically? (y/N): ")
        if update.lower() == 'y':
            set_key(".env", "POLYMARKET_API_KEY", creds.api_key)
            set_key(".env", "POLYMARKET_API_SECRET", creds.api_secret)
            set_key(".env", "POLYMARKET_API_PASSPHRASE", creds.api_passphrase)
            print("  [OK] Updated .env file.")

    except Exception as e:
        print(f"\n[FAIL] Error generating/verifying keys: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
