import asyncio
import os
import sys
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, BalanceAllowanceParams

# Monkey-patch requests.Session to default to Chrome UA (Enhanced)
original_init = requests.Session.__init__
def new_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    self.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://polymarket.com/",
        "Origin": "https://polymarket.com",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site"
    })
requests.Session.__init__ = new_init

# Load .env
load_dotenv()

# --- CONSTANTS ---
CHAIN_ID = 137
HOST = "https://clob.polymarket.com"
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")

class ManualBuyer:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        self.client = None
        self.market_data = {
            "up_id": None, "down_id": None, 
            "up_price": 0.0, "down_price": 0.0,
            "btc_price": 0.0, "open_price": 0.0,
            "start_ts": 0
        }
        self.market_url = ""

    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def get_onchain_balances(self, address):
        """Standard JSON-RPC check for MATIC and USDC versions"""
        rpc_url = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
        
        # Token Contracts
        USDC_BRIDGED = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        USDC_NATIVE  = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
        
        # Helper for RPC Call
        def rpc_call(method, params):
            try:
                resp = requests.post(rpc_url, json={
                    "jsonrpc": "2.0", "method": method, "params": params, "id": 1
                }, timeout=5).json()
                return resp.get("result", "0x0")
            except: return "0x0"

        # 1. MATIC (eth_getBalance)
        matic_hex = rpc_call("eth_getBalance", [address, "latest"])
        matic_bal = int(matic_hex, 16) / 10**18
        
        # 2. USDC (eth_call balanceOf)
        # Sig: 0x70a08231 + 32-byte address
        data = "0x70a08231000000000000000000000000" + address[2:].lower()
        
        bridged_hex = rpc_call("eth_call", [{"to": USDC_BRIDGED, "data": data}, "latest"])
        bridged_bal = int(bridged_hex, 16) / 10**6
        
        native_hex = rpc_call("eth_call", [{"to": USDC_NATIVE, "data": data}, "latest"])
        native_bal = int(native_hex, 16) / 10**6
        
        return matic_bal, bridged_bal, native_bal

    def init_client(self):
        if not PRIVATE_KEY:
            self.log("CRITICAL: No PRIVATE_KEY in .env!")
            sys.exit(1)
        try:
            key_acct = Account.from_key(PRIVATE_KEY)
            # NOTE: Testing proved this private key is NOT the owner of the Proxy.
            # We MUST use signature_type=0 (EOA) with the EOA address as funder.
            # Funds need to be in the EOA wallet, not the Proxy.
            funder = key_acct.address
            
            self.client = ClobClient(
                host=HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID, 
                signature_type=0, funder=funder # 0=EOA (Direct)
            )
            creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(creds)
            self.log(f"Connected to Polymarket (EOA: {funder})")
            
            # --- DIAGNOSTICS: Check Balance & Allowance ---
            try:
                # 1. Check Primary Funder (Proxy if set, otherwise EOA)
                params = BalanceAllowanceParams(asset_type="COLLATERAL")
                bal_resp = self.client.get_balance_allowance(params)
                
                balance = float(bal_resp.get('balance', 0)) / 10**6
                
                # Check Allowances (Handle both singular and plural API responses)
                allowance = 0.0
                if 'allowance' in bal_resp: 
                    allowance = float(bal_resp['allowance']) / 10**6
                elif 'allowances' in bal_resp and bal_resp['allowances']:
                    # Take the max allowance found
                    vals = [float(x) for x in bal_resp['allowances'].values()]
                    allowance = max(vals) / 10**6

                self.log(f"--- ACCOUNT DIAGNOSTICS ---")
                self.log(f"Primary Funder: {funder} ({'PROXY' if PROXY_ADDRESS else 'EOA'})")
                self.log(f"Poly Balance:   ${balance:.2f} (USDC)")
                self.log(f"Allowance:      ${allowance:.2f}")
                
                # --- ON-CHAIN VERIFICATION ---
                self.log(f"--- ON-CHAIN DATA (Polygon RPC) ---")
                
                # Check EOA
                e_matic, e_bridged, e_native = self.get_onchain_balances(key_acct.address)
                self.log(f"EOA ({key_acct.address[:10]}...):")
                self.log(f"   MATIC:   {e_matic:.4f}")
                self.log(f"   Bridged: ${e_bridged:.2f} (This is what Polymarket uses)")
                self.log(f"   Native:  ${e_native:.2f} (Must bridge/swap to use)")
                
                if PROXY_ADDRESS:
                     p_matic, p_bridged, p_native = self.get_onchain_balances(PROXY_ADDRESS)
                     self.log(f"PROXY ({PROXY_ADDRESS[:10]}...):")
                     self.log(f"   MATIC:   {p_matic:.4f}")
                     self.log(f"   Bridged: ${p_bridged:.2f}")
                     
                     if p_bridged < 1.0 and e_bridged > 1.0:
                         self.log(f"!!! ALERT: You have funds in EOA but Proxy is empty. Send funds to {PROXY_ADDRESS} !!!")
                     if p_native > 1.0 or e_native > 1.0:
                         self.log(f"!!! ALERT: You have NATIVE USDC. You must swap it to BRIDGED USDC (Acct 0x2791...) !!!")

                if allowance < 1.0:
                    self.log(f"WARNING: Low Allowance on Primary Funder!")

            except Exception as e:
                self.log(f"Could not fetch balance: {e}")
                import traceback
                traceback.print_exc()

        except Exception as e:
            self.log(f"Client Init Error: {e}")
            sys.exit(1)

    async def fetch_current_market(self):
        # 1. Calculate Window
        now_dt = datetime.now(timezone.utc)
        minutes = now_dt.minute
        floor = (minutes // 15) * 15
        start_dt = now_dt.replace(minute=floor, second=0, microsecond=0)
        ts_start = int(start_dt.timestamp())
        self.market_url = f"https://polymarket.com/event/btc-updown-15m-{ts_start}"
        self.market_data["start_ts"] = ts_start
        
        elapsed = int(time.time() - ts_start)
        remaining = 900 - elapsed # 15m window
        self.log(f"Scanning Window: {start_dt.strftime('%H:%M')} (T-{remaining}s remaining)")
        
        # 2. Get Metadata
        slug = self.market_url.split("/")[-1]
        url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
        resp = await asyncio.to_thread(self.session.get, url)
        
        if resp.status_code != 200:
            self.log("Error fetching market metadata.")
            return

        data = resp.json()
        if "clobTokenIds" in data:
            ids = json.loads(data["clobTokenIds"])
            outcomes = json.loads(data["outcomes"])
            
            up_idx, down_idx = 0, 1
            for i, name in enumerate(outcomes):
                if "Up" in name or "Yes" in name: up_idx = i
                elif "Down" in name or "No" in name: down_idx = i
            
            self.market_data["up_id"] = ids[up_idx]
            self.market_data["down_id"] = ids[down_idx]
            
        # 3. Get Prices
        clob_url = "https://clob.polymarket.com/price"
        for side, token_id in [("UP", self.market_data["up_id"]), ("DOWN", self.market_data["down_id"])]:
            p = await asyncio.to_thread(self.session.get, clob_url, params={"token_id": token_id, "side": "buy"})
            if p.status_code == 200:
                price = float(p.json().get("price", 0))
                if side == "UP": self.market_data["up_price"] = price
                else: self.market_data["down_price"] = price

        self.log(f"UP: {self.market_data['up_price']:.3f} | DOWN: {self.market_data['down_price']:.3f}")

    async def run(self):
        print("--- Manual Buyer v1.1 (Anti-Bot Headers) ---")
        self.init_client()
        await self.fetch_current_market()
        
        print("\n--- MANUAL BUY ENTRY ---")
        try:
            side_input = input("Enter Side (UP / DOWN) [or 'q' to quit]: ").strip().upper()
            if side_input in ['Q', 'QUIT', 'EXIT']:
                print("Exiting cleanly.")
                return

            if side_input not in ["UP", "DOWN"]:
                print("Invalid side. Exiting.")
                return
            
            side = side_input

            amount_str = input("Enter Amount ($): ").strip()
            if amount_str.lower() in ['q', 'quit']:
                 print("Exiting cleanly.")
                 return
            amount = float(amount_str)

            # Execute
            token_id = self.market_data["up_id"] if side == "UP" else self.market_data["down_id"]
            current_price = self.market_data["up_price"] if side == "UP" else self.market_data["down_price"]
            
            if current_price <= 0: current_price = 0.50 # Safety
            
            # --- SMART LIMIT LOGIC (FIXED) ---
            
            # 1. Refresh Balance
            try:
                params = BalanceAllowanceParams(asset_type="COLLATERAL")
                bal_resp = self.client.get_balance_allowance(params)
                balance = float(bal_resp.get('balance', 0)) / 10**6
                self.log(f"API Balance: ${balance:.2f}")

                # FAILSAFE: If API says 0 but we know we have funds, check on-chain
                if balance <= 0.05 and PROXY_ADDRESS:
                    self.log("API reports 0. Checking On-Chain Backup...")
                    _, bridged, _ = self.get_onchain_balances(PROXY_ADDRESS)
                    if bridged > balance:
                        balance = bridged
                        self.log(f"Using On-Chain Balance: ${balance:.2f}")

            except Exception as e:
                self.log(f"Error fetching balance: {e}")
                # Last ditch effort
                if PROXY_ADDRESS:
                     _, balance, _ = self.get_onchain_balances(PROXY_ADDRESS)
                else:
                     balance = 0.0

            self.log(f"Buying Power: ${balance:.2f}")

            # User Input 'amount' = Desired Collateral to SPEND.
            # To ensure fill, we set Limit = 0.99.
            # Detailed Cost = Shares * Limit.
            # Therefore: Shares = Amount / Limit.
            
            limit_price = 0.99 # Standard "Market Buy" aggression
            shares = round(amount / limit_price, 2)
            
            # Check if we have enough balance
            if balance < amount:
                 self.log(f"WARNING: Balance (${balance:.2f}) < Desired Spend (${amount:.2f})")
                 # Adjust to max affordable
                 shares = round(balance / limit_price, 2)
                 self.log(f"   -> Adjusted to max affordable: {shares} shares")

            max_cost = shares * limit_price

            self.log(f"Executing BUY {shares} shares of {side}")
            self.log(f"   Market: {current_price:.3f} | Limit: {limit_price:.3f} | Bal: ${balance:.2f}")
            self.log(f"   Collateral Req: ${max_cost:.2f}")
            
            order = OrderArgs(
                price=limit_price, size=shares, side="BUY", token_id=token_id
            )
            resp = await asyncio.to_thread(lambda: self.client.post_order(self.client.create_order(order)))
            
            if resp and (resp.get("success") or resp.get("orderID")):
                self.log(f"SUCCESS! Order ID: {resp.get('orderID')}")
            else:
                self.log(f"FAILED: {resp.get('errorMsg')}")

        except KeyboardInterrupt:
            print("\n\nCancelled by user (Ctrl+C). Exiting cleanly.")
            return
        except Exception as e:
            self.log(f"EXCEPTION: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    t = ManualBuyer()
    try:
        asyncio.run(t.run())
    except KeyboardInterrupt:
        print("\nExited.")
