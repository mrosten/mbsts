"""
MANUAL BUYER v3 - The "One-Click" Proxy Trader
1. Connects to Proxy (SigType=1)
2. Auto-scans for the latest BTC 15m active market
3. Asks user to pick a side (Yes/No) and Amount
4. Executes trade with correct neg_risk handling
"""
import os
import sys
import json
import asyncio
import time
import requests
from dotenv import load_dotenv
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, BalanceAllowanceParams, PartialCreateOrderOptions

# Force stdout encoding for Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
load_dotenv()

# --- CONFIG ---
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
HOST = "https://clob.polymarket.com"
CHAIN_ID = 137

class ManualBuyerV3:
    def __init__(self):
        self.client = None
        if not PRIVATE_KEY or not PROXY_ADDRESS:
            print("❌ CRITICAL: PRIVATE_KEY or PROXY_ADDRESS missing in .env")
            sys.exit(1)
            
        print("=" * 60)
        print("  MANUAL BUYER v3 (PROXY MODE)")
        print("=" * 60)
        print(f"  Proxy: {PROXY_ADDRESS}")
        
        self._init_client()

    def _init_client(self):
        """Initialize ClobClient with FORCE PROXY settings"""
        try:
            self.client = ClobClient(
                host=HOST,
                key=PRIVATE_KEY,
                chain_id=CHAIN_ID,
                signature_type=2,  # TRY GNOSIS SAFE (Type 2)
                funder=PROXY_ADDRESS
            )
            
            # DERIVE NEW KEYS FOR THIS SESSION
            print("  [INIT] Deriving session API keys...")
            creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(creds)
            
            # Check Balance
            try:
                bal = self.client.get_balance_allowance(BalanceAllowanceParams(asset_type="COLLATERAL"))
                usdc = float(bal.get('balance', 0)) / 10**6
                print(f"  [OK] Proxy Balance: ${usdc:.2f}")
            except Exception as e:
                print(f"  [WARN] Balance check error: {e}")
                
        except Exception as e:
            print(f"  [ERROR] Client init failed: {e}")
            sys.exit(1)

    def fetch_active_market(self):
        """Find the most relevant active BTC 15m market"""
        print("\n  [SCAN] Searching for active BTC 15m markets...")
        
        candidates = []
        
        # METHOD 1: Broad Search via Gamma API
        try:
            # Search for "bitcoin" generally
            url = "https://gamma-api.polymarket.com/events"
            params = {"slug": "bitcoin", "closed": "false", "limit": 20}
            
            resp = requests.get(url, params=params)
            data = resp.json()
            if not isinstance(data, list): data = []
            
            for event in data:
                title = event.get("title", "")
                
                # Check for "15m" or "15 Min" or similar
                if "15m" not in title.lower() and "15 min" not in title.lower(): continue
                
                markets = event.get("markets", [])
                for m in markets:
                    if m.get("closed"): continue
                    if "clobTokenIds" not in m: continue
                    
                    candidates.append({
                        "question": m.get("question", title),
                        "slug": event.get("slug"),
                        "token_ids": json.loads(m.get("clobTokenIds", "[]")),
                        "outcomes": json.loads(m.get("outcomes", "[]")),
                        "neg_risk": m.get("negRisk", False)
                    })
        except Exception as e:
            print(f"  [WARN] Gamma search failed: {e}")

        # METHOD 2: Calculate specific 15m market slug (Fallback)
        # Copied logic from manual_buy_v2.py
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            minutes = now.minute
            
            # Look ahead logic? If close to end, maybe look at next?
            # 15m logic: floor to 00, 15, 30, 45
            floor = (minutes // 15) * 15
            start_dt = now.replace(minute=floor, second=0, microsecond=0)
            ts_start = int(start_dt.timestamp())
            
            # Predict the slug
            slug = f"btc-updown-15m-{ts_start}"
            
            # Check if we already found it?
            found_slugs = [c['slug'] for c in candidates]
            
            if slug not in found_slugs:
                # Fetch specific event by slug
                print(f"  [SCAN] Checking specific slug: {slug}...")
                url = f"https://gamma-api.polymarket.com/events"
                resp = requests.get(url, params={"slug": slug})
                data = resp.json()
                
                if isinstance(data, list) and len(data) > 0:
                    event = data[0]
                    markets = event.get("markets", [])
                    for m in markets:
                        if "clobTokenIds" in m:
                            candidates.append({
                                "question": m.get("question", event.get("title")),
                                "slug": slug,
                                "token_ids": json.loads(m.get("clobTokenIds", "[]")),
                                "outcomes": json.loads(m.get("outcomes", "[]")),
                                "neg_risk": m.get("negRisk", False)
                            })
        except Exception as e:
            print(f"  [WARN] Fallback calc failed: {e}")
            
        if not candidates:
            print("  [INFO] No markets found matching 'BTC' + '15m'.")
            return None
            
        print(f"  [FOUND] {len(candidates)} active markets.")
        return candidates[0]

    def get_price_simple(self, token_id):
        """Fetch current BUY price (Best Ask) from CLOB simpler endpoint"""
        try:
            url = f"{HOST}/price"
            resp = requests.get(url, params={"token_id": token_id, "side": "buy"})
            if resp.status_code == 200:
                data = resp.json()
                price = float(data.get("price", 0))
                # IF price is 0, check the ORDERBOOK? 
                # Sometimes /price returns 0 if no spread?
                if price == 0:
                    return self.get_price_from_book(token_id)
                return price
        except Exception as e:
            print(f"  [WARN] /price fetch failed: {e}")
        return 0

    def get_price_from_book(self, token_id):
        """Fallback to orderbook fetch"""
        try:
            ob = self.client.get_order_book(token_id)
            if ob.asks and len(ob.asks) > 0:
                return float(ob.asks[0].price)
        except: pass
        return 0

    async def run(self):
        # 1. Fetch Market
        market = self.fetch_active_market()
        if not market:
            print("  ❌ No active markets found. Exiting.")
            return

        print("\n" + "-"*40)
        print(f"  MARKET: {market['question']}")
        print(f"  Slug:   {market['slug']}")
        print("-" * 40)
        
        # 2. Fetch Prices for ALL Outcomes
        print("  Prices (Buy / Best Ask):")
        prices = []
        for i, out in enumerate(market['outcomes']):
            if i < len(market['token_ids']):
                tid = market['token_ids'][i]
                
                # Use simple price fetcher
                price = self.get_price_simple(tid)
                prices.append(price if price > 0 else 0.99)
                
                price_str = f"${price:.3f}" if price > 0 else "N/A"
                print(f"    [{i+1}] {out.upper():<5} | Buy Price: {price_str}")
            else:
                prices.append(0)
                print(f"    [{i+1}] {out.upper():<5} | Buy Price: ???")
        
        # 3. Ask User for Side
        try:
            choice = input("\n  Enter Choice (1/2) [q to quit]: ").strip()
        except EOFError:
            return

        if choice.lower() in ['q', 'quit']: return
        if choice not in ['1', '2']:
            print("  Invalid choice.")
            return
            
        side_idx = int(choice) - 1
        if side_idx >= len(market['token_ids']):
            print("  Error: Missing token ID for this outcome.")
            return
            
        token_id = market['token_ids'][side_idx]
        outcome_label = market['outcomes'][side_idx]
        est_price = prices[side_idx]
        
        # 4. Ask Amount
        amount_input = input(f"  Amount to Buy ($): ").strip()
        if not amount_input: return
        
        amount_val = 0.0
        try:
            amount_val = float(amount_input)
            if est_price > 0:
                shares = round(amount_val / est_price, 2)
            else:
                shares = round(amount_val / 0.50, 2)
        except:
            pass
            
        print(f"\n  [PLAN] Buy ~{shares} shares of {outcome_label} for ${amount_val}")
        if input("  Execute? (y/N): ").lower() != 'y':
            print("  Cancelled.")
            return

        # 5. Execute
        order_args = OrderArgs(
            price=0.99, # Market Buy aggression
            size=shares,
            side="BUY",
            token_id=token_id
        )
        
        print("\n  [EXEC] Posting Order...")
        
        # ATTEMPT 1: neg_risk=True
        try:
            options = PartialCreateOrderOptions(neg_risk=True)
            signed = self.client.create_order(order_args, options)
            resp = await asyncio.to_thread(self.client.post_order, signed)
            print(f"  ✅ SUCCESS! Order ID: {resp.get('orderID')}")
            print(f"  {resp}")
            return
        except Exception as e:
            # print(f"  [info] neg_risk=True failed, retrying False...")
            pass

        # ATTEMPT 2: neg_risk=False
        try:
            options = PartialCreateOrderOptions(neg_risk=False)
            signed = self.client.create_order(order_args, options)
            resp = await asyncio.to_thread(self.client.post_order, signed)
            print(f"  ✅ SUCCESS! Order ID: {resp.get('orderID')}")
            print(f"  {resp}")
        except Exception as e:
            print(f"  ❌ ALL ATTEMPTS FAILED.")
            print(f"  Error: {e}")

if __name__ == "__main__":
    b = ManualBuyerV3()
    try:
        asyncio.run(b.run())
    except KeyboardInterrupt:
        print("\nExited.")
