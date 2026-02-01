"""
Version 5.0
Simulator: LIVE Strong Uptrend Detection Strategy (Paper Trader)

This script simulates a "Strong Uptrend Detection" strategy in REAL-TIME using live Polymarket/Binance data.
It continuously scans prices from minute 5-9 and executes a trade when a strong uptrend is detected.

Features:
- Real-Time Data Fetching (Polymarket + Binance)
- Robust Opening Price Logic (from bot_trend_t9_LIVE.py)
- Continuous 5-Second Sampling (T+5 to T+9)
- Strong Uptrend Detection (momentum-based)
- Global Price Cap (< 0.85)
"""
import requests
import time
import json
import asyncio
import sys
from datetime import datetime, timezone, timedelta
import os

# --- Configuration ---
DRIFT_THRESHOLD = 0.0004
STATE_FILE = "sim_live_linear_state.json"
LOG_FILE = "sim_live_linear_log.txt"

def print_status(msg, log_to_file=False):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    if log_to_file:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")

class LiveLinearSimulator:
    def __init__(self, balance):
        self.balance = float(balance)
        self.session = requests.Session()
        
        # State
        self.is_running = True
        self.market_url = ""
        self.active_trade = None
        self.strategy_triggered = False
        self.checkpoints = {} # {second: price}
        
        # Data
        self.btc_offset = -86.0
        self.auto_offset = True
        self.last_offset_update = 0
        self.market_data = {
            "up_id": None, "down_id": None, 
            "up_price": 0.0, "down_price": 0.0,
            "btc_price": 0.0, 
            "open_price": 0.0,
            "start_ts": 0, "end_ts": 0
        }

    # --- Data Fetching (Reusable) ---
    def safe_load(self, val, default):
        if isinstance(val, (list, dict)): return val
        try: return json.loads(val)
        except: return default

    async def fetch_coingecko_price(self):
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
            resp = await asyncio.to_thread(self.session.get, url, timeout=3.0)
            return float(resp.json()['bitcoin']['usd'])
        except: return 0.0

    async def fetch_coinbase_price(self):
        try:
            url = "https://api.coinbase.com/v2/prices/BTC-USD/spot"
            resp = await asyncio.to_thread(self.session.get, url, timeout=3.0)
            data = resp.json()
            return float(data['data']['amount'])
        except Exception as e:
            return 0.0

    async def get_coinbase_open(self, timestamp_ms):
        try:
            # Coinbase Exchange API (Candles)
            # granularity=60 (1 minute)
            # start/end must be ISO 8601
            ts_sec = timestamp_ms / 1000
            start_iso = datetime.fromtimestamp(ts_sec, tz=timezone.utc).isoformat()
            end_iso = datetime.fromtimestamp(ts_sec + 60, tz=timezone.utc).isoformat()
            
            url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
            params = {
                "start": start_iso,
                "end": end_iso,
                "granularity": 60
            }
            # Headers often needed for Coinbase
            headers = {"User-Agent": "PolySim/1.0"}
            
            resp = await asyncio.to_thread(self.session.get, url, params=params, headers=headers, timeout=3.0)
            data = resp.json()
            # Response: [ [ time, low, high, open, close, volume ], ... ]
            if data and isinstance(data, list) and len(data) > 0:
                # Coinbase returns newest first.
                return float(data[-1][3]) # Index 3 is Open
        except Exception as e:
            # print(f"Coinbase Hist Error: {e}")
            pass
        return 0.0

    async def get_historical_open(self, timestamp_ms):
        # 1. Try Binance
        try:
            url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={timestamp_ms}&limit=1"
            resp = await asyncio.to_thread(self.session.get, url, timeout=2)
            data = resp.json()
            if data and len(data) > 0:
                return float(data[0][1]) + self.btc_offset
        except: 
            pass
            
        # 2. Try Coinbase (Fallback)
        op = await self.get_coinbase_open(timestamp_ms)
        if op > 0: return op # No offset needed for Coinbase usually, or assume relative? 
                             # Actually self.btc_offset is for Binance<->CoinGecko drift. 
                             # Coinbase is usually close to "True" USD.
                             # For safety, let's just return raw Coinbase open.
        
        return 0.0

    async def fetch_spot_price(self):
        price = 0.0
        source = "Binance"
        
        # 1. Try Binance
        try:
            url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
            resp = await asyncio.to_thread(self.session.get, url, timeout=2.0)
            data = resp.json()
            if "price" in data:
                price = float(data["price"])
        except Exception as e:
            # print(f"Binance Error: {e}") 
            pass

        # 2. Try Coinbase (Fallback)
        if price == 0:
            source = "Coinbase"
            price = await self.fetch_coinbase_price()
            
        # 3. Try CoinGecko (Last Resort)
        if price == 0:
            source = "CoinGecko"
            price = await self.fetch_coingecko_price()

        # Update State
        if price > 0:
            # If we used Coinbase/Gecko, maybe we don't apply the 'btc_offset' if it was calculated for Binance?
            # But the offset is (CoinGecko - Binance). 
            # If Source == Coinbase, it's likely already close to CoinGecko.
            # Let's apply offset only if Binance? No, simplicity first.
            final_price = price + (self.btc_offset if source == "Binance" else 0.0)
            
            self.market_data["btc_price"] = final_price
            
            # Logic: Fetch & Cache Open Price
            if self.market_data["open_price"] == 0 and self.market_data["start_ts"] > 0:
                 op = await self.get_historical_open(self.market_data["start_ts"] * 1000)
                 if op > 0: 
                     self.market_data["open_price"] = op
                     print_status(f"OPEN PRICE CACHED (via Hist): {op:,.2f}")
                 elif (time.time() - self.market_data["start_ts"]) < 300: # Expanded to 5 mins
                     self.market_data["open_price"] = final_price
                     print_status(f"OPEN PRICE SET (LIVE FALLBACK): {final_price:,.2f}")
        else:
             print_status(f"CRITICAL: Failed to fetch BTC price from all sources.", log_to_file=True)

    async def fetch_market_data(self):
        # 1. Get Token IDs
        if not self.market_data["up_id"] and self.market_url:
            try:
                slug = self.market_url.split("/")[-1].split("?")[0]
                url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
                resp = await asyncio.to_thread(self.session.get, url, timeout=2.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if "clobTokenIds" in data:
                        ids = self.safe_load(data["clobTokenIds"], [])
                        # Robust mapping (Default or by Name)
                        up_id, down_id = None, None
                        if len(ids) >= 2:
                            up_id, down_id = ids[0], ids[1] # Default
                            
                        # Try name mapping
                        outcomes = self.safe_load(data.get("outcomes", "[]"), [])
                        if len(outcomes) >= 2:
                            for i, name in enumerate(outcomes):
                                if "Up" in name or "Yes" in name: up_id = ids[i]
                                elif "Down" in name or "No" in name: down_id = ids[i]
                        
                        self.market_data["up_id"] = up_id
                        self.market_data["down_id"] = down_id
            except: pass

        # 2. Get Prices
        if self.market_data["up_id"]:
            try:
                clob_url = "https://clob.polymarket.com/price"
                p1 = await asyncio.to_thread(self.session.get, clob_url, params={"token_id": self.market_data["up_id"], "side": "buy"})
                p2 = await asyncio.to_thread(self.session.get, clob_url, params={"token_id": self.market_data["down_id"], "side": "buy"})
                
                r1, r2 = p1.json(), p2.json()
                if "price" in r1: self.market_data["up_price"] = float(r1["price"])
                if "price" in r2: self.market_data["down_price"] = float(r2["price"])
            except: pass

    # --- Core Loop ---
    async def run(self):
        print(f"--- LIVE SIMULATOR: STRONG UPTREND DETECTION ---")
        print(f"Starting Balance: ${self.balance:.2f}")
        print("Calibrating Offset...")
        await self.fetch_spot_price()
        print(f"Offset: {self.btc_offset:.2f}")
        print_status(f"STARTUP | Balance: ${self.balance:.2f} | Offset: {self.btc_offset:.2f}", log_to_file=True)

        while self.is_running:
            try:
                # 1. Window Calculation
                now = datetime.now(timezone.utc)
                min15 = (now.minute // 15) * 15
                start_dt = now.replace(minute=min15, second=0, microsecond=0)
                ts_start = int(start_dt.timestamp())
                url = f"https://polymarket.com/event/btc-updown-15m-{ts_start}"

                # 2. Reset on New Window
                if url != self.market_url:
                    if self.market_url != "":
                        # Settle Previous
                        await self.settle_window()
                        
                    self.market_url = url
                    print(f"\n>> NEW WINDOW: {start_dt.strftime('%H:%M')} <<")
                    print(f"Monitoring: {self.market_url}")
                    print_status(f"NEW WINDOW: {start_dt.strftime('%H:%M')} | {self.market_url}", log_to_file=True)
                    
                    # Reset Data
                    btc_p = self.market_data["btc_price"]
                    self.market_data = {
                        "up_id": None, "down_id": None, 
                        "up_price": 0.0, "down_price": 0.0,
                        "btc_price": btc_p, 
                        "open_price": 0.0,
                        "start_ts": ts_start, "end_ts": ts_start + 900
                    }
                    self.checkpoints = {}
                    self.active_trade = None
                    self.strategy_triggered = False

                # 3. Fetch Data
                await self.fetch_spot_price()
                await self.fetch_market_data()

                # 4. Sampling & Strategy
                elapsed = int(time.time() - ts_start)
                
                # Update Status Line
                self.print_status_line(elapsed)

                if self.market_data["open_price"] > 0:
                     await self.process_strategy(elapsed)

                # 5. Smart Sleep (Aim for 5s intervals)
                await asyncio.sleep(5)

            except KeyboardInterrupt: break
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(5)

    def calculate_bollinger_edge(self):
        """
        Calculate if current price is at Bollinger Band edge.
        Returns True if price is within 10% of upper or lower band.
        Uses 20-period simple moving average with 2 standard deviations.
        """
        if len(self.checkpoints) < 20:
            return False  # Not enough data for Bollinger Bands
        
        # Get sorted price history
        checkpoint_times = sorted(self.checkpoints.keys())
        prices = [self.checkpoints[t] for t in checkpoint_times]
        
        # Use last 20 samples for calculation
        recent_prices = prices[-20:]
        current_price = recent_prices[-1]
        
        # Calculate Simple Moving Average (SMA)
        sma = sum(recent_prices) / len(recent_prices)
        
        # Calculate Standard Deviation
        variance = sum((p - sma) ** 2 for p in recent_prices) / len(recent_prices)
        std_dev = variance ** 0.5
        
        # Bollinger Bands: SMA ± 2*StdDev
        upper_band = sma + (2 * std_dev)
        lower_band = sma - (2 * std_dev)
        
        # Calculate band width for edge detection (10% threshold)
        band_width = upper_band - lower_band
        edge_threshold = band_width * 0.10
        
        # Check if price is at upper or lower edge
        at_upper_edge = current_price >= (upper_band - edge_threshold)
        at_lower_edge = current_price <= (lower_band + edge_threshold)
        
        is_at_edge = at_upper_edge or at_lower_edge
        
        # Log for debugging
        if is_at_edge:
            edge_type = "UPPER" if at_upper_edge else "LOWER"
            print_status(f"  [BOLLINGER] At {edge_type} edge | Price: {current_price:.3f} | Bands: [{lower_band:.3f}, {upper_band:.3f}]", log_to_file=True)
        
        return is_at_edge

    def print_status_line(self, elapsed):
        btc = self.market_data["btc_price"]
        op = self.market_data["open_price"]
        up = self.market_data["up_price"]
        dn = self.market_data["down_price"]
        
        drift = 0.0
        if op > 0: drift = abs(btc - op) / op
        
        trade_str = f"ACTIVE ({self.active_trade['type']})" if self.active_trade else "WAITING"
        t_str = f"T+{elapsed // 60}:{elapsed % 60:02d}"
        
        print(f"\r[{t_str}] BTC: {btc:,.1f} | OPEN: {op:,.1f} | UP: {up:.2f} DN: {dn:.2f} | Drift: {drift:.4%} | {trade_str}   ", end="", flush=True)

    async def process_strategy(self, elapsed):
        if self.strategy_triggered: return
        
        btc = self.market_data["btc_price"]
        op = self.market_data["open_price"]
        
        # Determine Leader
        leader_side = "UP" if btc > op else "DOWN"
        leader_price = self.market_data["up_price"] if leader_side == "UP" else self.market_data["down_price"]
        
        # --- CONTINUOUS SAMPLING (Every 5s from T+5:00 to T+9:00) ---
        # Only track during the scanning window (300s to 540s)
        if 300 <= elapsed <= 540:
            # Store checkpoint with elapsed time as key
            if elapsed not in self.checkpoints:
                self.checkpoints[elapsed] = leader_price
                print_status(f"  [Scan T+{elapsed}s] {leader_side} @ {leader_price:.2f}", log_to_file=True)
        
        # --- STRONG UPTREND DETECTION ---
        drift = abs(btc - op) / op
        
        # Only analyze during scanning window (T+5:00 to T+9:00)
        if 300 <= elapsed <= 540 and not self.active_trade:
            # Need at least 3 data points (spanning 60+ seconds) to detect uptrend
            checkpoint_times = sorted(self.checkpoints.keys())
            
            if len(checkpoint_times) >= 3:
                # Get recent history (last 60-90 seconds)
                recent_times = [t for t in checkpoint_times if elapsed - t <= 90]
                
                if len(recent_times) >= 3:
                    recent_prices = [self.checkpoints[t] for t in recent_times]
                    
                    # Calculate momentum: price change over the period
                    price_start = recent_prices[0]
                    price_current = recent_prices[-1]
                    momentum = price_current - price_start
                    
                    # Check for consistency: count consecutive rising samples
                    consecutive_rises = 0
                    max_consecutive = 0
                    for i in range(1, len(recent_prices)):
                        if recent_prices[i] > recent_prices[i-1]:
                            consecutive_rises += 1
                            max_consecutive = max(max_consecutive, consecutive_rises)
                        else:
                            consecutive_rises = 0
                    
                    # Calculate velocity (acceleration): compare recent vs earlier momentum
                    if len(recent_times) >= 6:
                        mid_point = len(recent_times) // 2
                        early_momentum = recent_prices[mid_point] - recent_prices[0]
                        late_momentum = recent_prices[-1] - recent_prices[mid_point]
                        is_accelerating = late_momentum >= early_momentum * 0.8  # Allow slight deceleration
                    else:
                        is_accelerating = True  # Not enough data, assume neutral
                    
                    # --- UPTREND CRITERIA ---
                    # 1. Strong momentum: price increased by at least 0.10 (10 cents)
                    # 2. Consistency: at least 2 consecutive rising samples
                    # 3. Velocity: maintaining or accelerating
                    # 4. Standard checks: drift, price caps
                    
                    has_strong_momentum = momentum >= 0.10
                    has_consistency = max_consecutive >= 2
                    
                    if (has_strong_momentum and 
                        has_consistency and 
                        is_accelerating and
                        drift > DRIFT_THRESHOLD and 
                        leader_price < 0.85 and 
                        leader_price > 0.10):
                        
                        # STRONG UPTREND DETECTED - EXECUTE IMMEDIATELY
                        self.execute_trade("UPTREND", leader_side, leader_price, 0.20)
                        print_status(f"  [STRONG UPTREND DETECTED] Momentum: +{momentum:.3f} | Consecutive: {max_consecutive} | History: {recent_prices}", log_to_file=True)
                    
                    # Log near-misses for analysis (every 30 seconds)
                    elif elapsed % 30 == 0:
                        reason = []
                        if not has_strong_momentum: reason.append(f"Weak Momentum ({momentum:+.3f})")
                        if not has_consistency: reason.append(f"Inconsistent (Max {max_consecutive} rises)")
                        if not is_accelerating: reason.append("Decelerating")
                        if drift <= DRIFT_THRESHOLD: reason.append(f"Drift Low ({drift:.4%})")
                        if leader_price >= 0.85: reason.append(f"Price High ({leader_price:.2f})")
                        if reason:
                            print_status(f"  [T+{elapsed}s NO SIGNAL] {', '.join(reason)}", log_to_file=True)
        
        # --- FALLBACK: T+9 (540s) if no uptrend detected ---
        if 540 <= elapsed <= 550 and not self.active_trade:
            # Check if at Bollinger Band edge
            at_bb_edge = self.calculate_bollinger_edge()
            
            # Determine price threshold based on Bollinger Band position
            # If at BB edge: allow entry at price > 0.55
            # Otherwise: require price > 0.80 (more conservative)
            if at_bb_edge:
                min_price = 0.55
                reason_suffix = "at BB edge"
            else:
                min_price = 0.80
                reason_suffix = "not at BB edge"
            
            # Apply the conditional logic
            if (drift > DRIFT_THRESHOLD and 
                leader_price >= min_price and 
                leader_price < 0.85 and 
                leader_price > 0.10):
                
                self.execute_trade("FALLBACK-T9", leader_side, leader_price, 0.10)
                print_status(f"  [FALLBACK T+9] Entry at {leader_price:.2f} ({reason_suffix})", log_to_file=True)
            elif elapsed == 540:
                reason = []
                if drift <= DRIFT_THRESHOLD: reason.append(f"Drift Low ({drift:.4%})")
                if leader_price >= 0.85: reason.append(f"Price Too High ({leader_price:.2f})")
                if leader_price < min_price: reason.append(f"Price Below Threshold ({leader_price:.2f} < {min_price:.2f}, {reason_suffix})")
                print_status(f"  [T+9 SKIP] {', '.join(reason)}", log_to_file=True)

    def execute_trade(self, type_name, side, price, budget_pct):
        cost = min(50.0, self.balance * budget_pct)
        cost = max(5.50, cost)  # Enforce Polymarket minimum
        
        # Skip trade if balance insufficient
        if cost > self.balance:
            print_status(f"SKIP: Insufficient balance (${self.balance:.2f} < ${cost:.2f})", log_to_file=True)
            return
            
        shares = cost / price
        self.balance -= cost
        
        self.active_trade = {
            "type": type_name,
            "side": side,
            "entry": price,
            "shares": shares,
            "cost": cost
        }
        self.strategy_triggered = True 
        print(f"\n\n>>> TRADE EXECUTED: {type_name} <<<")
        print(f"Side: {side} | Price: {price:.3f} | Cost: ${cost:.2f}")
        print_status(f"Entered {type_name} ({side}) @ {price:.3f}", log_to_file=True)

    async def settle_window(self):
        if not self.active_trade: return
        
        # Determine Winner logic
        btc = self.market_data["btc_price"]
        op = self.market_data["open_price"]
        
        if op == 0:
            print("Warning: No Open Price. Assuming Refund/No Action.")
            return

        winner = "UP" if btc > op else "DOWN"
        side = self.active_trade["side"]
        
        print(f"\n--- SETTLEMENT ---")
        print(f"Final BTC: {btc:,.1f} | Open: {op:,.1f} -> Winner: {winner}")
        
        if side == winner:
            payout = self.active_trade["shares"]
            profit = payout - self.active_trade["cost"]
            self.balance += payout
            print(f"RESULT: WIN! Payout: ${payout:.2f} (Profit: ${profit:.2f})")
            print_status(f"WIN: +${profit:.2f} | Bal: ${self.balance:.2f}", log_to_file=True)
        else:
            print(f"RESULT: LOSS. -${self.active_trade['cost']:.2f}")
            print_status(f"LOSS: -${self.active_trade['cost']:.2f} | Bal: ${self.balance:.2f}", log_to_file=True)
            
        print(f"New Balance: ${self.balance:.2f}")
        print("------------------")



if __name__ == "__main__":
    try:
        val = input("Enter Starting Balance [50.0]: ").strip()
        bal = float(val) if val else 50.0
        
        sim = LiveLinearSimulator(bal)
        asyncio.run(sim.run())
    except KeyboardInterrupt:
        print("\nSimulator Stopped.")
