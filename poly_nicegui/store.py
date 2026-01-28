from nicegui import ui, run
import json
import requests
import asyncio
import market_analysis
import strategies
import os
from dotenv import load_dotenv
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from datetime import datetime
import time

load_dotenv()
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
CHAIN_ID = 137
HOST = "https://clob.polymarket.com"

class Store:
    def __init__(self):
        self.url = ""
        self.market_data = {} # {up_id, down_id, up_token, down_token, ...}
        self.analysis_results = {}
        self.active_position = None 
        self.is_analyzing = False
        self.btc_offset = -86.0 
        self.btc_offset = -86.0 
        self.refresh_rate = 2.0 
        self.trading_side = "UP" # UI State for Lever/SL Sync
        
        # Stop Loss State
        self.sl_active = False
        self.sl_token_id = None
        self.sl_trigger_price = 0.0
        # Stop Loss State
        self.sl_active = False
        self.sl_token_id = None
        self.sl_trigger_price = 0.0
        self.sl_size = 0.0
        self.sl_side = "up" # For UI display
        self.sl_trailing = False
        self.sl_trail_dist = 0.05
        
        # Strategy State
        self.strategy_reversion_active = False
        self.strategy_trend_active = False
        self.strategy_bracket_active = False # Bracket Bot (Auto SL/TP)
        self.bracket_tp_pct = 0.20
        self.bracket_sl_pct = 0.10
        self.last_auto_trade_ts = 0
        
        self.session = requests.Session()
        self.clob_api = "https://clob.polymarket.com"
        self.client = self._init_client()
        
        # Start Background Loop manually in main.py
        self.loop_running = False
        
    async def background_loop(self):
        if self.loop_running: return
        self.loop_running = True
        print("DEBUG: Background Loop Started")
        
        try:
            while True:
                try:
                    if self.url:
                        await self.fetch_option_prices()
                        await self.fetch_spot_price()
                        # Check Stop Loss
                        await self.check_stop_loss()
                        
                        # Check Strategies
                        await self.evaluate_strategies()
                        
                        # CSV Logging
                        up = self.market_data.get("up_price", 0)
                        down = self.market_data.get("down_price", 0)
                        btc = self.market_data.get("btc_price", 0)
                        if btc > 0: btc += self.btc_offset
                        strike = self.analysis_results.get("strike_price", 0)
                        div = btc - strike if (btc > 0 and strike > 0) else 0
                        
                        # Time Remaining
                        end_ts = self.analysis_results.get('end_ts')
                        time_str = "T-?:??"
                        if end_ts:
                            seconds = max(0, end_ts - datetime.now().timestamp())
                            mins, secs = divmod(int(seconds), 60)
                            time_str = f"T-{mins}:{secs:02}"
                        
                        print(f"CSV: {time_str}, UP={up:.3f}, DOWN={down:.3f}, BTC={btc:.2f}, STRIKE={strike:.2f}, DIV={div:.2f}")

                        # Auto-Switch Market Check
                        # If time_left is defined and < -10 (10s buffer after close)
                        if self.analysis_results:
                            tl = self.analysis_results.get('time_left_s', 999)
                            # If expired (tl <= 0). Give it a moment to clear.
                            # Or if user just wants next one immediately? 
                            # Let's say if expired.
                            if tl == 0 and self.url:
                                 # Trigger search (throttled?)
                                 # We don't want to spam requests.
                                 # Check if we already tried?
                                 pass 
                                 
                                 # Actually, we should check periodically.
                                 # Let's check every 10s if expired?
                                 if int(time.time()) % 10 == 0:
                                     print("DEBUG: Market Expired. Searching for next...")
                                     next_url = await run.io_bound(market_analysis.find_next_btc_market, self.url)
                                     if next_url and next_url != self.url:
                                         self.set_url(next_url)
                                         self.safe_notify(f"🔄 Auto-Switched to Next Market!", "positive")
                                         
                except Exception as e:
                    import traceback
                    # Ignore "parent element" errors which are just UI disconnects
                    if "parent element" not in str(e):
                        # print(f"DEBUG: Loop Error: {e}")
                        # print(traceback.format_exc())
                        pass
                
                await asyncio.sleep(self.refresh_rate)
        except asyncio.CancelledError:
            print("DEBUG: Background Loop Cancelled")
        finally:
            self.loop_running = False
            print("DEBUG: Background Loop Stopped")
            
    def safe_notify(self, msg, type='info', close=False):
        try:
            if type == 'info': ui.notify(msg, color='info', close_button=close)
            elif type == 'positive': ui.notify(msg, color='positive', close_button=close)
            elif type == 'negative': ui.notify(msg, color='negative', close_button=close)
            elif type == 'warning': ui.notify(msg, color='warning', close_button=close)
            else: ui.notify(msg, close_button=close)
        except Exception as e:
            # Squelch UI errors in background loop
            pass
        
    def _init_client(self):
        if not PRIVATE_KEY: 
            print("DEBUG: No PRIVATE_KEY found")
            return None
        try:
            # Init with Proxy Support
            funder = PROXY_ADDRESS if PROXY_ADDRESS else Account.from_key(PRIVATE_KEY).address
            print(f"DEBUG: Initializing Client with funder: {funder}")
            
            client = ClobClient(host=HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID, signature_type=1, funder=funder)
            creds = client.create_or_derive_api_creds()
            client.set_api_creds(creds)
            return client
        except Exception as e:
            print(f"DEBUG: Client Init Error: {e}")
            return None
        
    def safe_load(self, val, default):
        if isinstance(val, (list, dict)): return val
        try:
            return json.loads(val)
        except:
            return default
        
    def set_url(self, url):
        if url != self.url:
            self.url = url
            self.market_data = {} # Clear old token IDs/prices
            self.analysis_results = {} # Clear old analysis
            print(f"DEBUG: URL changed to {url}. State reset.")
        
    async def run_analysis(self):
        print(f"DEBUG: Starting analysis for {self.url}")
        if not self.url: 
            print("DEBUG: No URL provided")
            return
        self.is_analyzing = True
        
        try:
            # Run in executor to avoid blocking main thread
            print("DEBUG: Calling market_analysis.analyze_market_data...")
            results = await run.io_bound(market_analysis.analyze_market_data, self.url, self.btc_offset)
            print(f"DEBUG: Results received: {results.keys() if results else 'None'}")
            self.analysis_results = results
        except asyncio.CancelledError:
            print("DEBUG: Analysis cancelled")
            return
        except Exception as e:
            print(f"DEBUG: Analysis Error: {e}")
            self.analysis_results = {"recommendation": f"Error: {str(e)}"}
            
        self.is_analyzing = False
        
    async def fetch_option_prices(self):
        if not self.url: return
        
        try:
            # 1. Metadata Check (Need Token IDs)
            if "up_id" not in self.market_data:
                 slug = self.url.strip("/").split("?")[0].split("/")[-1]
                 gamma_url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
                 
                 def _get_meta():
                     return self.session.get(gamma_url, timeout=2).json()
                 
                 data = await run.io_bound(_get_meta)
                 if not data: return
                 
                 outcomes = self.safe_load(data.get("outcomes"), [])
                 clob_ids = self.safe_load(data.get("clobTokenIds"), [])
                 prices = self.safe_load(data.get("outcomePrices"), []) # Initial fallback
                 
                 up_idx, down_idx = 0, 1
                 for i, name in enumerate(outcomes):
                    if str(name).lower() in ["up", "yes", "higher"]: up_idx = i
                    if str(name).lower() in ["down", "no", "lower"]: down_idx = i
                 
                 self.market_data["up_id"] = clob_ids[up_idx] if len(clob_ids) > up_idx else None
                 self.market_data["down_id"] = clob_ids[down_idx] if len(clob_ids) > down_idx else None
                 self.market_data["up_label"] = outcomes[up_idx] if len(outcomes) > up_idx else "Up"
                 self.market_data["down_label"] = outcomes[down_idx] if len(outcomes) > down_idx else "Down"
                 
                 # Set initial fallback prices
                 self.market_data["up_price"] = float(prices[up_idx]) if len(prices) > up_idx else 0.0
                 self.market_data["down_price"] = float(prices[down_idx]) if len(prices) > down_idx else 0.0

            # 2. CLOB Live Prices (Real-Time)
            if self.market_data.get("up_id"):
                def _get_clob():
                    # Fetch UP Price
                    p1 = self.session.get(f"{self.clob_api}/price", params={"token_id": self.market_data.get("up_id"), "side": "buy"}, timeout=1)
                    # Fetch DOWN Price
                    p2 = self.session.get(f"{self.clob_api}/price", params={"token_id": self.market_data.get("down_id"), "side": "buy"}, timeout=1)
                    return p1.json(), p2.json()

                res = await run.io_bound(_get_clob)
                if res and len(res) == 2:
                    r1, r2 = res
                    
                    # Update with FRESH prices
                    if "price" in r1: self.market_data["up_price"] = float(r1["price"])
                    if "price" in r2: self.market_data["down_price"] = float(r2["price"])
                
                # print(f"DEBUG: CLOB Update -> UP: {self.market_data['up_price']} | DOWN: {self.market_data['down_price']}")
                # Only log if price changed significantly
                pass

        except asyncio.CancelledError:
            return
        except Exception as e:
            print(f"DEBUG: Price Fetch Error: {e}")
            
    async def fetch_spot_price(self):
        try:
            # Binance is usually fastest for spot
            api_url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
            
            def _get():
                try:
                    return self.session.get(api_url, timeout=1).json()
                except:
                    return None
            
            data = await run.io_bound(_get)
            if data and "price" in data:
                self.market_data["btc_price"] = float(data["price"])
        except Exception as e:
            print(f"DEBUG: Spot Fetch Error: {e}")

    async def check_stop_loss(self):
        if not self.sl_active or not self.sl_token_id: return

        # Find current price for the watched token
        # We need to know if it's UP or DOWN token to check market_data
        curr_price = 0.0
        if self.sl_token_id == self.market_data.get("up_id"):
            curr_price = self.market_data.get("up_price", 0.0)
        elif self.sl_token_id == self.market_data.get("down_id"):
            curr_price = self.market_data.get("down_price", 0.0)
            
        if curr_price <= 0: return # Data not ready
        
        # print(f"DEBUG: SL Check: {curr_price} vs {self.sl_trigger_price}")
        
        # Trailing Logic
        if self.sl_trailing:
             new_trigger = round(curr_price - self.sl_trail_dist, 2)
             if new_trigger > self.sl_trigger_price:
                 old = self.sl_trigger_price
                 self.sl_trigger_price = new_trigger
                 self.safe_notify(f"📈 Trailing SL Moved Up: ${old} -> ${new_trigger}", "positive")
        
        if curr_price <= self.sl_trigger_price:
            self.safe_notify(f"🚨 STOP LOSS TRIGGERED! Selling...", "negative", close=True)
            print(f"\n!!! SL TRIGGERED !!!")
            print(f"Current: ${curr_price} <= Trigger: ${self.sl_trigger_price}")
            
            # Execute Sell
            await self.place_trade_sell(self.sl_token_id, self.sl_size)
            
            # Deactivate
            self.sl_active = False
            self.sl_active = False
            self.safe_notify("🛡️ Stop Loss Executed & Disabled", "warning")

    async def evaluate_strategies(self):
        # Lazy Init check
        if not hasattr(self, 'last_auto_trade_ts'): self.last_auto_trade_ts = 0
        
        # Prevent rapid firing (1 trade per minute per strategy?)
        if time.time() - self.last_auto_trade_ts < 60: return
        
        signal_side = None
        strategy_name = ""
        
        # 1. Reversion Master
        if self.strategy_reversion_active:
            sig = strategies.check_reversion(self.analysis_results)
            if sig:
                signal_side = sig
                strategy_name = "Reversion Master"
                
        # 2. Trend Surfer (Priority? Or Mutually Exclusive?)
        # Let's say Reversion takes priority if active, else Trend
        if not signal_side and self.strategy_trend_active:
            sig = strategies.check_trend_surfer(self.analysis_results)
            if sig:
                signal_side = sig
                strategy_name = "Trend Surfer"
                
        if signal_side:
            print(f"DEBUG: Strategy Signal: {strategy_name} -> {signal_side}")
            # Execute Trade (Small size for safety initially?)
            # Use self.sl_size or a dedicated strategy size? using sl_size for consistency
            size = self.sl_size if self.sl_size > 0 else 5.0
            
            self.last_auto_trade_ts = time.time()
            self.safe_notify(f"🤖 {strategy_name} Triggered! Buying {signal_side}...", "info")
            await self.place_trade(signal_side, size)

    async def place_trade_sell(self, token_id, size):
        if not self.client: return
        # Critical Safety Function - must be robust
        try:
           def _sell():
               # Market Sell (Limit 0.01)
               args = OrderArgs(price=0.01, size=size, token_id=token_id, side="SELL")
               return self.client.post_order(self.client.create_order(args))
           
           print(f"DEBUG: Attempting Auto-Sell for {size} shares...")
           res = await run.io_bound(_sell)
           
           if res.get("success"):
               ui.notify(f"✅ Auto-Sell Success! ID: {res.get('orderID')}", color="positive")
               print(f"DEBUG: Sell Success: {res.get('orderID')}")
           else:
               ui.notify(f"❌ Auto-Sell Failed: {res.get('errorMsg')}", color="negative")
               print(f"DEBUG: Sell Failed: {res}")
               
        except Exception as e:
             err_msg = f"❌ Sell Exception: {str(e)}"
             self.safe_notify(err_msg, "negative")
             print(f"CRITICAL: {err_msg}")
            
    async def place_trade(self, side, size):
        if not self.client:
            ui.notify("Error: CLOB Client not initialized (Check .env)", color="negative")
            return
            
        token_id = self.market_data.get(f"{side}_id")
        if not token_id:
            ui.notify("Error: Token ID not found. Wait for prices to load.", color="negative")
            return
            
        ui.notify(f"Buying {size} shares of {side.upper()}...", color="info")
        
        try:
            # Run in thread
            def _trade():
                buy_args = OrderArgs(price=0.99, size=size, token_id=token_id, side="BUY")
                resp = self.client.create_order(buy_args)
                return self.client.post_order(resp)
            
            res = await run.io_bound(_trade)
            
            if res.get("success"):
                ui.notify(f"✅ Executed! ID: {res.get('orderID')}", color="positive")
                
                # Auto-Activate Stop Loss
                self.sl_side = side
                self.sl_token_id = token_id
                self.sl_size = float(size)
                # Estimate entry price (optimistic 0.99 fill or use market data)
                # Better: use current LIVE price from market_data - 0.05 safety
                curr = self.market_data.get(f"{side}_price", 0.0)
                if curr > 0:
                     self.sl_trigger_price = max(0.01, round(curr - 0.05, 2))
                else:
                     self.sl_trigger_price = 0.02 # Fallback
                     
                self.sl_active = True
                self.sl_trailing = True # Auto-enable trailing
                self.sl_trail_dist = 0.05
                ui.notify(f"🛡️ Auto-SL Active @ ${self.sl_trigger_price} (Trailing)", color="warning")
                
                # BRACKET BOT LOGIC
                if self.strategy_bracket_active:
                     # Calculate SL/TP
                     # Note: Auto-SL above sets SL. Bracket Bot overrides it with configurable %
                     # Entry Price Estimate
                     entry = self.market_data.get(f"{side}_price", 0.0)
                     if entry > 0:
                         tp, sl = strategies.calculate_bracket_orders(entry, side, self.bracket_tp_pct, self.bracket_sl_pct)
                         
                         # Update SL State
                         self.sl_trigger_price = sl
                         self.sl_active = True # Ensure active
                         self.safe_notify(f"🤖 Bracket Bot: TP ${tp} | SL ${sl}", "info")
                         
                         # Place Limit Sell for TP?
                         # For now, just notifying TP. Implementing Auto-Limit Sell requires Order ID tracking or open order check.
                         # Let's just create a 'Pending TP' state or just place the limit order immediately?
                         # Placing limit order immediately might lock funds/shares.
                         # Let's place it!
                         # await self.place_limit_sell(token_id, size, tp) # TODO: Implement place_limit_sell
                         
                         ui.notify(f"🎯 Bracket Targets Set: TP ${tp} / SL ${sl}", color="positive")
                         
                     else:
                         ui.notify("⚠️ Bracket Bot: Could not determine entry price.", color="warning")
                
            else:
                ui.notify(f"❌ Failed: {res.get('errorMsg')}", color="negative")
                
        except Exception as e:
            self.safe_notify(f"❌ Trade Exception: {str(e)}", "negative")
        
    def get_price_labels(self):
        # Fallback
        return "Up", "Down"

# Global Store Instance
state = Store()
