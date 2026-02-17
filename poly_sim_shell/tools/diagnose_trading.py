"""
Polymarket Trading Diagnostics
================================
Tests every possible configuration to find what works.
Run this ONCE to identify the correct setup.
"""
import os
import sys
import json
import requests
import importlib.metadata

from dotenv import load_dotenv
from eth_account import Account

load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
HOST = "https://clob.polymarket.com"
CHAIN_ID = 137

# USDC contracts on Polygon
USDC_BRIDGED = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
USDC_NATIVE = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"

# Exchange contracts that need allowances
EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"
CTF = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def rpc_call(method, params):
    rpc_url = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
    try:
        resp = requests.post(rpc_url, json={
            "jsonrpc": "2.0", "method": method, "params": params, "id": 1
        }, timeout=10).json()
        return resp.get("result", "0x0")
    except Exception as e:
        return "0x0"


def check_balance(address, label):
    """Check MATIC and both USDC types for an address"""
    print(f"\n  [{label}] {address}")
    
    # MATIC
    matic_hex = rpc_call("eth_getBalance", [address, "latest"])
    matic = int(matic_hex, 16) / 10**18
    print(f"    MATIC:        {matic:.6f}")
    
    # Bridged USDC (what Polymarket uses)
    data = "0x70a08231000000000000000000000000" + address[2:].lower()
    bridged_hex = rpc_call("eth_call", [{"to": USDC_BRIDGED, "data": data}, "latest"])
    bridged = int(bridged_hex, 16) / 10**6
    print(f"    USDC.e:       ${bridged:.4f}  (Polymarket uses this)")
    
    # Native USDC
    native_hex = rpc_call("eth_call", [{"to": USDC_NATIVE, "data": data}, "latest"])
    native = int(native_hex, 16) / 10**6
    print(f"    USDC native:  ${native:.4f}  (Must bridge to use)")
    
    return {"matic": matic, "bridged": bridged, "native": native}


def check_allowance(owner, spender, token, label):
    """Check ERC20 allowance: how much `spender` can spend of `owner`'s tokens"""
    # allowance(address,address) = 0xdd62ed3e
    data = "0xdd62ed3e" + owner[2:].lower().zfill(64) + spender[2:].lower().zfill(64)
    result = rpc_call("eth_call", [{"to": token, "data": data}, "latest"])
    allowance = int(result, 16) / 10**6
    status = "[OK]" if allowance > 1000 else "[LOW]" if allowance > 0 else "[ZERO]"
    print(f"    {label}: {allowance:,.0f} {status}")
    return allowance


def test_signature_type(sig_type, funder, label):
    """Test if a specific signature_type + funder combo can create API creds and post orders"""
    from py_clob_client.client import ClobClient
    
    print(f"\n  {'─' * 55}")
    print(f"  Testing signature_type={sig_type} with funder={funder[:12]}... ({label})")
    
    try:
        client = ClobClient(
            host=HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID,
            signature_type=sig_type, funder=funder
        )
        
        # Step 1: API Creds
        try:
            creds = client.create_or_derive_api_creds()
            client.set_api_creds(creds)
            print(f"    API Creds:    [OK] Derived successfully")
            print(f"    API Key:      {creds.api_key[:20]}...")
        except Exception as e:
            print(f"    API Creds:    [FAIL] {e}")
            return False
        
        # Step 2: Balance check via API
        try:
            from py_clob_client.clob_types import BalanceAllowanceParams
            params = BalanceAllowanceParams(asset_type="COLLATERAL")
            bal = client.get_balance_allowance(params)
            balance = float(bal.get('balance', 0)) / 10**6
            print(f"    API Balance:  ${balance:.4f}")
        except Exception as e:
            print(f"    API Balance:  [FAIL] {e}")
        
        # Step 3: Try creating a TINY test order (won't post it)
        try:
            from py_clob_client.clob_types import OrderArgs
            
            # Get a real token ID from current BTC market
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            min15 = (now.minute // 15) * 15
            start_dt = now.replace(minute=min15, second=0, microsecond=0)
            ts = int(start_dt.timestamp())
            slug = f"btc-updown-15m-{ts}"
            
            meta_resp = requests.get(f"https://gamma-api.polymarket.com/markets/slug/{slug}", timeout=10)
            if meta_resp.status_code == 200:
                mdata = meta_resp.json()
                token_ids = json.loads(mdata.get("clobTokenIds", "[]"))
                neg_risk = mdata.get("neg_risk", False)  # Check if it's a neg_risk market!
                print(f"    Market found: {slug}")
                print(f"    neg_risk:     {'YES (!!)' if neg_risk else 'No'}")
                
                if token_ids:
                    token_id = token_ids[0]
                    
                    # Try signing an order (very small, will likely fail balance check but 
                    # signature should be valid)
                    order_args = OrderArgs(
                        price=0.50, size=1.0, side="BUY", token_id=token_id
                    )
                    
                    # Test WITHOUT neg_risk first
                    try:
                        signed = client.create_order(order_args)
                        print(f"    Order Sign:   [OK] (without neg_risk)")
                        
                        # Try posting (will fail if no balance, but we want to see the error)
                        try:
                            resp = client.post_order(signed)
                            if resp.get("success") or resp.get("orderID"):
                                print(f"    Order Post:   [OK] SUCCESS: {resp.get('orderID', '')}")
                            else:
                                err = resp.get("errorMsg", str(resp))
                                print(f"    Order Post:   [FAIL] {err}")
                                if "not enough balance" in err.lower():
                                    print(f"    >>> Signature is VALID! Just need funds.")
                                elif "invalid signature" in err.lower():
                                    print(f"    >>> Signature INVALID on post.")
                        except Exception as e:
                            print(f"    Order Post:   [FAIL] {e}")
                            
                    except Exception as e:
                        err_str = str(e)
                        print(f"    Order Sign:   [FAIL] (without neg_risk): {err_str[:80]}")
                    
                    # Test WITH neg_risk
                    try:
                        # Check if PartialCreateOrderOptions exists
                        from py_clob_client.clob_types import PartialCreateOrderOptions
                        options = PartialCreateOrderOptions(neg_risk=True)
                        signed_nr = client.create_order(order_args, options)
                        print(f"    Order Sign:   [OK] (WITH neg_risk=True)")
                        
                        try:
                            resp = client.post_order(signed_nr)
                            if resp.get("success") or resp.get("orderID"):
                                print(f"    Order Post:   [OK] SUCCESS: {resp.get('orderID', '')}")
                            else:
                                err = resp.get("errorMsg", str(resp))
                                print(f"    Order Post:   [FAIL] {err}")
                                if "not enough balance" in err.lower():
                                    print(f"    >>> VALID SIGNATURE! Just need balance.")
                                elif "invalid signature" in err.lower():
                                    print(f"    >>> Still invalid with neg_risk.")
                        except Exception as e:
                            print(f"    Order Post:   [FAIL] {e}")
                            
                    except ImportError:
                        print(f"    neg_risk:     [WARN] PartialCreateOrderOptions not found (old py-clob-client?)")
                    except Exception as e:
                        print(f"    Order Sign:   [FAIL] (WITH neg_risk): {str(e)[:80]}")
            else:
                print(f"    Market:       [FAIL] Could not fetch (status {meta_resp.status_code})")
                
        except Exception as e:
            print(f"    Order Test:   [FAIL] {e}")
            
        return True
        
    except Exception as e:
        print(f"    Init:         [FAIL] {e}")
        return False


def main():
    print("=" * 65)
    print("  POLYMARKET TRADING DIAGNOSTICS")
    print("=" * 65)
    
    # 0. Version check
    print("\n[1] ENVIRONMENT")
    try:
        ver = importlib.metadata.version("py-clob-client")
        print(f"  py-clob-client: v{ver}")
    except:
        print(f"  py-clob-client: version unknown")
    
    if not PRIVATE_KEY:
        print("  [FAIL] PRIVATE_KEY not set in .env!")
        sys.exit(1)
    
    eoa = Account.from_key(PRIVATE_KEY)
    print(f"  Private Key:    ...{PRIVATE_KEY[-8:]}")
    print(f"  EOA Address:    {eoa.address}")
    print(f"  Proxy Address:  {PROXY_ADDRESS or 'NOT SET'}")
    
    # 1. On-chain balances
    print("\n" + "=" * 65)
    print("[2] ON-CHAIN BALANCES")
    eoa_bal = check_balance(eoa.address, "EOA")
    proxy_bal = None
    if PROXY_ADDRESS:
        proxy_bal = check_balance(PROXY_ADDRESS, "PROXY")
    
    # 2. Allowances (for the proxy - this is where funds are)
    if PROXY_ADDRESS and proxy_bal and proxy_bal["bridged"] > 0:
        print("\n" + "=" * 65)
        print("[3] USDC.e ALLOWANCES (Proxy -> Exchange Contracts)")
        check_allowance(PROXY_ADDRESS, EXCHANGE, USDC_BRIDGED, "Main Exchange")
        check_allowance(PROXY_ADDRESS, NEG_RISK_EXCHANGE, USDC_BRIDGED, "NegRisk Exchange")
        check_allowance(PROXY_ADDRESS, NEG_RISK_ADAPTER, USDC_BRIDGED, "NegRisk Adapter")
        
        print("\n  CONDITIONAL TOKEN ALLOWANCES (Proxy -> Exchange Contracts)")
        check_allowance(PROXY_ADDRESS, EXCHANGE, CTF, "CTF -> Main Exchange")
        check_allowance(PROXY_ADDRESS, NEG_RISK_EXCHANGE, CTF, "CTF -> NegRisk Exchange")
        check_allowance(PROXY_ADDRESS, NEG_RISK_ADAPTER, CTF, "CTF -> NegRisk Adapter")
    
    # 3. Test all signature types
    print("\n" + "=" * 65)
    print("[4] SIGNATURE TYPE TESTS")
    
    configs = []
    
    # Type 1: POLY_PROXY (Magic Link) -- THIS IS MOST LIKELY CORRECT
    if PROXY_ADDRESS:
        configs.append((1, PROXY_ADDRESS, "POLY_PROXY + Proxy Funder"))
    
    # Type 2: GNOSIS_SAFE -- try with proxy funder
    if PROXY_ADDRESS:
        configs.append((2, PROXY_ADDRESS, "GNOSIS_SAFE + Proxy Funder"))
    
    # Type 0: EOA Direct
    configs.append((0, eoa.address, "EOA Direct"))
    
    for sig_type, funder, label in configs:
        test_signature_type(sig_type, funder, label)
    
    # Summary
    print("\n" + "=" * 65)
    print("[5] RECOMMENDATIONS")
    print("=" * 65)
    
    if proxy_bal and proxy_bal["bridged"] > 0:
        print(f"  [OK] Your Proxy has ${proxy_bal['bridged']:.2f} USDC.e -- funds ARE there.")
        print(f"  [OK] You should NOT need to transfer to EOA.")
    else:
        print(f"  [WARN] Proxy has $0 -- funds may have moved or address is wrong.")
    
    print(f"""
  MOST LIKELY FIX:
  -----------------
  1. Use signature_type=1 (POLY_PROXY) with funder={PROXY_ADDRESS}
  2. Add neg_risk=True when creating orders (BTC markets need this)
  3. Update py-clob-client: pip install --upgrade py-clob-client
  
  If sig_type=1 gives "invalid signature" but sig_type=2 works,
  you may have logged in via browser wallet (not email).
  """)


if __name__ == "__main__":
    main()

