"""
Version 5.1 (v2)
Simulator: LIVE Strong Uptrend Detection Strategy with BB Position Sizing

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
import csv


# --- Configuration ---
DRIFT_THRESHOLD = 0.0004
STATE_FILE = "sim_live_linear_v2_state.json"
# LOG_FILE will be set dynamically with timestamp in __init__

def print_status(msg, log_to_file=False, log_file=None):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    if log_to_file and log_file:
        with open(log_file, "a") as f:
            f.write(line + "\n")

class LiveLinearSimulator:
    def __init__(self, balance, use_bb_sizing=True):
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
        self.use_bb_sizing = use_bb_sizing  # Toggle for BB-based position sizing
        
        # Logging (timestamped filenames)
        timestamp_str = datetime.now().strftime('%Y-%b-%d_%H-%M-%S')
        self.log_file = f"sim_live_v2_log_{timestamp_str}.txt"
        self.csv_file = None
        self.csv_writer = None
        self.csv_filename = f"sim_live_v2_detailed_{timestamp_str}.csv"

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
             print_status(f"CRITICAL: Failed to fetch BTC price from all sources.", log_to_file=True, log_file=self.log_file)

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
        mode_str = "BB-Weighted" if self.use_bb_sizing else "Fixed Size"
        print(f"--- LIVE SIMULATOR: STRONG UPTREND DETECTION ({mode_str}) ---")
        print(f"Starting Balance: ${self.balance:.2f}")
        print("Calibrating Offset...")
        await self.fetch_spot_price()
        print(f"Offset: {self.btc_offset:.2f}")
        print_status(f"STARTUP | Mode: {mode_str} | Balance: ${self.balance:.2f} | Offset: {self.btc_offset:.2f}", log_to_file=True, log_file=self.log_file)

        try:
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
                        print_status(f"NEW WINDOW: {start_dt.strftime('%H:%M')} | {self.market_url}", log_to_file=True, log_file=self.log_file)
                        
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

                except KeyboardInterrupt: 
                    break
                except Exception as e:
                    print(f"Error: {e}")
                    await asyncio.sleep(5)
        finally:
            # Close CSV file on exit
            if self.csv_file:
                self.csv_file.close()
                print(f"\n✅ CSV log saved to: {self.csv_filename}")


    # --- CSV Logging Methods ---
    def init_csv_logging(self):
        """Initialize CSV file with headers for detailed logging"""
        self.csv_file = open(self.csv_filename, 'w', newline='')
        self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=[
            'timestamp', 'window_start', 'elapsed_sec', 'btc_price', 'btc_open', 
            'drift_pct', 'up_price', 'down_price', 'leader_side', 'leader_price',
            'bb_position', 'bb_multiplier', 'bb_sma', 'bb_upper', 'bb_lower', 'bb_width',
            'action', 'reason', 'cost', 'balance'
        ])
        self.csv_writer.writeheader()
        self.csv_file.flush()
        print_status(f"CSV logging initialized: {self.csv_filename}", log_to_file=True, log_file=self.log_file)
    
    def log_checkpoint(self, elapsed, leader_side, leader_price, action, reason="", cost=0):
        """Log detailed checkpoint data to CSV"""
        if not self.csv_writer:
            self.init_csv_logging()
        
        btc = self.market_data["btc_price"]
        op = self.market_data["open_price"]
        drift = abs(btc - op) / op if op > 0 else 0
        
        bb_metrics = self.calculate_bollinger_metrics()
        
        self.csv_writer.writerow({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'window_start': datetime.fromtimestamp(self.market_data["start_ts"], tz=timezone.utc).strftime('%H:%M') if self.market_data["start_ts"] > 0 else "",
            'elapsed_sec': elapsed,
            'btc_price': f"{btc:.2f}",
            'btc_open': f"{op:.2f}",
            'drift_pct': f"{drift:.6f}",
            'up_price': f"{self.market_data['up_price']:.3f}",
            'down_price': f"{self.market_data['down_price']:.3f}",
            'leader_side': leader_side,
            'leader_price': f"{leader_price:.3f}",
            'bb_position': f"{bb_metrics['position']:.3f}",
            'bb_multiplier': f"{bb_metrics['size_multiplier']:.3f}",
            'bb_sma': f"{bb_metrics['sma']:.3f}",
            'bb_upper': f"{bb_metrics['upper_band']:.3f}",
            'bb_lower': f"{bb_metrics['lower_band']:.3f}",
            'bb_width': f"{bb_metrics['band_width']:.3f}",
            'action': action,
            'reason': reason,
            'cost': f"{cost:.2f}",
            'balance': f"{self.balance:.2f}"
        })
        self.csv_file.flush()  # Write immediately


    def calculate_bollinger_metrics(self):
        """
        Calculate Bollinger Band metrics for position sizing and risk assessment.
        
        Returns a dictionary with:
        - at_edge: True if price is within 10% of upper or lower band
        - position: 0.0 (lower band) to 1.0 (upper band), 0.5 = middle
        - size_multiplier: 0.5x (at edges) to 1.5x (at middle) for position sizing
        - band_width: Width of the band (volatility measure)
        
        Uses 36-period (3 minutes at 5-second intervals) SMA with 2 standard deviations.
        """
        # 3 minutes = 180 seconds, at 5-second intervals = 36 samples
        BB_PERIOD = 36
        
        # Default values when insufficient data
        default_result = {
            "at_edge": False,
            "position": 0.5,  # Assume middle
            "size_multiplier": 1.0,  # Baseline
            "band_width": 0.0,
            "sma": 0.0,
            "upper_band": 0.0,
            "lower_band": 0.0
        }
        
        if len(self.checkpoints) < BB_PERIOD:
            return default_result
        
        # Get sorted price history
        checkpoint_times = sorted(self.checkpoints.keys())
        prices = [self.checkpoints[t] for t in checkpoint_times]
        
        # Use last 36 samples (3 minutes) for calculation
        recent_prices = prices[-BB_PERIOD:]
        current_price = recent_prices[-1]
        
        # Calculate Simple Moving Average (SMA)
        sma = sum(recent_prices) / len(recent_prices)
        
        # Calculate Standard Deviation
        variance = sum((p - sma) ** 2 for p in recent_prices) / len(recent_prices)
        std_dev = variance ** 0.5
        
        # Bollinger Bands: SMA ± 2*StdDev
        upper_band = sma + (2 * std_dev)
        lower_band = sma - (2 * std_dev)
        
        # Calculate band width
        band_width = upper_band - lower_band
        
        # Calculate position within band (0.0 = lower, 0.5 = middle, 1.0 = upper)
        if band_width > 0:
            position = (current_price - lower_band) / band_width
            position = max(0.0, min(1.0, position))  # Clamp to [0, 1]
        else:
            position = 0.5  # No volatility, assume middle
        
        # Calculate distance from middle (0.0 = at middle, 0.5 = at edge)
        distance_from_middle = abs(position - 0.5)
        
        # Position sizing multiplier based on distance from middle
        # At middle (distance=0.0): 1.5x (low risk, high confidence)
        # At edges (distance=0.5): 0.5x (high risk, reduce exposure)
        # Linear interpolation: multiplier = 1.5 - (distance_from_middle * 2.0)
        size_multiplier = 1.5 - (distance_from_middle * 2.0)
        size_multiplier = max(0.5, min(1.5, size_multiplier))  # Clamp to [0.5, 1.5]
        
        # Edge detection (within 10% of band boundaries)
        edge_threshold = band_width * 0.10
        at_upper_edge = current_price >= (upper_band - edge_threshold)
        at_lower_edge = current_price <= (lower_band + edge_threshold)
        at_edge = at_upper_edge or at_lower_edge
        
        # Log for debugging
        if at_edge:
            edge_type = "UPPER" if at_upper_edge else "LOWER"
            print_status(f"  [BOLLINGER] At {edge_type} edge | Price: {current_price:.3f} | Bands: [{lower_band:.3f}, {upper_band:.3f}]", log_to_file=True, log_file=self.log_file)
        
        return {
            "at_edge": at_edge,
            "position": position,
            "size_multiplier": size_multiplier,
            "band_width": band_width,
            "sma": sma,
            "upper_band": upper_band,
            "lower_band": lower_band
        }

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
        btc = self.market_data["btc_price"]
        op = self.market_data["open_price"]
        
        # Determine Leader
        leader_side = "UP" if btc > op else "DOWN"
        leader_price = self.market_data["up_price"] if leader_side == "UP" else self.market_data["down_price"]
        
        # Log to CSV (Unconditionally, every 5s)
        action_label = "MONITOR"
        if self.active_trade: action_label = f"Post-Trade ({self.active_trade['type']})"
        self.log_checkpoint(elapsed, leader_side, leader_price, action_label)

        if self.strategy_triggered: return
        
        # --- CONTINUOUS SAMPLING (Every 5s from T+5:00 to T+9:00) ---
        # Only track during the scanning window (300s to 540s) for STRATEGY purposes
        if 300 <= elapsed <= 540:
            # Store checkpoint with elapsed time as key
            if elapsed not in self.checkpoints:
                self.checkpoints[elapsed] = leader_price
                print_status(f"  [Scan T+{elapsed}s] {leader_side} @ {leader_price:.2f}", log_to_file=True, log_file=self.log_file)
        
        # --- STRONG UPTREND DETECTION ---
        drift = abs(btc - op) / op
        
        # --- SIGNAL: BB DIP ENTRY (Early Entry ~0.60) ---
        # User Logic: If at Lower Bollinger Band, expect bounce (Mean Reversion).
        # Enter if price is > 0.60 but "Lower Band" (Dip in trend).
        if 300 <= elapsed <= 540 and not self.active_trade:
             if 0.60 <= leader_price < 0.85 and drift > DRIFT_THRESHOLD:
                  bb = self.calculate_bollinger_metrics()
                  # Position <= 0.20 means we are at the bottom 20% of the band (Oversold/Lower Edge)
                  if bb["position"] <= 0.20:
                       # Confirm it's not crashing (Momentum >= 0)
                       if len(self.checkpoints) >= 2:
                            last2 = sorted(self.checkpoints.keys())[-2:]
                            p_now = self.checkpoints[last2[1]]
                            p_prev = self.checkpoints[last2[0]]
                            
                            if p_now >= p_prev: # Not crashing
                                 self.execute_trade("BB-DIP", leader_side, leader_price, 0.15, bb["size_multiplier"])
                                 print_status(f"  [BB DIP ENTRY] Price: {leader_price:.3f} (Lower Band {bb['position']:.2f}, Bounce)", log_to_file=True, log_file=self.log_file)
                                 # Log to CSV
                                 self.log_checkpoint(elapsed, leader_side, leader_price, "TRADE_BB-DIP", 
                                                   f"Price >= 0.60 + Lower Band + Stable", cost=min(50.0, self.balance * 0.15))
                                 return

        # --- SIGNAL: HIGH CONFIDENCE ENTRY (88+ cents with MOMENTUM FILTER) ---
        # If leader price reaches 88+ cents AND is RISING, that's a very strong signal
        # Enter immediately with smaller position size for quick wins
        if 300 <= elapsed <= 540 and not self.active_trade:
            if leader_price >= 0.88 and drift > DRIFT_THRESHOLD:
                # MOMENTUM FILTER: Check if price is RISING (Option C)
                if len(self.checkpoints) >= 2:
                    checkpoint_times = sorted(self.checkpoints.keys())
                    recent_prices = [self.checkpoints[t] for t in checkpoint_times[-2:]]
                    
                    if recent_prices[-1] > recent_prices[-2]:  # Rising
                        bb_metrics = self.calculate_bollinger_metrics()
                        self.execute_trade("HIGH-CONF", leader_side, leader_price, 0.05, bb_metrics["size_multiplier"])
                        print_status(f"  [HIGH CONFIDENCE ENTRY] Price: {leader_price:.3f} (≥88%, Rising)", log_to_file=True, log_file=self.log_file)
                        if self.use_bb_sizing:
                            print_status(f"  [BB Sizing] Position: {bb_metrics['position']:.2f} | Multiplier: {bb_metrics['size_multiplier']:.2f}x", log_to_file=True, log_file=self.log_file)
                        
                        # Log to CSV
                        self.log_checkpoint(elapsed, leader_side, leader_price, "TRADE_HIGH-CONF", 
                                          f"Price ≥0.88 + Rising", cost=min(50.0, self.balance * 0.05))
                        return  # Exit early, trade executed
        
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
                        
                        # STRONG UPTREND DETECTED - Calculate BB-adjusted position size
                        bb_metrics = self.calculate_bollinger_metrics()
                        self.execute_trade("UPTREND", leader_side, leader_price, 0.20, bb_metrics["size_multiplier"])
                        print_status(f"  [STRONG UPTREND DETECTED] Momentum: +{momentum:.3f} | Consecutive: {max_consecutive} | History: {recent_prices}", log_to_file=True, log_file=self.log_file)
                        if self.use_bb_sizing:
                            print_status(f"  [BB Sizing] Position: {bb_metrics['position']:.2f} | Multiplier: {bb_metrics['size_multiplier']:.2f}x", log_to_file=True, log_file=self.log_file)
                        
                        # Log to CSV
                        self.log_checkpoint(elapsed, leader_side, leader_price, "TRADE_UPTREND", 
                                          f"Momentum +{momentum:.3f}, Consecutive {max_consecutive}", 
                                          cost=min(50.0, self.balance * 0.20))
                    
                    # Log near-misses for analysis (every 30 seconds)
                    elif elapsed % 30 == 0:
                        reason = []
                        if not has_strong_momentum: reason.append(f"Weak Momentum ({momentum:+.3f})")
                        if not has_consistency: reason.append(f"Inconsistent (Max {max_consecutive} rises)")
                        if not is_accelerating: reason.append("Decelerating")
                        if drift <= DRIFT_THRESHOLD: reason.append(f"Drift Low ({drift:.4%})")
                        if leader_price >= 0.85: reason.append(f"Price High ({leader_price:.2f})")
                        if reason:
                            print_status(f"  [T+{elapsed}s NO SIGNAL] {', '.join(reason)}", log_to_file=True, log_file=self.log_file)
        
        # --- FALLBACK: T+9 (540s) if no uptrend detected ---
        if 540 <= elapsed <= 550 and not self.active_trade:
            # Get BB metrics for T+9 decision
            bb_metrics = self.calculate_bollinger_metrics()
            at_bb_edge = bb_metrics["at_edge"]
            
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
                
                self.execute_trade("FALLBACK-T9", leader_side, leader_price, 0.10, bb_metrics["size_multiplier"])
                print_status(f"  [FALLBACK T+9] Entry at {leader_price:.2f} ({reason_suffix})", log_to_file=True, log_file=self.log_file)
                if self.use_bb_sizing:
                    print_status(f"  [BB Sizing] Position: {bb_metrics['position']:.2f} | Multiplier: {bb_metrics['size_multiplier']:.2f}x", log_to_file=True, log_file=self.log_file)
                
                # Log to CSV
                self.log_checkpoint(elapsed, leader_side, leader_price, "TRADE_T9-FALLBACK", 
                                  f"T+9 entry ({reason_suffix})", 
                                  cost=min(50.0, self.balance * 0.10))
            elif elapsed == 540:
                reason = []
                if drift <= DRIFT_THRESHOLD: reason.append(f"Drift Low ({drift:.4%})")
                if leader_price >= 0.85: reason.append(f"Price Too High ({leader_price:.2f})")
                if leader_price < min_price: reason.append(f"Price Below Threshold ({leader_price:.2f} < {min_price:.2f}, {reason_suffix})")
                print_status(f"  [T+9 SKIP] {', '.join(reason)}", log_to_file=True, log_file=self.log_file)

    def execute_trade(self, type_name, side, price, budget_pct, bb_multiplier=1.0):
        base_cost = min(50.0, self.balance * budget_pct)
        
        # Apply BB multiplier if enabled
        if self.use_bb_sizing:
            cost = base_cost * bb_multiplier
        else:
            cost = base_cost  # Fixed sizing
        
        cost = max(5.50, cost)  # Enforce Polymarket minimum
        
        # Skip trade if balance insufficient
        if cost > self.balance:
            print_status(f"SKIP: Insufficient balance (${self.balance:.2f} < ${cost:.2f})", log_to_file=True, log_file=self.log_file)
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
        if self.use_bb_sizing:
            print(f"BB Multiplier: {bb_multiplier:.2f}x (Base: ${base_cost:.2f})")
        print_status(f"Entered {type_name} ({side}) @ {price:.3f} | Cost: ${cost:.2f}", log_to_file=True, log_file=self.log_file)

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
            print_status(f"WIN: +${profit:.2f} | Bal: ${self.balance:.2f}", log_to_file=True, log_file=self.log_file)
        else:
            print(f"RESULT: LOSS. -${self.active_trade['cost']:.2f}")
            print_status(f"LOSS: -${self.active_trade['cost']:.2f} | Bal: ${self.balance:.2f}", log_to_file=True, log_file=self.log_file)
            
        print(f"New Balance: ${self.balance:.2f}")
        print("------------------")



if __name__ == "__main__":
    try:
        val = input("Enter Starting Balance [50.0]: ").strip()
        bal = float(val) if val else 50.0
        
        # Ask about BB-based position sizing
        print("\nPosition Sizing Mode:")
        print("  1. BB-Weighted (0.5x-1.5x based on volatility)")
        print("  2. Fixed Size (1.0x always)")
        bb_choice = input("Select [1]: ").strip()
        use_bb_sizing = (bb_choice != "2")  # Default to BB-weighted
        
        sim = LiveLinearSimulator(bal, use_bb_sizing)
        asyncio.run(sim.run())
    except KeyboardInterrupt:
        print("\nSimulator Stopped.")
