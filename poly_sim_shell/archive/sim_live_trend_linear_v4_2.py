"""
Version 4.2 (v4_2) - FULLY PLAYABLE
Simulator: News Sentiment & Order Book Walls + v3 Core Logic
------------------------------------------------------------
New Features:
1. News Shock Detector: Scans RSS for keywords (SEC, Hack, CPI). key: 'NEWS_SHOCK'
2. Order Book Walls: Checks CLOB liquidity depth before entry.

Base Logic (v3/v4):
- Hard Cap ($15)
- Time-of-Day Filter
- Exhaustion Filter (Max 4 consec)
- Partial Hedge (Loss Mitigation)
- Macro Trend (4H) & ATR Volatility (from v4)
"""

import requests
import time
import json
import asyncio
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
import os
import csv
import math

# --- Configuration ---
DRIFT_THRESHOLD = 0.0004
MAX_COST = 15.0      
MIN_COST = 5.50      
BAD_HOURS_UTC = {5, 8, 11, 16}
REDUCED_HOURS_UTC = {4, 13}
MAX_CONSECUTIVE_RISES = 5

# Keywords for News Shock
SHOCK_KEYWORDS = ["SEC ", "ETF ", "HACK", "EXPLOIT", "CPI ", "INFLATION", "FED ", "CRASH", "DUMP"]

class LiveLinearSimulatorV4_2:
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
        self.consecutive_wins = 0
        self.total_wins = 0
        self.total_losses = 0
        self.session_pnl = 0.0
        self.peak_balance = float(balance)
        self.window_count = 0
        self.windows_skipped = 0
        self.strategy_triggered = False
        
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

        # v4 Context
        self.context = {
            "trend_4h": "NEUTRAL",
            "trend_1h": "NEUTRAL",
            "atr_24h_pct": 0.0,
            "regime": "NORMAL",
            "news_shock": False,    # v4.2
            "last_news_ts": 0,
            "wall_score": 1.0       # v4.2 (>1 Bullish Wall, <1 Bearish Wall)
        }
        self.last_context_update = 0

        # Logging
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = os.path.join("data", f"sim_live_v4_2_log_{timestamp_str}.txt")
        self.csv_filename = os.path.join("data", f"sim_live_v4_2_detailed_{timestamp_str}.csv")
        os.makedirs("data", exist_ok=True)
        
        self.csv_file = None
        self.csv_writer = None
        self.init_csv_logging()

    def print_status(self, msg, log_to_file=False):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {msg}"
        print(line)
        if log_to_file:
            with open(self.log_file, "a", encoding='utf-8') as f:
                f.write(line + "\n")
    
    # --- v4.2: News Sentiment ---
    async def check_news_sentiment(self):
        """Scans RSS for shock keywords."""
        try:
            # CoinDesk or Cointelegraph RSS
            url = "https://cointelegraph.com/rss"
            resp = await asyncio.to_thread(self.session.get, url, timeout=4.0)
            
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                latest_items = root.findall("./channel/item")[:5] # Top 5 news
                
                shock_detected = False
                for item in latest_items:
                    title_elem = item.find("title")
                    if title_elem is None: continue
                    title = title_elem.text.upper()
                    
                    for kw in SHOCK_KEYWORDS:
                        if kw in title:
                            self.print_status(f"⚠️ NEWS SHOCK DETECTED: {kw} in '{title}'", log_to_file=True)
                            shock_detected = True
                            self.context["last_news_ts"] = time.time()
                            break
                    if shock_detected: break
                
                # Decay shock after 15 mins
                if shock_detected:
                    self.context["news_shock"] = True
                elif self.context["news_shock"] and time.time() - self.context["last_news_ts"] > 900:
                    self.context["news_shock"] = False
                    self.print_status("NEWS SHOCK CLEARED. Resuming normal operations.", log_to_file=True)
                    
        except Exception as e:
            pass

    # --- v4.2: Order Book Analysis ---
    async def analyze_order_book(self, token_id):
        """
        Fetches CLOB book. 
        Returns 'Wall Ratio' = Support (Bids) / Resistance (Asks).
        """
        try:
            url = f"https://clob.polymarket.com/book"
            params = {"token_id": token_id}
            resp = await asyncio.to_thread(self.session.get, url, params=params, timeout=2.0)
            data = resp.json()
            
            bids = data.get("bids", [])
            asks = data.get("asks", [])
            
            if not bids or not asks: return 1.0
            
            # Filter depth within 5 cents of top
            best_bid = float(bids[0]["price"])
            best_ask = float(asks[0]["price"])
            
            bid_vol = sum(float(b["size"]) for b in bids if float(b["price"]) >= best_bid - 0.05)
            ask_vol = sum(float(a["size"]) for a in asks if float(a["price"]) <= best_ask + 0.05)
            
            if ask_vol == 0: return 2.0
            ratio = bid_vol / ask_vol
            
            self.print_status(f"  [ORDER BOOK] Bids: {bid_vol:.0f} | Asks: {ask_vol:.0f} | Ratio: {ratio:.2f}", log_to_file=True)
            return ratio
            
        except: return 1.0

    async def update_context(self):
        """Combined Context Update (Macro + News)"""
        now = time.time()
        
        # News (Every 60s)
        if now - self.last_context_update > 60:
            await self.check_news_sentiment()

            # Macro Trend Update (Every 5 mins)
            if now - self.last_context_update > 300:
                 # --- ATTEMPT 1: BINANCE ---
                 try:
                    url = "https://api.binance.com/api/v3/klines"
                    
                    # 4H Trend
                    p_4h = {"symbol": "BTCUSDT", "interval": "4h", "limit": 10}
                    r_4h = await asyncio.to_thread(self.session.get, url, params=p_4h, timeout=2)
                    k_4h = r_4h.json()
                    if k_4h:
                        closes = [float(x[4]) for x in k_4h]
                        sma_short = sum(closes[-3:]) / 3
                        sma_long = sum(closes) / len(closes)
                        if sma_short > sma_long * 1.002: self.context["trend_4h"] = "UP"
                        elif sma_short < sma_long * 0.998: self.context["trend_4h"] = "DOWN"
                        else: self.context["trend_4h"] = "NEUTRAL"
                    
                    # 1H ATR
                    p_1h = {"symbol": "BTCUSDT", "interval": "1h", "limit": 24}
                    r_1h = await asyncio.to_thread(self.session.get, url, params=p_1h, timeout=2)
                    k_1h = r_1h.json()
                    
                    if k_1h:
                        closes_1h = [float(x[4]) for x in k_1h]
                        highs = [float(x[2]) for x in k_1h]
                        lows = [float(x[3]) for x in k_1h]
                        tr_sum = 0
                        for i in range(1, len(k_1h)):
                            tr = max(highs[i]-lows[i], abs(highs[i]-closes_1h[i-1]), abs(lows[i]-closes_1h[i-1]))
                            tr_sum += tr
                        atr = tr_sum / (len(k_1h)-1)
                        self.context["atr_24h_pct"] = (atr / closes_1h[-1]) * 100
                        
                        if self.context["atr_24h_pct"] < 0.5: self.context["regime"] = "LOW_VOL"
                        elif self.context["atr_24h_pct"] > 1.2: self.context["regime"] = "HIGH_VOL"
                        else: self.context["regime"] = "NORMAL"

                    self.print_status(f"CONTEXT UPDATE (BN): 4H={self.context['trend_4h']} | ATR={self.context['atr_24h_pct']:.2f}% ({self.context['regime']}) | SHOCK={self.context['news_shock']}", log_to_file=True)
                 
                 except Exception:
                     # --- ATTEMPT 2: COINBASE (Fallback) ---
                     try:
                        # Coinbase uses [time, low, high, open, close, volume]
                        # 6H Candles (Proxy for 4H)
                        url_cb = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
                        
                        # 1. Trend (6H)
                        p_6h = {"granularity": 21600} # 6h
                        r_6h = await asyncio.to_thread(self.session.get, url_cb, params=p_6h, timeout=2)
                        k_6h = r_6h.json() # Returns latest first
                        if k_6h and len(k_6h) > 5:
                            # Reverse to chronological for SMA calc
                            k_6h = k_6h[:10][::-1] 
                            closes = [float(x[4]) for x in k_6h]
                            sma_short = sum(closes[-3:]) / 3
                            sma_long = sum(closes) / len(closes)
                            if sma_short > sma_long * 1.002: self.context["trend_4h"] = "UP"
                            elif sma_short < sma_long * 0.998: self.context["trend_4h"] = "DOWN"
                            else: self.context["trend_4h"] = "NEUTRAL"

                        # 2. ATR (1H)
                        p_1h = {"granularity": 3600}
                        r_1h = await asyncio.to_thread(self.session.get, url_cb, params=p_1h, timeout=2)
                        k_1h = r_1h.json()
                        if k_1h and len(k_1h) > 24:
                            k_1h = k_1h[:24][::-1]
                            closes_1h = [float(x[4]) for x in k_1h]
                            highs = [float(x[2]) for x in k_1h]
                            lows = [float(x[1]) for x in k_1h] # Index 1 is LOW in CB
                            
                            tr_sum = 0
                            for i in range(1, len(k_1h)):
                                tr = max(highs[i]-lows[i], abs(highs[i]-closes_1h[i-1]), abs(lows[i]-closes_1h[i-1]))
                                tr_sum += tr
                            atr = tr_sum / (len(k_1h)-1)
                            self.context["atr_24h_pct"] = (atr / closes_1h[-1]) * 100
                            
                            if self.context["atr_24h_pct"] < 0.5: self.context["regime"] = "LOW_VOL"
                            elif self.context["atr_24h_pct"] > 1.2: self.context["regime"] = "HIGH_VOL"
                            else: self.context["regime"] = "NORMAL"

                        self.print_status(f"CONTEXT UPDATE (CB): 4H(6H)={self.context['trend_4h']} | ATR={self.context['atr_24h_pct']:.2f}% ({self.context['regime']})", log_to_file=True)
                     except Exception as e:
                         self.print_status(f"Context Fail: {e}", log_to_file=True)
                 
            self.last_context_update = now

    # --- Sizing ---
    def calculate_trade_cost(self, strategy_type, budget_pct, bb_multiplier=1.0):
        base_cost = self.balance * budget_pct
        notes = []
        cost = base_cost
        
        if self.use_bb_sizing:
             cost *= bb_multiplier
             if abs(bb_multiplier - 1.0) > 0.05: notes.append(f"BB {bb_multiplier:.2f}x")

        # v4 Macro Adjustments
        if strategy_type == "UPTREND":
            if self.context["trend_4h"] == "DOWN":
                cost *= 0.5
                notes.append("against-4h(50%)")
            elif self.context["trend_4h"] == "NEUTRAL" and self.context["regime"] == "LOW_VOL":
                cost *= 0.6
                notes.append("low-vol(60%)")
        
        # v4.2 Walls
        wall_score = self.context["wall_score"]
        if wall_score > 2.0:
            cost *= 1.2
            notes.append(f"wall-boost({wall_score:.1f}x)")
        elif wall_score < 0.5:
            cost *= 0.5
            notes.append("resistance-wall(50%)")
            
        # v4.2 News Halt
        if self.context["news_shock"]:
            cost = 0.0
            notes.append("NEWS-SHOCK-HALT")
            
        # v3 Caps & Filters
        if cost > MAX_COST: 
            notes.append(f"cap->${MAX_COST}")
            cost = MAX_COST
        
        current_hour = datetime.now(timezone.utc).hour
        if current_hour in BAD_HOURS_UTC:
            cost *= 0.60
            notes.append(f"bad-hour({current_hour}h)")
        
        if self.consecutive_losses >= 2:
            cost *= 0.70
            notes.append(f"streak({self.consecutive_losses}L)")
            
        cost = max(MIN_COST if cost > 0 else 0, cost)
        self._last_sizing_notes = notes
        return cost
        
    def calculate_bollinger_metrics(self):
        # Improved BB Calc
        BB_PERIOD = 36
        default = {"position": 0.5, "size_multiplier": 1.0}
        if len(self.checkpoints) < BB_PERIOD: return default
        
        prices = [self.checkpoints[t] for t in sorted(self.checkpoints.keys())[-BB_PERIOD:]]
        sma = sum(prices) / len(prices)
        std = (sum((p-sma)**2 for p in prices) / len(prices)) ** 0.5
        upper = sma + 2*std
        lower = sma - 2*std
        width = upper - lower
        
        pos = 0.5
        if width > 0:
            pos = (prices[-1] - lower) / width
            pos = max(0.0, min(1.0, pos))
            
        mult = 1.5 - (abs(pos - 0.5) * 2.0)
        mult = max(0.5, min(1.5, mult))
        
        return {"position": pos, "size_multiplier": mult}

    # --- Data Fetching ---
    async def fetch_spot_price(self):
        # Attempt 1: Binance
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
                         self.print_status(f"OPEN PRICE SET: {price:,.2f}", log_to_file=True)
                return
        except: pass

        # Attempt 2: Coinbase (Fallback)
        try:
            url = "https://api.coinbase.com/v2/prices/BTC-USD/spot"
            resp = await asyncio.to_thread(self.session.get, url, timeout=2.0)
            data = resp.json()
            if "data" in data and "amount" in data["data"]:
                price = float(data["data"]["amount"]) + self.btc_offset
                self.market_data["btc_price"] = price
                # Open Price Logic (Duplicate for fallback)
                if self.market_data["open_price"] == 0 and self.market_data["start_ts"] > 0:
                     if (time.time() - self.market_data["start_ts"]) < 300:
                         self.market_data["open_price"] = price
                         self.print_status(f"OPEN PRICE SET (CB): {price:,.2f}", log_to_file=True)
        except: pass

    async def fetch_market_data(self):
        # Fetch IDs
        if not self.market_data["up_id"] and self.market_url:
            try:
                slug = self.market_url.split("/")[-1].split("?")[0]
                url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
                resp = await asyncio.to_thread(self.session.get, url, timeout=2.0)
                if "clobTokenIds" in resp.json():
                    ids = json.loads(resp.json()["clobTokenIds"])
                    self.market_data["up_id"] = ids[0]
                    self.market_data["down_id"] = ids[1]
            except: pass
            
        # Fetch Prices
        if self.market_data["up_id"]:
            try:
                url = "https://clob.polymarket.com/price"
                p1 = await asyncio.to_thread(self.session.get, url, params={"token_id": self.market_data["up_id"], "side": "buy"})
                p2 = await asyncio.to_thread(self.session.get, url, params={"token_id": self.market_data["down_id"], "side": "buy"})
                if p1.status_code == 200: self.market_data["up_price"] = float(p1.json().get("price", 0))
                if p2.status_code == 200: self.market_data["down_price"] = float(p2.json().get("price", 0))
            except: pass

    # --- Process Strategy ---
    async def process_strategy(self, elapsed):
        btc = self.market_data["btc_price"]
        op = self.market_data["open_price"]
        drift = abs(btc - op) / op if op > 0 else 0
        leader_side = "UP" if btc > op else "DOWN"
        leader_price = self.market_data["up_price"] if leader_side == "UP" else self.market_data["down_price"]
        
        self.log_checkpoint(elapsed, leader_side, leader_price, "MONITOR")
        
        if self.active_trade:
            # v3 Partial Hedge Logic (Mitigation)
            if not self.active_trade.get("hedged") and elapsed > 600:
                cost = self.active_trade["cost"]
                price = self.market_data["up_price"] if self.active_trade["side"] == "UP" else self.market_data["down_price"]
                opp_price = self.market_data["down_price"] if self.active_trade["side"] == "UP" else self.market_data["up_price"]
                
                # Condition: Losing Badly (<0.20) + Opp Winning (>0.80)
                if price < 0.20 and opp_price > 0.80:
                    hedge_amt = cost * 0.30
                    if self.balance >= hedge_amt:
                        self.balance -= hedge_amt
                        self.active_trade["hedged"] = True
                        self.active_trade["hedge_cost"] = hedge_amt
                        self.active_trade["hedge_shares"] = hedge_amt / opp_price
                        self.active_trade["hedge_side"] = "DOWN" if self.active_trade["side"] == "UP" else "UP"
                        self.print_status(f"PARTIAL HEDGE: Spent ${hedge_amt:.2f} to mitigate loss.", log_to_file=True)
                        
                        self.log_checkpoint(elapsed, self.active_trade["hedge_side"], opp_price, "HEDGE_PARTIAL", cost=hedge_amt)
            return

        if self.strategy_triggered: return

        # Sampling
        if 300 <= elapsed <= 780 and not self.active_trade:
            if elapsed not in self.checkpoints:
                self.checkpoints[elapsed] = leader_price
                self.scan_count += 1
                
                if (elapsed % 30 == 0) or (self.scan_count == 1):
                    mins = elapsed // 60
                    secs = elapsed % 60
                    self.print_status(f"  [Scan T+{mins}:{secs:02d}] {leader_side} leads | Price:{leader_price:.2f} | Drift:{drift:.3%} (#{self.scan_count})", log_to_file=True)
                
                # --- SIGNAL 1: Strong Uptrend (Start to Mid Game: T+5 to T+9) ---
                if elapsed <= 540:
                    times = sorted(self.checkpoints.keys())
                    recent = [self.checkpoints[t] for t in times if elapsed - t <= 90]
                    if len(recent) >= 3:
                         # Calculate momentum
                         start_p = recent[0]
                         end_p = recent[-1]
                         mom = end_p - start_p
                         
                         consec = 0
                         max_consec = 0
                         for i in range(1, len(recent)):
                             if recent[i] > recent[i-1]: consec += 1
                             else: consec = 0
                             max_consec = max(max_consec, consec)
                         
                         if max_consec >= MAX_CONSECUTIVE_RISES + 1: return
                         
                         if (mom >= 0.25 and max_consec >= 3 and drift > DRIFT_THRESHOLD 
                             and leader_price < 0.85 and leader_price > 0.10):
                             
                             # v4.2: CHECK WALLS
                             token_id_target = self.market_data["up_id"] if leader_side == "UP" else self.market_data["down_id"]
                             self.context["wall_score"] = await self.analyze_order_book(token_id_target)
                             
                             if self.context["wall_score"] < 0.4:
                                 self.print_status(f"SKIP ENTRY: Resistance Wall too thick (Ratio {self.context['wall_score']:.2f})", log_to_file=True)
                                 return
                             
                             bb = self.calculate_bollinger_metrics()
                             budget_pct = 0.20 if leader_price < 0.72 else 0.12
                             cost = self.calculate_trade_cost("UPTREND", budget_pct, bb["size_multiplier"])
                             
                             if cost > 0 and self.balance >= cost:
                                 self.balance -= cost
                                 shares = cost / leader_price
                                 self.active_trade = {"side": leader_side, "entry": leader_price, "cost": cost, "shares": shares, "type": "UPTREND"}
                                 self.strategy_triggered = True
                                 
                                 sizing_info = f" | Sizing: {', '.join(self._last_sizing_notes)}" if self._last_sizing_notes else ""
                                 self.print_status(f"BUY {leader_side} @ {leader_price:.2f} | Cost ${cost:.2f} | Context: 4H={self.context['trend_4h']} ATR={self.context['atr_24h_pct']:.2f}% | Wall: {self.context['wall_score']:.2f}{sizing_info}", log_to_file=True)
                                 self.log_checkpoint(elapsed, leader_side, leader_price, "TRADE_UPTREND", cost=cost)

                # --- SIGNAL 2: Late Game Sniper (T+11 to T+13) ---
                elif 660 <= elapsed <= 780:
                    # Conditions:
                    # 1. Price is high confidence but not locked (0.80 - 0.92)
                    # 2. Drift is SIGNIFICANT (> 0.30%) - implies distinct move
                    # 3. Macro 4H matches perfectly (Confluence)
                    
                    if (0.80 <= leader_price <= 0.92) and (drift > 0.003): # 0.3%
                        # Check Macro
                        if (leader_side == "UP" and self.context["trend_4h"] == "UP") or \
                           (leader_side == "DOWN" and self.context["trend_4h"] == "DOWN"):
                               
                               cost = self.calculate_trade_cost("LATE_SNIPER", 0.12) # Conservative size
                               
                               if cost > 0 and self.balance >= cost:
                                   self.balance -= cost
                                   shares = cost / leader_price
                                   self.active_trade = {"side": leader_side, "entry": leader_price, "cost": cost, "shares": shares, "type": "LATE_SNIPER"}
                                   self.strategy_triggered = True
                                   
                                   self.print_status(f"SNIPE {leader_side} @ {leader_price:.2f} | Cost ${cost:.2f} | Drift {drift:.3%} | 4H Matched", log_to_file=True)
                                   self.log_checkpoint(elapsed, leader_side, leader_price, "TRADE_SNIPE", cost=cost)

    def print_status_line(self, elapsed):
        btc = self.market_data["btc_price"]
        op = self.market_data["open_price"]
        up = self.market_data["up_price"]
        dn = self.market_data["down_price"]
        drift = abs(btc - op) / op if op > 0 else 0
        rem = 900 - elapsed
        trade = f"ACTIVE ({self.active_trade['type']})" if self.active_trade else "SCAN"
        
        # Add tiny indicators for context
        ctx = f"4H:{self.context['trend_4h'][0]} ATR:{self.context['atr_24h_pct']:.1f}%"
        
        print(f"\r[T-{rem}s] BTC:{btc:,.0f} | UP:{up:.2f} DN:{dn:.2f} | {trade} | {ctx} | Bal:${self.balance:.2f}   ", end="", flush=True)

    # --- Main Loop ---
    async def run(self):
        self.print_status(f"--- SIMULATOR v4.2 (News & Walls) ---", log_to_file=True)
        self.print_status(f"Balance: ${self.balance:.2f}", log_to_file=True)
        self.print_status(f"Log File: {self.log_file}")
        self.print_status(f"CSV File: {self.csv_filename}")
        
        while self.is_running:
            try:
                await self.update_context()
                
                now = datetime.now(timezone.utc)
                min15 = (now.minute // 15) * 15
                start_dt = now.replace(minute=min15, second=0, microsecond=0)
                ts_start = int(start_dt.timestamp())
                url = f"https://polymarket.com/event/btc-updown-15m-{ts_start}"

                if url != self.market_url:
                    # Settle old window
                    if self.market_url and self.active_trade:
                        self.print_status("\nSettling window...", log_to_file=True)
                        btc = self.market_data["btc_price"]
                        op = self.market_data["open_price"]
                        win_side = "UP" if btc > op else "DOWN"
                        payout = 0
                        
                        # Main Payout
                        if self.active_trade["side"] == win_side:
                            payout += self.active_trade["shares"]
                        
                        # Hedge Payout
                        if self.active_trade.get("hedged"):
                            if self.active_trade["hedge_side"] == win_side:
                                payout += self.active_trade["hedge_shares"]
                                
                        cost_total = self.active_trade["cost"] + self.active_trade.get("hedge_cost", 0)
                        profit = payout - cost_total
                        self.balance += payout
                        self.session_pnl += profit
                        
                        if profit > 0: 
                            self.consecutive_wins += 1
                            self.consecutive_losses = 0
                            result = "WIN"
                        elif profit < 0: 
                            self.consecutive_losses += 1
                            self.consecutive_wins = 0
                            result = "LOSS"
                        else: result = "BREAK-EVEN"
                        
                        self.print_status(f"RESULT: {result} ({win_side}) | P&L: ${profit:+.2f} | Bal: ${self.balance:.2f}", log_to_file=True)
                    
                    self.market_url = url
                    self.window_count += 1
                    self.market_data = {
                        "up_id": None, "down_id": None, 
                        "up_price": 0.0, "down_price": 0.0,
                        "btc_price": self.market_data["btc_price"], 
                        "open_price": 0.0, "start_ts": ts_start
                    }
                    self.active_trade = None
                    self.strategy_triggered = False
                    self.checkpoints = {}
                    
                    self.print_status(f"\n[{start_dt.strftime('%H:%M')} TC] WINDOW #{self.window_count}", log_to_file=True)

                await self.fetch_spot_price()
                await self.fetch_market_data()
                
                elapsed = int(time.time() - ts_start)
                self.print_status_line(elapsed)
                
                if self.market_data["open_price"] > 0:
                    await self.process_strategy(elapsed)
                
                await asyncio.sleep(5)
            except KeyboardInterrupt: break
            except Exception as e:
                print(f"Loop Error: {e}")
                await asyncio.sleep(5)

    def init_csv_logging(self):
        self.csv_file = open(self.csv_filename, 'w', newline='')
        self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=[
            'timestamp', 'elapsed', 'btc_price', 'open_price', 'up_price', 'down_price',
            'side', 'price', 'action', 'cost', 
            'context_4h', 'context_atr', 'context_wall', 'context_news'
        ])
        self.csv_writer.writeheader()

    def log_checkpoint(self, elapsed, side, price, action, cost=0):
        if self.csv_writer:
            self.csv_writer.writerow({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'elapsed': elapsed,
                'btc_price': f"{self.market_data['btc_price']:.2f}",
                'open_price': f"{self.market_data['open_price']:.2f}",
                'up_price': f"{self.market_data['up_price']:.3f}",
                'down_price': f"{self.market_data['down_price']:.3f}",
                'side': side,
                'price': f"{price:.3f}",
                'action': action,
                'cost': f"{cost:.2f}",
                'context_4h': self.context['trend_4h'],
                'context_atr': f"{self.context['atr_24h_pct']:.2f}",
                'context_wall': f"{self.context['wall_score']:.2f}",
                'context_news': str(self.context['news_shock'])
            })
            self.csv_file.flush()

if __name__ == "__main__":
    print("--- SIMULATOR v4.2 (News & Walls) ---")
    
    # Prompt for Balance
    start_bal = 20.0
    try:
        ans = input(f"Starting Balance [Default $20]: ").strip()
        if ans:
            start_bal = float(ans)
    except: pass
    
    sim = LiveLinearSimulatorV4_2(balance=start_bal)
    try:
        asyncio.run(sim.run())
    except KeyboardInterrupt:
        print("\nStopped.")
