"""
Version 6.0 (v3)
Simulator: LIVE Strong Uptrend Detection Strategy — DATA-DRIVEN EDITION

Created from v2 with improvements based on analysis of 748 trades:
  - $19 -> $1,350 with 83.4% win rate, but $143 max drawdown

Key Changes from v2 (based on data):
  1. POSITION SIZING CAP: Hard cap at $15 (was $50). Large bets caused 94.3% of losses.
  2. REMOVED FALLBACK-T9: Net negative strategy (-$45.32 on 19 trades, 68.4% WR).
  3. EXHAUSTION FILTER: Skip UPTREND when consecutive rises >= 5 (64.7% WR, -$110).
  4. TIME-OF-DAY FILTER: Reduce sizing during worst hours (05,08,11,16 UTC).
  5. ENTRY PRICE SWEET SPOT: Best risk/reward at 0.50-0.65 (avg $6.51/trade profit).
  6. HIGH-CONF TIGHTENED: Skip entries >= 0.93 (only $0.62 avg profit, high risk).
  7. MOMENTUM QUALITY: Added min momentum floor for UPTREND (avoid weak +0.10 signals).
  8. STREAK AWARENESS: Reduce sizing after 2+ consecutive losses.
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
STATE_FILE = "sim_live_linear_v3_state.json"

# v3: Position Sizing Limits (data-driven)
MAX_COST = 15.0      # Hard cap (was $50 in v2 — large bets caused 94.3% of losses)
MIN_COST = 5.50      # Polymarket minimum

# v3: Time-of-Day Filters (UTC hours that consistently lost money)
BAD_HOURS_UTC = {5, 8, 11, 16}  # Combined -$339 in v2 analysis
REDUCED_HOURS_UTC = {4, 13}     # Slightly negative, reduce size

# v3: Exhaustion Filter
MAX_CONSECUTIVE_RISES = 4       # 5+ consecutive had only 64.7% WR and -$110 P&L

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
        self.initial_balance = float(balance)
        self.session = requests.Session()
        
        # State
        self.is_running = True
        self.market_url = ""
        self.active_trade = None
        self.strategy_triggered = False
        self.checkpoints = {} # {second: price}
        self.scan_count = 0   # v3: throttle scan logging
        
        # v3: Streak tracking
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.total_wins = 0
        self.total_losses = 0
        self.session_pnl = 0.0
        self.peak_balance = float(balance)
        self.window_count = 0
        self.windows_traded = 0
        self.windows_skipped = 0
        
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
        self.use_bb_sizing = use_bb_sizing
        
        # Logging (timestamped filenames)
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = os.path.join("data", f"sim_live_v3_log_{timestamp_str}.txt")
        self.csv_file = None
        self.csv_writer = None
        self.csv_filename = os.path.join("data", f"sim_live_v3_detailed_{timestamp_str}.csv")
        
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)

    # --- Data Fetching (Unchanged from v2) ---
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
            ts_sec = timestamp_ms / 1000
            start_iso = datetime.fromtimestamp(ts_sec, tz=timezone.utc).isoformat()
            end_iso = datetime.fromtimestamp(ts_sec + 60, tz=timezone.utc).isoformat()
            
            url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
            params = {
                "start": start_iso,
                "end": end_iso,
                "granularity": 60
            }
            headers = {"User-Agent": "PolySim/1.0"}
            
            resp = await asyncio.to_thread(self.session.get, url, params=params, headers=headers, timeout=3.0)
            data = resp.json()
            if data and isinstance(data, list) and len(data) > 0:
                return float(data[-1][3])
        except Exception as e:
            pass
        return 0.0

    async def get_historical_open(self, timestamp_ms):
        try:
            url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={timestamp_ms}&limit=1"
            resp = await asyncio.to_thread(self.session.get, url, timeout=2)
            data = resp.json()
            if data and len(data) > 0:
                return float(data[0][1]) + self.btc_offset
        except: 
            pass
            
        op = await self.get_coinbase_open(timestamp_ms)
        if op > 0: return op
        
        return 0.0

    async def fetch_spot_price(self):
        price = 0.0
        source = "Binance"
        
        try:
            url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
            resp = await asyncio.to_thread(self.session.get, url, timeout=2.0)
            data = resp.json()
            if "price" in data:
                price = float(data["price"])
        except Exception as e:
            pass

        if price == 0:
            source = "Coinbase"
            price = await self.fetch_coinbase_price()
            
        if price == 0:
            source = "CoinGecko"
            price = await self.fetch_coingecko_price()

        if price > 0:
            final_price = price + (self.btc_offset if source == "Binance" else 0.0)
            self.market_data["btc_price"] = final_price
            
            if self.market_data["open_price"] == 0 and self.market_data["start_ts"] > 0:
                 op = await self.get_historical_open(self.market_data["start_ts"] * 1000)
                 if op > 0: 
                     self.market_data["open_price"] = op
                     print_status(f"OPEN PRICE CACHED (via Hist): {op:,.2f}")
                 elif (time.time() - self.market_data["start_ts"]) < 300:
                     self.market_data["open_price"] = final_price
                     print_status(f"OPEN PRICE SET (LIVE FALLBACK): {final_price:,.2f}")
        else:
             print_status(f"CRITICAL: Failed to fetch BTC price from all sources.", log_to_file=True, log_file=self.log_file)

    async def fetch_market_data(self):
        if not self.market_data["up_id"] and self.market_url:
            try:
                slug = self.market_url.split("/")[-1].split("?")[0]
                url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
                resp = await asyncio.to_thread(self.session.get, url, timeout=2.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if "clobTokenIds" in data:
                        ids = self.safe_load(data["clobTokenIds"], [])
                        up_id, down_id = None, None
                        if len(ids) >= 2:
                            up_id, down_id = ids[0], ids[1]
                            
                        outcomes = self.safe_load(data.get("outcomes", "[]"), [])
                        if len(outcomes) >= 2:
                            for i, name in enumerate(outcomes):
                                if "Up" in name or "Yes" in name: up_id = ids[i]
                                elif "Down" in name or "No" in name: down_id = ids[i]
                        
                        self.market_data["up_id"] = up_id
                        self.market_data["down_id"] = down_id
            except: pass

        if self.market_data["up_id"]:
            try:
                clob_url = "https://clob.polymarket.com/price"
                p1 = await asyncio.to_thread(self.session.get, clob_url, params={"token_id": self.market_data["up_id"], "side": "buy"})
                p2 = await asyncio.to_thread(self.session.get, clob_url, params={"token_id": self.market_data["down_id"], "side": "buy"})
                
                r1, r2 = p1.json(), p2.json()
                if "price" in r1: self.market_data["up_price"] = float(r1["price"])
                if "price" in r2: self.market_data["down_price"] = float(r2["price"])
            except: pass

    # --- v3: Position Sizing Engine (Major Change) ---
    def calculate_trade_cost(self, strategy_type, budget_pct, bb_multiplier=1.0):
        """
        v3: Unified position sizing with hard cap and contextual adjustments.
        Returns (cost, sizing_notes) tuple for logging.
        """
        base_cost = self.balance * budget_pct
        notes = []
        
        # Apply BB multiplier if enabled
        if self.use_bb_sizing:
            cost = base_cost * bb_multiplier
            if abs(bb_multiplier - 1.0) > 0.05:
                notes.append(f"BB {bb_multiplier:.2f}x")
        else:
            cost = base_cost
        
        # v3: Hard cap (the #1 improvement from analysis)
        if cost > MAX_COST:
            notes.append(f"capped ${cost:.0f}->${MAX_COST:.0f}")
            cost = MAX_COST
        
        # v3: Time-of-day adjustment
        current_hour_utc = datetime.now(timezone.utc).hour
        if current_hour_utc in BAD_HOURS_UTC:
            cost *= 0.60
            notes.append(f"bad-hour({current_hour_utc}h)->60%")
        elif current_hour_utc in REDUCED_HOURS_UTC:
            cost *= 0.80
            notes.append(f"caution-hour({current_hour_utc}h)->80%")
        
        # v3: Streak-based reduction
        if self.consecutive_losses >= 2:
            cost *= 0.70
            notes.append(f"streak({self.consecutive_losses}L)->70%")
        
        # Enforce minimums
        cost = max(MIN_COST, cost)
        
        self._last_sizing_notes = notes  # Store for logging
        return cost

    # --- v3: Helper for record string ---
    def _record_str(self):
        total = self.total_wins + self.total_losses
        if total == 0:
            return "0-0 (0%)"
        wr = self.total_wins / total * 100
        return f"{self.total_wins}W-{self.total_losses}L ({wr:.0f}%)"
    
    def _hour_quality(self, hour_utc):
        if hour_utc in BAD_HOURS_UTC:
            return "BAD"
        elif hour_utc in REDUCED_HOURS_UTC:
            return "CAUTION"
        else:
            return "OK"

    # --- Core Loop ---
    async def run(self):
        mode_str = "BB-Weighted" if self.use_bb_sizing else "Fixed Size"
        
        # v3: Rich startup banner
        banner = [
            "="*60,
            "  POLYMARKET SIM v3 - DATA-DRIVEN EDITION",
            "="*60,
            f"  Balance:    ${self.balance:.2f}",
            f"  Sizing:     {mode_str} | Cap: ${MAX_COST:.0f}/trade",
            f"  Strategies: HIGH-CONF (0.88-0.93) + UPTREND (momentum)",
            f"  Removed:    FALLBACK-T9 (net negative in v2)",
            f"  Filters:    Exhaustion (>{MAX_CONSECUTIVE_RISES} consec), Bad Hours {sorted(BAD_HOURS_UTC)}",
            f"  Logs:       {self.log_file}",
            "="*60,
        ]
        for line in banner:
            print(line)
        
        print("Calibrating BTC offset...")
        await self.fetch_spot_price()
        print(f"Offset: {self.btc_offset:.2f}")
        
        startup_msg = (f"STARTUP | v3 Data-Driven | Mode: {mode_str} | "
                       f"Balance: ${self.balance:.2f} | Cap: ${MAX_COST:.0f} | "
                       f"Offset: {self.btc_offset:.2f} | "
                       f"Strategies: HIGH-CONF + UPTREND | "
                       f"Bad Hours: {sorted(BAD_HOURS_UTC)}")
        print_status(startup_msg, log_to_file=True, log_file=self.log_file)

        try:
            while self.is_running:
                try:
                    now = datetime.now(timezone.utc)
                    min15 = (now.minute // 15) * 15
                    start_dt = now.replace(minute=min15, second=0, microsecond=0)
                    ts_start = int(start_dt.timestamp())
                    url = f"https://polymarket.com/event/btc-updown-15m-{ts_start}"

                    if url != self.market_url:
                        if self.market_url != "":
                            await self.settle_window()
                            
                        self.market_url = url
                        self.window_count += 1
                        self.scan_count = 0
                        
                        # v3: Rich window header with context
                        hour_utc = start_dt.hour
                        hour_q = self._hour_quality(hour_utc)
                        hour_warn = f" !! {hour_q} HOUR !!" if hour_q != "OK" else ""
                        
                        print(f"\n{'='*55}")
                        print(f">> WINDOW #{self.window_count}: {start_dt.strftime('%H:%M')} UTC{hour_warn} <<")
                        print(f"   Record: {self._record_str()} | P&L: ${self.session_pnl:+.2f} | Bal: ${self.balance:.2f}")
                        print(f"   {self.market_url}")
                        print(f"{'='*55}")
                        
                        window_log = (f"NEW WINDOW #{self.window_count}: {start_dt.strftime('%H:%M')} UTC | "
                                     f"Hour: {hour_utc}:00 ({hour_q}) | "
                                     f"Record: {self._record_str()} | "
                                     f"P&L: ${self.session_pnl:+.2f} | Bal: ${self.balance:.2f}")
                        print_status(window_log, log_to_file=True, log_file=self.log_file)
                        
                        if self.consecutive_losses >= 2:
                            print_status(f"  >> LOSS STREAK ACTIVE: {self.consecutive_losses} consecutive. Sizing at 70%.", log_to_file=True, log_file=self.log_file)
                        
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

                    await self.fetch_spot_price()
                    await self.fetch_market_data()

                    elapsed = int(time.time() - ts_start)
                    self.print_status_line(elapsed)

                    if self.market_data["open_price"] > 0:
                         await self.process_strategy(elapsed)

                    await asyncio.sleep(5)

                except KeyboardInterrupt: 
                    break
                except Exception as e:
                    print(f"Error: {e}")
                    await asyncio.sleep(5)
        finally:
            if self.csv_file:
                self.csv_file.close()
                print(f"\nCSV log saved to: {self.csv_filename}")
            self.print_session_summary()


    # --- CSV Logging ---
    def init_csv_logging(self):
        """Initialize CSV file with headers for detailed logging"""
        self.csv_file = open(self.csv_filename, 'w', newline='')
        self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=[
            'timestamp', 'window_start', 'elapsed_sec', 'btc_price', 'btc_open', 
            'drift_pct', 'up_price', 'down_price', 'leader_side', 'leader_price',
            'bb_position', 'bb_multiplier', 'bb_sma', 'bb_upper', 'bb_lower', 'bb_width',
            'action', 'reason', 'cost', 'balance',
            'consecutive_losses', 'hour_utc'  # v3 additions
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
            'balance': f"{self.balance:.2f}",
            'consecutive_losses': self.consecutive_losses,
            'hour_utc': datetime.now(timezone.utc).hour
        })
        self.csv_file.flush()


    def calculate_bollinger_metrics(self):
        """
        Calculate Bollinger Band metrics for position sizing and risk assessment.
        Uses 36-period (3 minutes at 5-second intervals) SMA with 2 standard deviations.
        """
        BB_PERIOD = 36
        
        default_result = {
            "at_edge": False,
            "position": 0.5,
            "size_multiplier": 1.0,
            "band_width": 0.0,
            "sma": 0.0,
            "upper_band": 0.0,
            "lower_band": 0.0
        }
        
        if len(self.checkpoints) < BB_PERIOD:
            return default_result
        
        checkpoint_times = sorted(self.checkpoints.keys())
        prices = [self.checkpoints[t] for t in checkpoint_times]
        recent_prices = prices[-BB_PERIOD:]
        current_price = recent_prices[-1]
        
        sma = sum(recent_prices) / len(recent_prices)
        variance = sum((p - sma) ** 2 for p in recent_prices) / len(recent_prices)
        std_dev = variance ** 0.5
        
        upper_band = sma + (2 * std_dev)
        lower_band = sma - (2 * std_dev)
        band_width = upper_band - lower_band
        
        if band_width > 0:
            position = (current_price - lower_band) / band_width
            position = max(0.0, min(1.0, position))
        else:
            position = 0.5
        
        distance_from_middle = abs(position - 0.5)
        size_multiplier = 1.5 - (distance_from_middle * 2.0)
        size_multiplier = max(0.5, min(1.5, size_multiplier))
        
        edge_threshold = band_width * 0.10
        at_upper_edge = current_price >= (upper_band - edge_threshold)
        at_lower_edge = current_price <= (lower_band + edge_threshold)
        at_edge = at_upper_edge or at_lower_edge
        
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
        
        trade_str = f"ACTIVE ({self.active_trade['type']})" if self.active_trade else "SCANNING" if 300 <= elapsed <= 540 else "WAITING"
        t_str = f"T+{elapsed // 60}:{elapsed % 60:02d}"
        streak_str = f" [{self.consecutive_losses}L streak]" if self.consecutive_losses >= 2 else ""
        
        print(f"\r[{t_str}] BTC:{btc:,.0f} | UP:{up:.2f} DN:{dn:.2f} | Drift:{drift:.3%} | ${self.balance:.0f} | {trade_str}{streak_str}   ", end="", flush=True)

    async def process_strategy(self, elapsed):
        btc = self.market_data["btc_price"]
        op = self.market_data["open_price"]
        
        # Determine Leader
        leader_side = "UP" if btc > op else "DOWN"
        leader_price = self.market_data["up_price"] if leader_side == "UP" else self.market_data["down_price"]

        # Calculate Drift immediately
        drift = abs(btc - op) / op
        
        # Log to CSV (Unconditionally, every 5s)
        action_label = "MONITOR"
        if self.active_trade: action_label = f"Post-Trade ({self.active_trade['type']})"
        self.log_checkpoint(elapsed, leader_side, leader_price, action_label)

        if self.strategy_triggered: return
        
        # --- CONTINUOUS SAMPLING (Every 5s from T+5:00 to T+9:00) ---
        if 300 <= elapsed <= 540:
            if elapsed not in self.checkpoints:
                self.checkpoints[elapsed] = leader_price
                self.scan_count += 1
                
                # v3: Smarter scan logging — first scan, every 6th scan (~30s), and log-file always
                is_first = self.scan_count == 1
                is_periodic = self.scan_count % 6 == 0
                mins = elapsed // 60
                secs = elapsed % 60
                up_p = self.market_data["up_price"]
                dn_p = self.market_data["down_price"]
                scan_msg = f"  [Scan T+{mins}:{secs:02d}] {leader_side} leads | UP:{up_p:.2f} DN:{dn_p:.2f} | Drift:{drift:.3%} (#{self.scan_count})"
                
                if is_first or is_periodic:
                    print_status(scan_msg, log_to_file=True, log_file=self.log_file)
                else:
                    # Still log to file, just don't print to console
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    with open(self.log_file, "a") as f:
                        f.write(f"[{timestamp}] {scan_msg}\n")

        
        # =====================================================
        # v3: REMOVED BB-DIP ENTRY (merged into UPTREND logic)
        # v3: REMOVED FALLBACK-T9 (net negative in 748 trades)
        # =====================================================
        
        # --- SIGNAL 1: HIGH CONFIDENCE ENTRY (88-92 cents, rising) ---
        if 300 <= elapsed <= 540 and not self.active_trade:
            if 0.88 <= leader_price < 0.93 and drift > DRIFT_THRESHOLD:
                if len(self.checkpoints) >= 2:
                    checkpoint_times = sorted(self.checkpoints.keys())
                    recent_prices = [self.checkpoints[t] for t in checkpoint_times[-2:]]
                    
                    if recent_prices[-1] > recent_prices[-2]:  # Rising
                        bb_metrics = self.calculate_bollinger_metrics()
                        cost = self.calculate_trade_cost("HIGH-CONF", 0.05, bb_metrics["size_multiplier"])
                        self.execute_trade("HIGH-CONF", leader_side, leader_price, cost)
                        
                        potential_profit = (cost / leader_price) - cost
                        sizing_info = f" | Sizing: {', '.join(self._last_sizing_notes)}" if self._last_sizing_notes else ""
                        print_status(
                            f"  [HIGH-CONF ENTRY] {leader_side} @ {leader_price:.2f} | "
                            f"Cost: ${cost:.2f} | Max Profit: ${potential_profit:.2f} | "
                            f"Drift: {drift:.3%}{sizing_info}", 
                            log_to_file=True, log_file=self.log_file)
                        
                        self.log_checkpoint(elapsed, leader_side, leader_price, "TRADE_HIGH-CONF", 
                                          f"Price {leader_price:.2f} (88-93% + Rising)", cost=cost)
                        return
        
        # --- SIGNAL 2: STRONG UPTREND DETECTION (Core strategy, #1 earner) ---
        if 300 <= elapsed <= 540 and not self.active_trade:
            checkpoint_times = sorted(self.checkpoints.keys())
            
            if len(checkpoint_times) >= 3:
                recent_times = [t for t in checkpoint_times if elapsed - t <= 90]
                
                if len(recent_times) >= 3:
                    recent_prices = [self.checkpoints[t] for t in recent_times]
                    
                    price_start = recent_prices[0]
                    price_current = recent_prices[-1]
                    momentum = price_current - price_start
                    
                    # Count consecutive rising samples
                    consecutive_rises = 0
                    max_consecutive = 0
                    for i in range(1, len(recent_prices)):
                        if recent_prices[i] > recent_prices[i-1]:
                            consecutive_rises += 1
                            max_consecutive = max(max_consecutive, consecutive_rises)
                        else:
                            consecutive_rises = 0
                    
                    # Velocity/acceleration check
                    if len(recent_times) >= 6:
                        mid_point = len(recent_times) // 2
                        early_momentum = recent_prices[mid_point] - recent_prices[0]
                        late_momentum = recent_prices[-1] - recent_prices[mid_point]
                        is_accelerating = late_momentum >= early_momentum * 0.8
                    else:
                        is_accelerating = True
                    
                    # --- v3: ENHANCED UPTREND CRITERIA ---
                    has_strong_momentum = momentum >= 0.10
                    has_consistency = max_consecutive >= 2
                    
                    # v3: EXHAUSTION FILTER — skip if too many consecutive rises
                    is_exhausted = max_consecutive >= MAX_CONSECUTIVE_RISES + 1  # >= 5
                    
                    # v3: ENTRY PRICE SWEET SPOT — best results at 0.50-0.72
                    # Still allow up to 0.85 but prefer lower entries
                    in_sweet_spot = leader_price < 0.72
                    
                    if (has_strong_momentum and 
                        has_consistency and 
                        is_accelerating and
                        not is_exhausted and
                        drift > DRIFT_THRESHOLD and 
                        leader_price < 0.85 and 
                        leader_price > 0.10):
                        
                        bb_metrics = self.calculate_bollinger_metrics()
                        
                        # v3: Budget % depends on entry quality
                        if in_sweet_spot:
                            budget_pct = 0.20
                            tier = "SWEET-SPOT"
                        else:
                            budget_pct = 0.12
                            tier = "STANDARD"
                        
                        cost = self.calculate_trade_cost("UPTREND", budget_pct, bb_metrics["size_multiplier"])
                        self.execute_trade("UPTREND", leader_side, leader_price, cost)
                        
                        potential_profit = (cost / leader_price) - cost
                        sizing_info = f" | Sizing: {', '.join(self._last_sizing_notes)}" if self._last_sizing_notes else ""
                        mins = elapsed // 60
                        secs = elapsed % 60
                        print_status(
                            f"  [UPTREND ENTRY] {leader_side} @ {leader_price:.2f} | T+{mins}:{secs:02d} | "
                            f"Momentum: +{momentum:.3f} | Consec: {max_consecutive} | Tier: {tier} | "
                            f"Cost: ${cost:.2f} | Max Profit: ${potential_profit:.2f}{sizing_info}", 
                            log_to_file=True, log_file=self.log_file)
                        print_status(
                            f"  [UPTREND DETAIL] Price history (last {len(recent_prices)}): {[f'{p:.2f}' for p in recent_prices[-8:]]}",
                            log_to_file=True, log_file=self.log_file)
                        
                        self.log_checkpoint(elapsed, leader_side, leader_price, "TRADE_UPTREND", 
                                          f"Momentum +{momentum:.3f}, Consecutive {max_consecutive}, {tier}", 
                                          cost=cost)
                    
                    # Log near-misses (every 30 seconds)
                    elif elapsed % 30 == 0:
                        reason = []
                        if not has_strong_momentum: reason.append(f"Mom({momentum:+.2f}<0.10)")
                        if not has_consistency: reason.append(f"Consec({max_consecutive}<2)")
                        if not is_accelerating: reason.append("Decel")
                        if is_exhausted: reason.append(f"EXHAUSTED({max_consecutive}consec)")
                        if drift <= DRIFT_THRESHOLD: reason.append(f"LowDrift({drift:.3%})")
                        if leader_price >= 0.85: reason.append(f"PriceHigh({leader_price:.2f})")
                        if reason:
                            mins = elapsed // 60
                            secs = elapsed % 60
                            print_status(f"  [T+{mins}:{secs:02d} SKIP] {leader_side}@{leader_price:.2f} | {', '.join(reason)}", log_to_file=True, log_file=self.log_file)
        
        # --- v3: HEDGING LOGIC (Zero-Risk Reversal Protection) ---
        # "If relatively low entry, swung to other side (High), offset potential loss"
        if self.active_trade and not self.active_trade.get("hedged", False):
            await self.check_and_execute_hedge(elapsed)

    async def check_and_execute_hedge(self, elapsed):
        side = self.active_trade["side"]
        entry = self.active_trade["entry"]
        cost_orig = self.active_trade["cost"]
        
        # Current status
        up_p = self.market_data["up_price"]
        dn_p = self.market_data["down_price"]
        current_price = up_p if side == "UP" else dn_p
        opp_price = dn_p if side == "UP" else up_p
        
        # Criteria for LOSS RECOVERY HEDGE:
        # 1. We are LOSING BADLY (Current price < 0.20)
        # 2. Opponent is WINNING (Opp price > 0.80)
        # 3. Heavy reversal (User: "swung completely 180 degrees")
        # 4. Little time remaining (> 10 mins elapsed)
        
        if elapsed > 600 and current_price < 0.20 and opp_price > 0.80:
            # PARTIAL MITIGATION HEDGE
            # We don't want to double down risk. We just want to soften the blow.
            # Strategy: Spend 30% of Original Cost to buy Opponent.
            
            hedge_budget = cost_orig * 0.30
            
            # Check Balance
            if hedge_budget > self.balance: return
            
            # Calculate shares we can get for this budget
            # shares = budget / price
            hedge_shares = hedge_budget / opp_price
            
            opp_side = "DOWN" if side == "UP" else "UP"
            
            # EXECUTE PARTIAL HEDGE
            self.balance -= hedge_budget
            self.active_trade["hedged"] = True
            self.active_trade["hedge_cost"] = hedge_budget
            self.active_trade["hedge_shares"] = hedge_shares
            self.active_trade["hedge_side"] = opp_side
            
            # Projected Outcome calculation
            # If Opponent Wins: Payout = hedge_shares. Net = hedge_shares - hedge_budget - cost_orig
            payout_hedge = hedge_shares
            net_loss_hedged = payout_hedge - hedge_budget - cost_orig
            net_loss_raw = -cost_orig
            saved = net_loss_hedged - net_loss_raw # How much we saved
            
            print_status(
                f"  [PARTIAL HEDGE] Mitigation Triggered.\n"
                f"    Buying {hedge_shares:.1f} {opp_side} @ {opp_price:.2f} (Cost ${hedge_budget:.2f})\n"
                f"    Scenario A ({opp_side} Wins): Loss reduced by ${saved:.2f}.\n"
                f"    Scenario B ({side} Wins): Profit reduced by ${hedge_budget:.2f}.", 
                log_to_file=True, log_file=self.log_file)

            self.log_checkpoint(elapsed, opp_side, opp_price, "TRADE_HEDGE_PARTIAL", 
                              f"Mitigate Loss (-${hedge_budget:.2f})", cost=hedge_budget)

    # ... (execute_trade remains unchanged) ...

    async def settle_window(self):
        if not self.active_trade:
            # v3: Log skipped windows too
            self.windows_skipped += 1
            # ... (omitted logging logic) ...
            return
        
        btc = self.market_data["btc_price"]
        op = self.market_data["open_price"]
        
        if op == 0:
            print("Warning: No Open Price. Assuming Refund/No Action.")
            return

        btc_move = btc - op
        winner = "UP" if btc_move > 0 else "DOWN"
        
        # PRIMARY TRADE
        side = self.active_trade["side"]
        cost = self.active_trade["cost"]
        shares = self.active_trade["shares"]
        
        primary_payout = shares if side == winner else 0.0
        
        # HEDGE TRADE
        hedge_payout = 0.0
        hedge_cost = 0.0
        if self.active_trade.get("hedged"):
             hedge_side = self.active_trade["hedge_side"]
             hedge_shares = self.active_trade["hedge_shares"]
             hedge_cost = self.active_trade["hedge_cost"]
             if hedge_side == winner:
                 hedge_payout = hedge_shares
        
        # NET RESULT
        total_cost = cost + hedge_cost
        total_payout = primary_payout + hedge_payout
        net_profit = total_payout - total_cost
        
        entry_price = self.active_trade["entry"]
        trade_type = self.active_trade["type"]
        
        self.balance += total_payout
        self.session_pnl += net_profit
        
        if net_profit > 0:
            self.total_wins += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            if self.balance > self.peak_balance: self.peak_balance = self.balance
            
            roi = (net_profit / total_cost) * 100
            print(f"\n  +++ WIN +++ {trade_type} {side} @ {entry_price:.2f} -> {winner}")
            if hedge_cost > 0: print(f"  (Hedged Recovery Successful)")
            print(f"  Profit: +${net_profit:.2f} (ROI: {roi:.0f}%) | Bal: ${self.balance:.2f}")
            
            win_log = (f"WIN +${net_profit:.2f} | {trade_type} {side}@{entry_price:.2f} | "
                      f"Cost: ${total_cost:.2f} | ROI: {roi:.0f}% | Bal: ${self.balance:.2f}")
            print_status(win_log, log_to_file=True, log_file=self.log_file)
            
        elif net_profit < 0:
            self.total_losses += 1
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            
            print(f"\n  --- LOSS --- {trade_type} {side} @ {entry_price:.2f} -> {winner}")
            if hedge_cost > 0: print(f"  (Hedge Failed - Double Loss?)")
            print(f"  Lost: -${abs(net_profit):.2f} | Bal: ${self.balance:.2f}")
            
            loss_log = (f"LOSS -${abs(net_profit):.2f} | {trade_type} {side}@{entry_price:.2f} | "
                       f"Cost: ${total_cost:.2f} | Bal: ${self.balance:.2f}")
            print_status(loss_log, log_to_file=True, log_file=self.log_file)
            
        else:
            # Break Even (0.00)
            print(f"\n  === BREAK EVEN === {trade_type} {side} -> {winner}")
            if hedge_cost > 0: print(f"  (Recovery Hedge Saved the Day!)")
            print(f"  P&L: $0.00 | Bal: ${self.balance:.2f}")
            print_status(f"BREAK_EVEN | {trade_type} (Hedged) | Bal: ${self.balance:.2f}", log_to_file=True, log_file=self.log_file)
        side = self.active_trade["side"]
        entry_price = self.active_trade["entry"]
        cost = self.active_trade["cost"]
        trade_type = self.active_trade["type"]
        
        if side == winner:
            payout = self.active_trade["shares"]
            profit = payout - cost
            roi = (profit / cost) * 100
            self.balance += payout
            self.total_wins += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            self.session_pnl += profit
            if self.balance > self.peak_balance:
                self.peak_balance = self.balance
            
            print(f"\n  +++ WIN +++ {trade_type} {side} @ {entry_price:.2f} -> {winner}")
            print(f"  Profit: +${profit:.2f} (ROI: {roi:.0f}%) | Bal: ${self.balance:.2f}")
            
            win_log = (f"WIN +${profit:.2f} | {trade_type} {side}@{entry_price:.2f} | "
                      f"Cost: ${cost:.2f} | ROI: {roi:.0f}% | "
                      f"Bal: ${self.balance:.2f} | Record: {self._record_str()} | "
                      f"P&L: ${self.session_pnl:+.2f}")
            if self.consecutive_wins >= 3:
                win_log += f" | HOT STREAK: {self.consecutive_wins}W"
            print_status(win_log, log_to_file=True, log_file=self.log_file)
        else:
            loss = cost
            self.total_losses += 1
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            self.session_pnl -= loss
            drawdown = self.peak_balance - self.balance
            
            print(f"\n  --- LOSS --- {trade_type} {side} @ {entry_price:.2f} -> {winner}")
            print(f"  Lost: -${loss:.2f} | BTC moved {'+' if btc_move > 0 else ''}{btc_move:.1f} | Bal: ${self.balance:.2f}")
            
            loss_log = (f"LOSS -${loss:.2f} | {trade_type} {side}@{entry_price:.2f} | "
                       f"BTC: {btc:,.0f} vs Open: {op:,.0f} ({'+' if btc_move > 0 else ''}{btc_move:.1f}) | "
                       f"Bal: ${self.balance:.2f} | Record: {self._record_str()} | "
                       f"P&L: ${self.session_pnl:+.2f}")
            if self.consecutive_losses >= 2:
                loss_log += f" | LOSS STREAK: {self.consecutive_losses} (sizing->70%)"
            if drawdown > 10:
                loss_log += f" | Drawdown: ${drawdown:.2f} from peak ${self.peak_balance:.2f}"
            print_status(loss_log, log_to_file=True, log_file=self.log_file)

    def print_session_summary(self):
        """v3: Comprehensive session summary"""
        total = self.total_wins + self.total_losses
        runtime = datetime.now().strftime('%H:%M:%S')
        
        print(f"\n{'='*60}")
        print(f"  SESSION SUMMARY (v3) — Ended {runtime}")
        print(f"{'='*60}")
        
        if total == 0:
            print(f"  No trades executed.")
            print(f"  Windows observed: {self.window_count}")
            print(f"{'='*60}")
            print_status(f"SESSION END | No trades | {self.window_count} windows observed", log_to_file=True, log_file=self.log_file)
            return
        
        wr = self.total_wins / total * 100
        balance_change = self.balance - self.initial_balance
        roi = (balance_change / self.initial_balance) * 100
        drawdown = self.peak_balance - self.balance
        avg_win = self.session_pnl / self.total_wins if self.total_wins > 0 else 0  # rough
        
        print(f"  Trades:       {total} ({self.total_wins}W / {self.total_losses}L)")
        print(f"  Win Rate:     {wr:.1f}%")
        print(f"  P&L:          ${self.session_pnl:+.2f}")
        print(f"  Balance:      ${self.initial_balance:.2f} -> ${self.balance:.2f} ({'+' if balance_change >= 0 else ''}{balance_change:.2f})")
        print(f"  ROI:          {roi:+.1f}%")
        print(f"  Peak Balance: ${self.peak_balance:.2f}")
        if drawdown > 0:
            print(f"  Cur Drawdown: ${drawdown:.2f}")
        print(f"  Windows:      {self.window_count} total ({self.windows_traded} traded, {self.windows_skipped} skipped)")
        print(f"  Position Cap: ${MAX_COST:.0f}")
        print(f"{'='*60}")
        
        summary = (f"SESSION END | {total} trades ({wr:.1f}% WR) | "
                   f"P&L: ${self.session_pnl:+.2f} | "
                   f"Bal: ${self.initial_balance:.2f}->${self.balance:.2f} ({roi:+.1f}%) | "
                   f"Peak: ${self.peak_balance:.2f} | "
                   f"Windows: {self.windows_traded}/{self.window_count} traded")
        print_status(summary, log_to_file=True, log_file=self.log_file)



if __name__ == "__main__":
    try:
        val = input("Enter Starting Balance [50.0]: ").strip()
        bal = float(val) if val else 50.0
        
        # Ask about BB-based position sizing
        print("\nPosition Sizing Mode:")
        print("  1. BB-Weighted (0.5x-1.5x based on volatility)")
        print("  2. Fixed Size (1.0x always)")
        bb_choice = input("Select [1]: ").strip()
        use_bb_sizing = (bb_choice != "2")
        
        sim = LiveLinearSimulator(bal, use_bb_sizing)
        asyncio.run(sim.run())
    except KeyboardInterrupt:
        print("\nSimulator Stopped.")
