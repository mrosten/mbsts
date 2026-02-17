"""
Final diagnostic: Check if the Polymarket CLOB server recognizes our EOA->proxy relationship.
Also try to determine the actual proxy address for our EOA.
"""
import os, sys, json, requests
from dotenv import load_dotenv
from eth_account import Account

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
HOST = "https://clob.polymarket.com"

eoa = Account.from_key(PRIVATE_KEY)

print("=" * 65)
print("  POLYMARKET API RELATIONSHIP CHECK")
print("=" * 65)
print(f"  EOA:   {eoa.address}")
print(f"  Proxy: {PROXY_ADDRESS}")
print()

# 1. Try to derive API creds with EACH signature type and check what the API returns
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams

configs = [
    (0, eoa.address, "EOA Direct"),
    (1, PROXY_ADDRESS, "POLY_PROXY"),
    (2, PROXY_ADDRESS, "GNOSIS_SAFE"),
]

for sig_type, funder, label in configs:
    print(f"--- Testing sig_type={sig_type} ({label}) ---")
    try:
        client = ClobClient(
            host=HOST,
            key=PRIVATE_KEY,
            chain_id=137,
            signature_type=sig_type,
            funder=funder,
        )
        
        # Derive creds
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        
        print(f"  API Key:    {creds.api_key[:20]}...")
        print(f"  API Secret: {creds.api_secret[:20]}...")
        
        # Check balance
        try:
            bal = client.get_balance_allowance(BalanceAllowanceParams(asset_type="COLLATERAL"))
            balance = float(bal.get('balance', 0)) / 10**6
            print(f"  Balance:    ${balance:.4f}")
        except Exception as e:
            print(f"  Balance:    ERROR - {e}")
        
        # Try to check what address the API thinks we are
        # The /auth/api-keys endpoint should tell us
        try:
            headers = client.create_level_2_headers("GET", "/auth/api-keys")
            resp = requests.get(f"{HOST}/auth/api-keys", headers=headers, timeout=10)
            if resp.status_code == 200:
                keys_data = resp.json()
                print(f"  API Keys:   {json.dumps(keys_data, indent=4)[:300]}...")
            else:
                print(f"  API Keys:   HTTP {resp.status_code}")
        except Exception as e:
            print(f"  API Keys endpoint: {e}")
            
    except Exception as e:
        print(f"  ERROR: {e}")
    print()

# 2. Check Polymarket profile API for our address
print("=" * 65)
print("[2] CHECKING POLYMARKET PROFILE API")
print("=" * 65)

for addr, label in [(eoa.address, "EOA"), (PROXY_ADDRESS, "PROXY")]:
    print(f"\n  {label}: {addr}")
    try:
        # profiles endpoint
        resp = requests.get(f"https://gamma-api.polymarket.com/profiles/{addr}", timeout=10)
        if resp.status_code == 200:
            profile = resp.json()
            print(f"    Profile found: {json.dumps(profile, indent=4)[:300]}...")
        else:
            print(f"    Profile: HTTP {resp.status_code}")
    except Exception as e:
        print(f"    Profile error: {e}")

# 3. Check Polymarket's verify/derive endpoint
print()
print("=" * 65)
print("[3] CHECKING ACCOUNT DETAILS")
print("=" * 65)

# Try calling the CLOB /auth/derive-api-key directly to see what it returns
try:
    client0 = ClobClient(host=HOST, key=PRIVATE_KEY, chain_id=137, signature_type=0, funder=eoa.address)
    # Check the raw response
    import time
    timestamp = int(time.time())
    
    # L1 auth header
    from py_clob_client.headers.headers import create_level_1_headers
    l1_headers = create_level_1_headers(client0.signer)
    
    # Check /auth/derive-api-key
    resp = requests.get(f"{HOST}/auth/derive-api-key", headers=l1_headers, timeout=10)
    print(f"  derive-api-key (sig_type=0): HTTP {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"    Response: {json.dumps(data, indent=4)[:300]}...")
    else:
        print(f"    Response: {resp.text[:200]}")
except Exception as e:
    print(f"  Error: {e}")

# 4. Try to find our proxy via CLOB whoami-type endpoints 
print()
print("=" * 65)
print("[4] CHECKING PROXY FACTORY ON-CHAIN")
print("=" * 65)

# Known Polymarket Proxy Wallet Factory on Polygon
FACTORY = "0xaB45c5A4B0c941a2F231C04C3f49182e1A254052"
RPC = os.getenv("POLYGON_RPC_URL", "https://polygon-bor-rpc.publicnode.com")

# The factory has a function to get/predict the proxy for a given wallet
# Common function: getProxy(address) or proxy(address) or proxies(address)
# keccak256("getProxy(address)")[:8] = we need to compute this
from eth_utils import keccak as keccak_hash

for fn_name in ["getProxy(address)", "proxies(address)", "getProxyWallet(address)", "proxyFor(address)"]:
    sig = keccak_hash(text=fn_name)[:4].hex()
    eoa_padded = eoa.address[2:].lower().zfill(64)
    data = f"0x{sig}{eoa_padded}"
    
    try:
        resp = requests.post(RPC, json={
            "jsonrpc": "2.0", "method": "eth_call",
            "params": [{"to": FACTORY, "data": data, "gas": "0x100000"}, "latest"],
            "id": 1
        }, timeout=10).json()
        result = resp.get("result")
        error = resp.get("error")
        
        if error:
            print(f"  {fn_name}: reverted ({error.get('message','')[:40]})")
        elif result and result != "0x" + "0"*64 and result != "0x":
            addr = "0x" + result[-40:]
            match = " <-- MATCHES!" if addr.lower() == PROXY_ADDRESS.lower() else f" (DIFFERENT from proxy {PROXY_ADDRESS[:12]}...)"
            print(f"  {fn_name}: {addr}{match}")
        else:
            print(f"  {fn_name}: zero/empty")
    except Exception as e:
        print(f"  {fn_name}: error {e}")

print()
print("DONE")
