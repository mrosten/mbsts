"""
Version 4.0 (v4)
Simulator: Context-Aware Live Trading Strategy
----------------------------------------------
Builds on v3 (Data-Driven) by adding Macro Context & Volatility Regimes.

New Features:
1. Macro Trend Filter (1H/4H): Reduces size or skips if fighting the "River Current".
2. Volatility Regime (ATR): Adapts strategy (Trending vs Choppy) based on 24h volatility.

Base Logic (v3):
- Hard Cap ($15)
- Time-of-Day Filter
- Exhaustion Filter (Max 4 consec)
- Partial Hedge (Loss Mitigation)
"""

import requests
import time
import json
import asyncio
import sys
from datetime import datetime, timezone, timedelta
import os
import csv
import math

# --- Configuration ---
DRIFT_THRESHOLD = 0.0004
STATE_FILE = "sim_live_linear_v4_state.json"

# v3 Constraints
MAX_COST = 15.0      
MIN_COST = 5.50      
BAD_HOURS_UTC = {5, 8, 11, 16}
REDUCED_HOURS_UTC = {4, 13}
MAX_CONSECUTIVE_RISES = 4

class LiveLinearSimulatorV4:
    def __init__(self, balance, use_bb_sizing=True):
        self.balance = float(balance)
        self.session = requests.Session()
        
        # State
        self.is_running = True
        self.market_url = ""
        self.active_trade = None
        self.checkpoints = {} 
        self.scan_count = 0
        self.consecutive_losses = 0
        self.total_wins = 0
        self.total_losses = 0
        self.session_pnl = 0.0
        self.peak_balance = float(balance)
        self.window_count = 0
        self.windows_skipped = 0
        
        # Data
        self.btc_offset = -86.0
        self.market_data = {
            "up_id": None, "down_id": None, 
            "up_price": 0.0, "down_price": 0.0,
            "btc_price": 0.0, "open_price": 0.0,
            "start_ts": 0
        }
        self.use_bb_sizing = use_bb_sizing
        self._last_sizing_notes = []
        
        # v4 Context Data
        self.context = {
            "trend_1h": "NEUTRAL",  # UP/DOWN/NEUTRAL
            "trend_4h": "NEUTRAL",
            "atr_24h_pct": 0.0,     # Volatility metric
            "regime": "NORMAL"      # LOW_VOL, INDECISIVE, HIGH_VOL
        }
        self.last_context_update = 0

        # Logging
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = os.path.join("data", f"sim_live_v4_log_{timestamp_str}.txt")
        self.csv_filename = os.path.join("data", f"sim_live_v4_detailed_{timestamp_str}.csv")
        os.makedirs("data", exist_ok=True)
        self.init_csv_logging()

    def print_status(self, msg, log_to_file=False):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}"
        print(line)
        if log_to_file:
            with open(self.log_file, "a") as f:
                f.write(line + "\n")

    # --- v4: Context Awareness ---
    async def update_context(self):
        """Fetch 1H/4H candles to determine Macro Trend and Volatility Regime."""
        now = time.time()
        if now - self.last_context_update < 300: return # Cache for 5 mins
        
        try:
            # Fetch 4H and 1H candles from Binance (limit 24 for 4H, 24 for 1H)
            # symbol=BTCUSDT
            url = "https://api.binance.com/api/v3/klines"
            
            # 1. 4H Trend
            p_4h = {"symbol": "BTCUSDT", "interval": "4h", "limit": 10}
            r_4h = await asyncio.to_thread(self.session.get, url, params=p_4h)
            k_4h = r_4h.json()
            if k_4h:
                closes = [float(x[4]) for x in k_4h]
                sma_short = sum(closes[-3:]) / 3
                sma_long = sum(closes) / len(closes)
                if sma_short > sma_long * 1.002: self.context["trend_4h"] = "UP"
                elif sma_short < sma_long * 0.998: self.context["trend_4h"] = "DOWN"
                else: self.context["trend_4h"] = "NEUTRAL"

            # 2. 1H Trend & Volatility (ATR)
            p_1h = {"symbol": "BTCUSDT", "interval": "1h", "limit": 24}
            r_1h = await asyncio.to_thread(self.session.get, url, params=p_1h)
            k_1h = r_1h.json()
            if k_1h:
                closes_1h = [float(x[4]) for x in k_1h]
                highs = [float(x[2]) for x in k_1h]
                lows = [float(x[3]) for x in k_1h]
                
                # Trend 1H
                if closes_1h[-1] > closes_1h[-5]: self.context["trend_1h"] = "UP"
                else: self.context["trend_1h"] = "DOWN"

                # ATR Calculation (24h)
                tr_sum = 0
                for i in range(1, len(k_1h)):
                    tr = max(highs[i]-lows[i], abs(highs[i]-closes_1h[i-1]), abs(lows[i]-closes_1h[i-1]))
                    tr_sum += tr
                atr = tr_sum / (len(k_1h)-1)
                self.context["atr_24h_pct"] = (atr / closes_1h[-1]) * 100
                
                # Regime Classification
                if self.context["atr_24h_pct"] < 0.5: self.context["regime"] = "LOW_VOL"
                elif self.context["atr_24h_pct"] > 1.2: self.context["regime"] = "HIGH_VOL"
                else: self.context["regime"] = "NORMAL"

            self.last_context_update = now
            self.print_status(f"CONTEXT UPDATE: 4H={self.context['trend_4h']} | 1H={self.context['trend_1h']} | ATR={self.context['atr_24h_pct']:.2f}% ({self.context['regime']})", log_to_file=True)
            
        except Exception as e:
            self.print_status(f"Context Update Failed: {e}", log_to_file=True)

    # --- Logic Helpers (v3 + v4 adjustments) ---
    def calculate_trade_cost(self, strategy_type, budget_pct, bb_multiplier=1.0):
        base_cost = self.balance * budget_pct
        notes = []
        
        # v3 Factors
        if self.use_bb_sizing:
            cost = base_cost * bb_multiplier
            if abs(bb_multiplier - 1.0) > 0.05: notes.append(f"BB {bb_multiplier:.2f}x")
        else: cost = base_cost

        # v4: Macro Trend "River Current" Adjustment
        # If trying to buy UPTREND but 4H is DOWN -> Reduce size significantly
        # If 4H is UP and we buy UPTREND -> Enhance slightly? (Maybe cap is still $15)
        if strategy_type == "UPTREND":
            if self.context["trend_4h"] == "DOWN":
                cost *= 0.5
                notes.append("against-4h-trend(50%)")
            elif self.context["trend_4h"] == "NEUTRAL" and self.context["trend_1h"] == "DOWN":
                cost *= 0.7
                notes.append("against-1h-trend(70%)")
        
        # v4: Regime Adjustment
        if self.context["regime"] == "LOW_VOL":
            # In low vol, breakouts often fail. Reduce size on momentum trades.
            cost *= 0.6
            notes.append("low-vol-regime(60%)")
        
        # v3: Time/Streak limits
        if cost > MAX_COST: 
            notes.append(f"capped ${cost:.0f}->${MAX_COST:.0f}")
            cost = MAX_COST
            
        current_hour = datetime.now(timezone.utc).hour
        if current_hour in BAD_HOURS_UTC:
            cost *= 0.60
            notes.append(f"bad-hour({current_hour}h)")
        
        if self.consecutive_losses >= 2:
            cost *= 0.70
            notes.append(f"streak({self.consecutive_losses}L)")
            
        cost = max(MIN_COST, cost)
        self._last_sizing_notes = notes
        return cost

    # --- Standard Fetch/Calc Methods (Simplified from v3) ---
    async def fetch_spot_price(self):
        try:
            url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
            resp = await asyncio.to_thread(self.session.get, url, timeout=2.0)
            data = resp.json()
            if "price" in data:
                price = float(data["price"]) + self.btc_offset
                self.market_data["btc_price"] = price
                # Open Price Logic
                if self.market_data["open_price"] == 0 and self.market_data["start_ts"] > 0:
                    if (time.time() - self.market_data["start_ts"]) < 300:
                        self.market_data["open_price"] = price
        except: pass

    async def fetch_market_data(self):
        # ... (Same as v3, simplified for brevity in this block, essentially fetches UP/DOWN prices)
        # Assuming v3 implementation is standard, will paste full if needed.
        # For simulation v4, we use the same endpoints.
        if self.market_data["up_id"]:
            try:
                url = "https://clob.polymarket.com/price"
                p1 = await asyncio.to_thread(self.session.get, url, params={"token_id": self.market_data["up_id"], "side": "buy"})
                p2 = await asyncio.to_thread(self.session.get, url, params={"token_id": self.market_data["down_id"], "side": "buy"})
                if p1.status_code == 200: self.market_data["up_price"] = float(p1.json().get("price", 0))
                if p2.status_code == 200: self.market_data["down_price"] = float(p2.json().get("price", 0))
            except: pass
        elif self.market_url:
            # Init IDs logic...
            try:
                slug = self.market_url.split("/")[-1].split("?")[0]
                resp = await asyncio.to_thread(self.session.get, f"https://gamma-api.polymarket.com/markets/slug/{slug}")
                if "clobTokenIds" in resp.json():
                    ids = json.loads(resp.json()["clobTokenIds"])
                    self.market_data["up_id"] = ids[0]
                    self.market_data["down_id"] = ids[1]
            except: pass

    def calculate_bollinger_metrics(self):
        # Standard v3 implementation
        BB_PERIOD = 36
        if len(self.checkpoints) < BB_PERIOD: return {"size_multiplier": 1.0, "position": 0.5}
        prices = sorted([v for k,v in self.checkpoints.items()])[-BB_PERIOD:]
        sma = sum(prices)/len(prices)
        std = (sum((p-sma)**2 for p in prices)/len(prices))**0.5
        width = 4*std
        pos = 0.5
        if width > 0: pos = (prices[-1] - (sma-2*std))/width
        multiplier = max(0.5, min(1.5, 1.5 - abs(pos-0.5)*2))
        return {"size_multiplier": multiplier, "position": pos}

    # --- Strategy Execution ---
    async def process_strategy(self, elapsed):
        btc = self.market_data["btc_price"]
        op = self.market_data["open_price"]
        drift = abs(btc - op) / op if op > 0 else 0
        
        leader_side = "UP" if btc > op else "DOWN"
        leader_price = self.market_data["up_price"] if leader_side == "UP" else self.market_data["down_price"]
        
        self.log_checkpoint(elapsed, leader_side, leader_price, "MONITOR")
        
        if self.active_trade:
            # v3 Hedge Logic (Partial Mitigation)
            if not self.active_trade.get("hedged") and elapsed > 600:
                cost = self.active_trade["cost"]
                price = self.market_data["up_price"] if self.active_trade["side"] == "UP" else self.market_data["down_price"]
                opp_price = self.market_data["down_price"] if self.active_trade["side"] == "UP" else self.market_data["up_price"]
                
                if price < 0.20 and opp_price > 0.80:
                    hedge_amt = cost * 0.30
                    if self.balance >= hedge_amt:
                        self.balance -= hedge_amt
                        self.active_trade["hedged"] = True
                        self.active_trade["hedge_cost"] = hedge_amt
                        self.active_trade["hedge_shares"] = hedge_amt / opp_price
                        self.active_trade["hedge_side"] = "DOWN" if self.active_trade["side"] == "UP" else "UP"
                        self.print_status(f"PARTIAL HEDGE: Spent ${hedge_amt:.2f} to mitigate loss.", log_to_file=True)
            return

        # Sampling
        if 300 <= elapsed <= 540:
            if elapsed not in self.checkpoints:
                self.checkpoints[elapsed] = leader_price
                if elapsed % 30 == 0:
                    self.print_status(f"Scanning... {leader_side} @ {leader_price:.2f} (Drift {drift:.2%})", log_to_file=True)
                
                # Check Signal
                # v3 Strong Uptrend Logic
                times = sorted(self.checkpoints.keys())
                recent = [self.checkpoints[t] for t in times if elapsed - t <= 90]
                if len(recent) >= 3:
                    start_p = recent[0]
                    end_p = recent[-1]
                    mom = end_p - start_p
                    consec = 0
                    max_consec = 0
                    for i in range(1, len(recent)):
                        if recent[i] > recent[i-1]: consec += 1
                        else: consec = 0
                        max_consec = max(max_consec, consec)
                        
                    # Filter: Exhaustion
                    if max_consec >= MAX_CONSECUTIVE_RISES + 1: return
                    
                    # Entry
                    if (mom >= 0.10 and max_consec >= 2 and drift > DRIFT_THRESHOLD 
                        and leader_price < 0.85 and leader_price > 0.10):
                        
                        bb = self.calculate_bollinger_metrics()
                        budget_pct = 0.20 if leader_price < 0.72 else 0.12
                        
                        cost = self.calculate_trade_cost("UPTREND", budget_pct, bb["size_multiplier"])
                        
                        # EXECUTE
                        if self.balance >= cost:
                            self.balance -= cost
                            shares = cost / leader_price
                            self.active_trade = {
                                "type": "UPTREND", "side": leader_side, "entry": leader_price,
                                "cost": cost, "shares": shares
                            }
                            self.print_status(f"BUY {leader_side} @ {leader_price:.2f} | Cost ${cost:.2f} | Context: 4H={self.context['trend_4h']}", log_to_file=True)

    async def run(self):
        self.print_status("--- SIMULATOR v4 (Context-Aware) ---", log_to_file=True)
        self.print_status(f"Balance: ${self.balance:.2f}", log_to_file=True)
        
        while self.is_running:
            try:
                await self.update_context() # v4 Context Update
                
                now = datetime.now(timezone.utc)
                min15 = (now.minute // 15) * 15
                start_dt = now.replace(minute=min15, second=0, microsecond=0)
                ts_start = int(start_dt.timestamp())
                url = f"https://polymarket.com/event/btc-updown-15m-{ts_start}"

                if url != self.market_url:
                    # Settle old
                    if self.market_url and self.active_trade:
                        # Simple settlement logic for v4 skeleton
                        self.print_status("Settling window...", log_to_file=True)
                        btc = self.market_data["btc_price"]
                        op = self.market_data["open_price"]
                        win_side = "UP" if btc > op else "DOWN"
                        payout = 0
                        
                        # Main
                        if self.active_trade["side"] == win_side:
                            payout += self.active_trade["shares"]
                        
                        # Hedge
                        if self.active_trade.get("hedged"):
                            if self.active_trade["hedge_side"] == win_side:
                                payout += self.active_trade["hedge_shares"]
                                
                        cost_total = self.active_trade["cost"] + self.active_trade.get("hedge_cost", 0)
                        profit = payout - cost_total
                        self.balance += payout
                        self.print_status(f"Result: {win_side} Wins. P&L: ${profit:.2f}. Bal: ${self.balance:.2f}", log_to_file=True)
                    
                    self.market_url = url
                    self.market_data = {
                        "up_id": None, "down_id": None, 
                        "up_price": 0.0, "down_price": 0.0,
                        "btc_price": self.market_data["btc_price"], 
                        "open_price": 0.0, "start_ts": ts_start
                    }
                    self.active_trade = None
                    self.checkpoints = {}
                    self.print_status(f"NEW WINDOW {start_dt.strftime('%H:%M')}", log_to_file=True)

                await self.fetch_spot_price()
                await self.fetch_market_data()
                
                elapsed = int(time.time() - ts_start)
                await self.process_strategy(elapsed)
                
                await asyncio.sleep(5)
            except KeyboardInterrupt: break
            except Exception as e:
                print(f"Loop Error: {e}")
                await asyncio.sleep(5)

    def init_csv_logging(self):
        self.csv_file = open(self.csv_filename, 'w', newline='')
        self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=['timestamp', 'elapsed', 'side', 'price', 'action', 'context_4h', 'context_atr'])
        self.csv_writer.writeheader()

    def log_checkpoint(self, elapsed, side, price, action):
        if self.csv_writer:
            self.csv_writer.writerow({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'elapsed': elapsed,
                'side': side,
                'price': price,
                'action': action,
                'context_4h': self.context['trend_4h'],
                'context_atr': f"{self.context['atr_24h_pct']:.2f}"
            })
            self.csv_file.flush()

if __name__ == "__main__":
    sim = LiveLinearSimulatorV4(balance=100.0)
    asyncio.run(sim.run())
