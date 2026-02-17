import json
import time
import threading
import os
import csv
import random
from datetime import datetime
from urllib.request import urlopen, Request
import signal
import sys

# --- CONFIGURATION ---
BINANCE_API_URL = "https://api.binance.com/api/v3"
POLY_API_URL = "https://clob.polymarket.com"
GAMMA_API_URL = "https://gamma-api.polymarket.com"

# --- SCANNERS (Ported from server.py) ---

class NPatternScanner:
    def __init__(self):
        self.min_impulse_size = 0.0003
        self.max_retrace_depth = 0.85
        self.support_tolerance = 0.002
        self.triggered_signal = None
        
    def reset(self):
        self.triggered_signal = None
        
    def analyze(self, history_objs, open_price):
        if self.triggered_signal and "BET_" in self.triggered_signal:
            return self.triggered_signal
            
        if not history_objs: return "WAIT"

        # Phase 1: Mins 0-3 (0-180s)
        phase1_prices = [p['price'] for p in history_objs if p['elapsed'] <= 180]
        if not phase1_prices: return "WAIT"
            
        first_peak = max(phase1_prices)
        impulse_height = first_peak - open_price
        
        if impulse_height < (open_price * self.min_impulse_size):
            return "WAIT" 
            
        peak_idx = next(i for i, p in enumerate(history_objs) if p['price'] == first_peak)
        retrace_objs = history_objs[peak_idx:]
        
        if not retrace_objs: return "WAIT"
            
        retrace_prices = [p['price'] for p in retrace_objs]
        retest_low = min(retrace_prices)
        
        failed_support = retest_low < (open_price * (1 - self.support_tolerance))
        retrace_pct = (first_peak - retest_low) / impulse_height if impulse_height > 0 else 0
        valid_dip = 0.20 <= retrace_pct <= self.max_retrace_depth
        
        if failed_support: return "PATTERN_INVALID"
        if not valid_dip: return "WAIT"
            
        current_price = history_objs[-1]['price']
        breakout = current_price > first_peak
        
        if breakout and valid_dip:
            self.triggered_signal = f"BET_UP_CONFIRMED|Breakout above {first_peak:.2f}"
            return self.triggered_signal
            
        return "WAIT"

class FakeoutScanner:
    def __init__(self):
        self.triggered_signal = None

    def reset(self):
        self.triggered_signal = None

    def analyze(self, history_objs, open_price, prev_window_color):
        if self.triggered_signal: return self.triggered_signal
        if not history_objs or not prev_window_color: return "NO_SIGNAL"
            
        early_prices = [p['price'] for p in history_objs if p['elapsed'] <= 180]
        if not early_prices: return "NO_SIGNAL"
            
        spike_high = max(early_prices)
        current_price = history_objs[-1]['price']
        
        local_signal = False
        if (spike_high > open_price) and (current_price < open_price):
            local_signal = True 
            
        if local_signal:
            if prev_window_color == "RED":
                self.triggered_signal = f"BET_DOWN_AGGRESSIVE|Rejected Rescue & Trend Align"
            elif prev_window_color == "GREEN":
                self.triggered_signal = f"WAIT_FOR_CONFIRMATION|Rejected Rescue vs Trend"
            return self.triggered_signal
                
        return "NO_SIGNAL"

class TailWagScanner:
    def __init__(self):
        self.triggered_signal = None
        
    def reset(self):
        self.triggered_signal = None

    def analyze(self, time_remaining, poly_volume, spot_depth, leader_direction, spot_price, price_history):
        if self.triggered_signal: return self.triggered_signal
        if time_remaining >= 180: return "WAIT_TIME"
        if not poly_volume or not spot_depth or spot_depth == 0: return "NO_DATA"
            
        if float(poly_volume) > (float(spot_depth) * 1.5):
            # NEW: Spot Reaction Test
            # Check last 30s of spot price history
            recent_prices = [p['price'] for p in price_history if p['elapsed'] >= (900-time_remaining-30)]
            if not recent_prices: return "WAIT_DATA"
            
            start_p = recent_prices[0]
            end_p = recent_prices[-1]
            move_pct = (end_p - start_p) / start_p
            
            # Confirm Spot is moving with the Whale
            confirmed = False
            if leader_direction == "UP" and move_pct > 0.0005: confirmed = True
            elif leader_direction == "DOWN" and move_pct < -0.0005: confirmed = True
            
            if confirmed:
                self.triggered_signal = f"WHALE_LEADER_{leader_direction}|Whale vol > 1.5x Cost + Spot Reacted"
                return self.triggered_signal
            
        return "NO_SIGNAL"


class RsiScanner:
    def __init__(self):
        self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, rsi, price, bb_lower, time_remaining):
        if self.triggered_signal: return self.triggered_signal
        if rsi < 15 and price < bb_lower and time_remaining > 300:
            self.triggered_signal = f"BET_UP_RSI_OVERSOLD|RSI {rsi:.1f} + Below BB"
            return self.triggered_signal
        return "WAIT"

class TrapCandleScanner:
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, price_history, open_price):
        if self.triggered_signal: return self.triggered_signal
        if not price_history: return "NO_DATA"
        try:
            p3_candle = next((x for x in price_history if x['elapsed'] >= 180), None)
            if p3_candle:
                start_move = abs(p3_candle['price'] - open_price)
                current_move = abs(price_history[-1]['price'] - open_price)
                if (start_move / open_price > 0.003) and (current_move < start_move * 0.25): # 75% retrace
                    self.triggered_signal = "BET_DOWN_FADE_BREAKOUT|Flash Crash >75% retraced"
                    return self.triggered_signal
        except: pass
        return "WAIT"

class MidGameScanner:
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, price_history, open_price, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if elapsed < 300: return "WAIT_TIME"
        crossed_up = any(x['price'] > open_price for x in price_history if 300 <= x['elapsed'] <= 600)
        green_ticks = sum(1 for x in price_history if x['price'] > open_price and 300 <= x['elapsed'] <= 600)
        if crossed_up and green_ticks < 20 and price_history[-1]['price'] < open_price and elapsed > 600:
             self.triggered_signal = "BET_DOWN_FAILED_RESCUE|Bulls failed to hold green"
             return self.triggered_signal
        return "WAIT"

class LateReversalScanner:
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, price_history, open_price, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if elapsed < 660: return "WAIT_TIME"
        early_low = min([x['price'] for x in price_history if x['elapsed'] < 420], default=open_price)
        if early_low >= open_price * 0.999: return "WAIT_NO_DROP"
        crossed = any(x['price'] > open_price for x in price_history if 420 <= x['elapsed'] <= 600)
        if not crossed: return "WAIT_NO_CROSS"
        if price_history[-1]['price'] > open_price * 1.0005:
            self.triggered_signal = "BET_UP_LATE_REVERSAL|Late surge to green"
            return self.triggered_signal
        return "WAIT"

class StaircaseBreakoutScanner:
    def __init__(self): 
        self.triggered_signal = None
    
    def reset(self): 
        self.triggered_signal = None
    
    def analyze(self, close_prices):
        if self.triggered_signal: return self.triggered_signal
        if len(close_prices) < 20: return "WAIT_DATA"
        
        # Analyze last 15 candles for staircase pattern
        window = close_prices[-15:]
        
        # Find local lows (simple approach: prices lower than neighbors)
        lows = []
        for i in range(1, len(window) - 1):
            if window[i] <= window[i-1] and window[i] <= window[i+1]:
                lows.append(window[i])
        
        # Need at least 3 swing lows to form a staircase
        if len(lows) < 3: return "WAIT_PATTERN"
        
        # Check if lows are ascending (staircase)
        is_ascending = all(lows[i] < lows[i+1] for i in range(len(lows)-1))
        
        if not is_ascending: return "WAIT_STAIRCASE"
        
        # Check for breakout above recent high
        recent_high = max(window)
        current_price = window[-1]
        
        # Require move >0.2% to confirm strength
        min_low = min(window)
        if (recent_high - min_low) < (min_low * 0.002): return "WAIT_WEAK"
        
        # Trigger if near or above recent high
        if current_price >= (recent_high * 0.9995):
             self.triggered_signal = "BET_UP_AGGRESSIVE|Staircase Breakout Confirmed"
             return self.triggered_signal
        
        return "WAIT"

class PostPumpScanner:
    def __init__(self): 
        self.triggered_signal = None
    
    def reset(self): 
        self.triggered_signal = None
    
    def analyze(self, current_price, current_open, last_window):
        if self.triggered_signal: return self.triggered_signal
        
        # Require previous window pumped >0.5%
        if not last_window or last_window.get('change_pct', 0) < 0.005: 
            return "WAIT"
        
        # Calculate midpoint of previous window's range
        midpoint = last_window['open'] + (last_window['height'] * 0.5)
        
        # If prev window was GREEN (pump up)  
        if last_window['close'] > last_window['open']:
            # Bet DOWN if fading below midpoint AND below current open
            if current_price < midpoint and current_price < current_open:
                self.triggered_signal = "BET_DOWN|Post-Pump Fade Below Midpoint"
                return self.triggered_signal
        
        # If prev window was RED (dump down)
        elif last_window['close'] < last_window['open']:
            # Bet UP if rallying above midpoint AND above current open
            if current_price > midpoint and current_price > current_open:
                self.triggered_signal = "BET_UP|Post-Dump Rally Above Midpoint"
                return self.triggered_signal
        
        return "WAIT"

class StepClimberScanner:
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, close_prices):
        if self.triggered_signal: return self.triggered_signal
        if len(close_prices) < 20: return "WAIT"
        ma20 = sum(close_prices[-20:]) / 20
        dist = abs(close_prices[-1] - ma20)
        if dist < (close_prices[-1] * 0.0015) and close_prices[-1] > ma20:
             self.triggered_signal = "SNIPER_ENTRY_UP|Perfect touch of MA20"
             return self.triggered_signal
        return "WAIT"

class SlingshotScanner:
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, close_prices):
        if self.triggered_signal: return self.triggered_signal
        if len(close_prices) < 10: return "WAIT"
        ma = sum(close_prices[-20:]) / 20
        if close_prices[-1] > ma and (close_prices[-2] < ma or close_prices[-3] < ma):
             self.triggered_signal = "MAX_BET_UP_RECLAIM|Reclaimed MA20"
             return self.triggered_signal
        return "WAIT"

class MinOneScanner:
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, price_history, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if elapsed < 60 or elapsed > 130: return "WAIT"
        min1 = [x for x in price_history if x['elapsed'] <= 60]
        if not min1: return "WAIT"
        h = max(x['price'] for x in min1)
        l = min(x['price'] for x in min1)
        c = min1[-1]['price']; o = min1[0]['price']
        body = abs(c - o)
        if (h - max(o, c)) > body * 1.5:
             self.triggered_signal = "BET_DOWN_WICK|Liar's Wick Detected"
             return self.triggered_signal
        if (min(o, c) - l) > body * 1.5:
             self.triggered_signal = "BET_UP_WICK|Liar's Wick Detected"
             return self.triggered_signal
        return "WAIT"

class LiquidityVacuumScanner:
    def __init__(self): 
        self.triggered_signal = None
        self.swept = False  # Track if we've swept below swing low
        self.sweep_high = 0 # Track high of the sweep candle
    
    def reset(self): 
        self.triggered_signal = None
        self.swept = False
        self.sweep_high = 0
    
    def analyze(self, current_price, swing_low, open_price):
        if self.triggered_signal: return self.triggered_signal
        if swing_low == 0: return "WAIT"
        
        # Phase 1: Detect sweep below swing low
        # Record the high of this 'sweep event' to ensure we break structure on reclaim
        if current_price < swing_low:
            self.swept = True
            if current_price > self.sweep_high: self.sweep_high = current_price # Simple tracking
            return "SWEEP_DETECTED"
        
        # Phase 2: Trigger only after reclaim AND structure shift
        # Price must reclaim swing low AND be higher than recent volatility (simplified as +0.02%)
        # or break the sweep high if we tracked it better. Here we use a buffer.
        buffer = swing_low * 1.0002
        
        if self.swept and current_price > buffer:
            self.triggered_signal = f"BET_UP_LIQ_SWEEP|Swept {swing_low:.2f} then broke structure >{buffer:.2f}"
            return self.triggered_signal
        
        return "WAIT"

class CobraScanner:
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, closes_60m, current_price, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if elapsed > 180 or len(closes_60m) < 20: return "WAIT"
        # BB Calculation
        slice_ = closes_60m[-20:]
        sma = sum(slice_) / 20
        std = (sum((x - sma) ** 2 for x in slice_) / 20) ** 0.5
        upper = sma + 2*std
        lower = sma - 2*std
        if current_price > upper:
            self.triggered_signal = "BET_UP_COBRA|Explosive breakout"
            return self.triggered_signal
        if current_price < lower:
            self.triggered_signal = "BET_DOWN_COBRA|Explosive breakdown"
            return self.triggered_signal
        return "WAIT"

class MesaCollapseScanner:
    def __init__(self): 
        self.triggered_signal = None
        self.state = "SEARCHING"  # SEARCHING → WATCHING_TOP → HUNTING_BREAK → EXECUTED
        self.mesa_floor = None
        self.pump_start_time = None
    
    def reset(self): 
        self.triggered_signal = None
        self.state = "SEARCHING"
        self.mesa_floor = None
        self.pump_start_time = None
    
    def analyze(self, price_history, open_price, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if elapsed < 180: return "WAIT_TIME"  # Need min 3 mins
        if not price_history: return "NO_DATA"
        
        current_price = price_history[-1]['price']
        
        # PHASE 1: SEARCHING - Detect initial pump
        if self.state == "SEARCHING":
            pct_gain = (current_price - open_price) / open_price if open_price > 0 else 0
            # Look for >0.15% pump in first 3 minutes
            if elapsed <= 180 and pct_gain > 0.0015:
                self.state = "WATCHING_TOP"
                self.pump_start_time = elapsed
                return "PUMP_DETECTED"
        
        # PHASE 2: WATCHING_TOP - Analyze for choppiness (Mesa pattern)
        elif self.state == "WATCHING_TOP":
            # Must have enough time passed since pump (at least 2 mins)
            if elapsed < (self.pump_start_time + 120): 
                return "WAIT_DEVELOP"
            
            # Get last 3 minutes of price data
            mesa_window = [p for p in price_history if (elapsed - 180) <= p['elapsed'] <= elapsed]
            if len(mesa_window) < 10: return "WAIT_DATA"
            
            prices = [p['price'] for p in mesa_window]
            ma = sum(prices) / len(prices)
            
            # Count MA crossovers (choppiness indicator)
            crosses = 0
            for i in range(1, len(prices)):
                prev_above = prices[i-1] > ma
                curr_above = prices[i] > ma
                if prev_above != curr_above:  # Crossover detected
                    crosses += 1
            
            # Is it choppy? (3+ crosses = messy top)
            is_choppy = crosses >= 3
            self.mesa_floor = min(prices)
            
            # If too clean and still rising, it's likely a bull flag (abort)
            if not is_choppy and current_price > ma * 1.001:
                self.reset()
                return "ABORT_BULL_FLAG"
            
            # If choppy, arm the trap and wait for break
            if is_choppy:
                self.state = "HUNTING_BREAK"
                return "MESA_ARMED"
        
        # PHASE 3: HUNTING_BREAK - Trigger on breakdown below mesa floor
        elif self.state == "HUNTING_BREAK":
            # REQ: Price must be < Floor for > 5 seconds continuously (The "Close" Proxy for 1s ticks)
            # OR simple logic: average of last 5 seconds < floor
            last_5 = [p['price'] for p in price_history[-5:]]
            if last_5 and max(last_5) < self.mesa_floor:
                self.triggered_signal = "BET_DOWN_HEAVY|Mesa Collapse Confirmed (5s Close)"
                self.state = "EXECUTED"
                return self.triggered_signal
        
        return "WAIT"

class MeanReversionScanner:
    def __init__(self):
        self.triggered_signal = None
        # Settings for 1s data
        self.period = 20
        self.std_dev_mult = 2.0
        
    def reset(self):
        self.triggered_signal = None
        
    def analyze(self, price_history, fast_bb):
        if self.triggered_signal: return self.triggered_signal
        if not fast_bb or len(price_history) < 20: return "WAIT"
        
        upper_band = fast_bb[0]
        current_price = price_history[-1]['price']
        
        # 1. IDENTIFY THE BREACH (ICARUS)
        # Look back 20 seconds. Did ANY candle breach the upper band?
        recent_history = price_history[-20:]
        breach_found = any(p['price'] > upper_band for p in recent_history)
        
        if not breach_found: return "WAIT"
        
        # 2. IDENTIFY THE SNAP
        # Current price must be INSIDE band
        if current_price >= upper_band: return "WAIT_STILL_OUTSIDE"
        
        # 3. CONFIRMATION: THE "DOUBLE TAP" CHECK (New Logic)
        # We need to confirm the high is "in" and we are not just wicking down.
        # Check if the last 5 seconds have been establishing Lower Highs or flat
        last_5 = recent_history[-5:]
        peak_price = max(p['price'] for p in recent_history)
        
        # If current is > 0.05% below peak, it's a hard rejection
        drop_pct = (peak_price - current_price) / peak_price
        
        if drop_pct > 0.0005: 
            self.triggered_signal = f"SHORT_THE_SNAP|Rejection {drop_pct*100:.2f}% from Top"
            return self.triggered_signal
            
        return "WAIT"

class GrindSnapScanner:
    def __init__(self):
        self.triggered_signal = None
        # Settings
        self.grind_time = 300 # 5 minutes
        self.snap_time = 60   # 1 minute
        
    def reset(self):
        self.triggered_signal = None
        
    def analyze(self, price_history, elapsed):
        if self.triggered_signal: return self.triggered_signal
        # Need Grind (300s) + Snap (60s) + Hold (30s)
        if elapsed < (self.grind_time + self.snap_time + 30): return "WAIT_TIME"
        if not price_history: return "WAIT"
        
        # Current Price (T)
        p_now = price_history[-1]['price']
        
        # Snap Start (T-30s? No, we check if the snap HAPPENED 30s ago)
        # We look for a Snap Event that concluded 30s ago. 
        # So elapsed time of snap end = elapsed - 30.
        
        snap_price_obj = next((x for x in reversed(price_history) if x['elapsed'] <= (elapsed - 30)), None)
        if not snap_price_obj: return "WAIT"
        p_snap_end = snap_price_obj['price']
        
        # Snap Start = elapsed - 30 - 60
        snap_start_obj = next((x for x in reversed(price_history) if x['elapsed'] <= (elapsed - 90)), None)
        if not snap_start_obj: return "WAIT"
        p_snap_start = snap_start_obj['price']
        
        # Grind Start = elapsed - 30 - 60 - 300
        grind_start_obj = next((x for x in reversed(price_history) if x['elapsed'] <= (elapsed - 390)), None)
        if not grind_start_obj: return "WAIT"
        p_grind_start = grind_start_obj['price']
        
        # 1. Grind Check
        grind_move = p_snap_start - p_grind_start
        if abs(grind_move / p_grind_start) < 0.001: return "WAIT_FLAT"
        
        # 2. Snap Check
        snap_move = p_snap_end - p_snap_start
        retrace = abs(snap_move / grind_move)
        
        # 3. Confirmation Check (The Hold)
        # Has price STAYED below the Snap End for the last 30s? 
        # (Assuming DOWN bet for UP grind)
        is_bearish_play = grind_move > 0
        
        failed_hold = False
        recent_30s = [p['price'] for p in price_history if p['elapsed'] > (elapsed - 30)]
        
        if is_bearish_play:
            # We want recent prices to be BELOW snap_start (or close to snap_end)
            # If any price broke above snap_start, it failed.
            if any(p > p_snap_start for p in recent_30s): failed_hold = True
        else:
            if any(p < p_snap_start for p in recent_30s): failed_hold = True
            
        if failed_hold: return "WAIT_FAILED_HOLD"
        
        if retrace > 0.60:
             direction = "DOWN" if is_bearish_play else "UP"
             self.triggered_signal = f"BET_{direction}_SNAP|Grind Snapped & Held 30s"
             return self.triggered_signal
             
        return "WAIT"

class VolCheckScanner:
    def __init__(self):
        self.triggered_signal = None
        # Settings
        self.min_avg_range = 10.0 # Min $ average range to consider valid
        self.safety_factor = 1.0  # Distance must be > 1.0x Avg 3m Range
        
    def reset(self):
        self.triggered_signal = None
        
    def calculate_avg_3m_range(self, closes_60m):
        # Need at least 30 mins (30 candles) to form good avg
        if len(closes_60m) < 30: return 0
        
        # Take last 45 mins
        window = closes_60m[-45:]
        ranges = []
        
        # Group into 3-minute chunks
        for i in range(0, len(window)-2, 3):
            chunk = window[i:i+3]
            if len(chunk) < 3: continue
            rng = max(chunk) - min(chunk)
            ranges.append(rng)
            
        if not ranges: return 0
        return sum(ranges) / len(ranges)
        
    def analyze(self, closes_60m, current_price, open_price, elapsed, up_p, down_p):
        if self.triggered_signal: return self.triggered_signal
        
        # 1. TIME CHECK: Only active in final 5 minutes (last 300s)
        time_left = 900 - elapsed
        if time_left > 300 or time_left < 30: return "WAIT_TIME"
        
        # 2. PRICE CHECK: Option price must be around 85-90 cents (High Confidence)
        # We check both sides. If UP is 85-90, we look to buy UP.
        target_side = None
        
        # Assuming Polymarket prices (up_p, down_p) are floats 0.0-1.0
        if 0.85 <= up_p <= 0.90: target_side = "UP"
        elif 0.85 <= down_p <= 0.90: target_side = "DOWN"
        
        if not target_side: return "WAIT_PRICE"
        if target_side == "UP" and up_p < 0.85: return "WAIT_Price" #Double check
        if target_side == "DOWN" and down_p < 0.85: return "WAIT_Price"
        
        # 3. VOLATILITY CHECK: Calculate Avg 3m Range
        avg_3m_range = self.calculate_avg_3m_range(closes_60m)
        if avg_3m_range < self.min_avg_range: return "WAIT_LOW_VOL"
        
        # 4. DISTANCE CHECK: Is the gap big enough?
        # Distance from current price to open price (breakeven point)
        dist_to_open = abs(current_price - open_price)
        
        # Are we winning?
        # If Target UP -> Current > Open
        # If Target DOWN -> Current < Open
        is_winning = (target_side == "UP" and current_price > open_price) or \
                     (target_side == "DOWN" and current_price < open_price)
        
        if not is_winning: return "WAIT_LOSING"
                     
        # Logic: If distance > Avg 3m Range, it's "Sufficiently Far"
        if dist_to_open > (avg_3m_range * self.safety_factor):
             self.triggered_signal = f"VOL_SAFE_{target_side}|Gap ${dist_to_open:.1f} > Avg3m ${avg_3m_range:.1f}"
             return self.triggered_signal
             
        return "WAIT"

class MosheSpecializedScanner:
    def __init__(self):
        self.triggered_signal = None
        self.checkpoints = {}
        self.scan_count = 0
        self.MAX_CONSECUTIVE_RISES = 5
        self.DRIFT_THRESHOLD = 0.0004
        
    def reset(self):
        self.triggered_signal = None
        self.checkpoints = {}
        self.scan_count = 0
        
    def analyze(self, elapsed, price, open_price, trend_4h, poly_price_up, poly_price_down):
        if self.triggered_signal: return self.triggered_signal
        
        # Basic Data Setup
        leader_side = "UP" if price > open_price else "DOWN"
        leader_price = poly_price_up if leader_side == "UP" else poly_price_down
        drift = abs(price - open_price) / open_price if open_price > 0 else 0
        
        # Record Checkpoint (Simulation of time-based scanning)
        if 300 <= elapsed <= 780:
             if elapsed not in self.checkpoints:
                 self.checkpoints[elapsed] = leader_price
                 self.scan_count += 1
        
        # --- SIGNAL 1: Strong Uptrend (T+5 to T+9) ---
        # "Start to Mid Game"
        if elapsed <= 540 and elapsed >= 300:
            times = sorted(self.checkpoints.keys())
            # Look back 90s
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
                
                # Logic from sim_live_trend_linear_v4_2.py
                if max_consec < (self.MAX_CONSECUTIVE_RISES + 1):
                    # Condition: mom >= 0.25 (25 cents?), max_consec >= 3, Drift > Threshold
                    # Note: mom in Poly cents (0.00-1.00). 0.25 is HUGE move in 90s.
                    if (mom >= 0.25 and max_consec >= 3 and drift > self.DRIFT_THRESHOLD 
                        and leader_price < 0.85 and leader_price > 0.10):
                        
                        # Wall Score Check (Placeholder 1.0 assumed pass > 0.4)
                        wall_score = 1.0 
                        if wall_score >= 0.4:
                             self.triggered_signal = f"MOSHE_STRONG_TREND_{leader_side}|MidGame Surge (Mom={mom:.2f}, Consec={max_consec})"
                             return self.triggered_signal

        # --- SIGNAL 2: Late Game Sniper (T+11 to T+13) ---
        elif 660 <= elapsed <= 780:
            # Logic:
            # 1. Price High Confidence (0.80 - 0.92)
            # 2. Drift Significant (> 0.30%)
            # 3. Macro 4H Matches
            
            if (0.80 <= leader_price <= 0.92) and (drift > 0.003):
                 if (leader_side == "UP" and trend_4h == "UP") or \
                    (leader_side == "DOWN" and trend_4h == "DOWN"):
                        self.triggered_signal = f"MOSHE_SNIPER_{leader_side}|Late Game 0.3% Drift + 4H Trend Match"
                        return self.triggered_signal
                        
        return "WAIT"

class ZScoreBreakoutScanner:
    def __init__(self):
        self.triggered_signal = None
        self.max_compression = 0.0005 # Max 0.05% deviation allowed in first 13 mins
        self.z_threshold = 3.0 # Move must be 3x standard deviation
        
    def reset(self):
        self.triggered_signal = None
        
    def analyze(self, price_history, open_price, elapsed):
        if self.triggered_signal: return self.triggered_signal
        
        # 1. TIME CHECK: Active in final 4 minutes (Last 240s)
        # T+660 to T+900
        if elapsed < 660: return "WAIT_TIME"
        if not price_history: return "WAIT"
        
        # 2. COMPRESSION CHECK (The "Coil")
        # Analyze data from T=0 to T=660 (First 11 mins) to establish the "Sleep" baseline
        early_data = [p['price'] for p in price_history if p['elapsed'] <= 660]
        if not early_data: return "WAIT_DATA"
        
        # Calculate Deviation of early period
        avg_price = sum(early_data) / len(early_data)
        # Standard Deviation of the "Sleep" period
        variance = sum((p - avg_price) ** 2 for p in early_data) / len(early_data)
        std_dev = variance ** 0.5
        
        # Max/Min during sleep
        high_11m = max(early_data)
        low_11m = min(early_data)
        range_pct = (high_11m - low_11m) / open_price
        
        # If range was too wide (>0.1%), market wasn't sleeping. No coil.
        if range_pct > 0.001: return "WAIT_NO_COIL"
        
        # Avoid division by zero if flatline
        if std_dev == 0: std_dev = 0.01 
        
        # 3. SET THRESHOLD BASED ON TIME REMAINING
        # Tier 1 (Early Warning): 4m left to 2m left -> Requires STRONG Move (3.5 Sigma)
        # Tier 2 (Final Spring): < 2m left -> Requires STANDARD Move (3.0 Sigma)
        
        effective_threshold = self.z_threshold # Default 3.0
        tier_name = "Final Spring"
        
        if elapsed < 780: # Between 11m and 13m
             effective_threshold = 3.5
             tier_name = "Early Breakout"
        
        # 4. THE SPRING CHECK (Current Pricing)
        current_price = price_history[-1]['price']
        
        # Calculate Z-Score of current price relative to the "Sleep" distribution
        z_score = (current_price - avg_price) / std_dev
        
        # 5. TRIGGER LOGIC
        if abs(z_score) > effective_threshold:
            direction = "UP" if z_score > 0 else "DOWN"
            
            # Double check: Must break the 11m Range High/Low
            if direction == "UP" and current_price <= high_11m: return "WAIT_INSIDE"
            if direction == "DOWN" and current_price >= low_11m: return "WAIT_INSIDE"
            
            # Triple check: Velocity (Must be recent)
            # Ensure this high price didn't drift up slowly.
            # Look at price 30s ago.
            recent_30s = next((x for x in reversed(price_history) if x['elapsed'] <= (elapsed - 30)), None)
            if recent_30s:
                move_30s = abs(current_price - recent_30s['price'])
                # If 30s move is small (< 1 Sigma), it's a drift, not a pop.
                if move_30s < std_dev: return "WAIT_DRIFT"
            
            self.triggered_signal = f"BET_{direction}_ZSCORE|{tier_name} (Z={z_score:.1f} > {effective_threshold})"
            return self.triggered_signal
            
        return "WAIT"

# --- HELPER FUNCTIONS ---

def calculate_ma(prices, period):
    if len(prices) < period: return 0
    return sum(prices[-period:]) / period

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return 50
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    seed = deltas[:period]
    up = sum(d for d in seed if d > 0) / period
    down = sum(-d for d in seed if d < 0) / period
    if down == 0: return 100
    rs = up / down
    rsi = 100 - (100 / (1 + rs))
    for i in range(period, len(deltas)):
        delta = deltas[i]
        gain = delta if delta > 0 else 0
        loss = -delta if delta < 0 else 0
        up = (up * (period - 1) + gain) / period
        down = (down * (period - 1) + loss) / period
    if down == 0: return 100
    rs = up / down
    return 100 - (100 / (1 + rs))

def calculate_bb(prices, period=20):
    if len(prices) < period: return 0, 0, 0
    slice_ = prices[-period:]
    sma = sum(slice_) / period
    variance = sum((x - sma) ** 2 for x in slice_) / period
    std_dev = variance ** 0.5
    return sma + (std_dev * 2), sma, sma - (std_dev * 2)

# --- MAIN LOGGING CLASS ---

class AlgoLogger:
    def __init__(self):
        self.scanners = {
            "NPattern": NPatternScanner(),
            "Fakeout": FakeoutScanner(),
            "TailWag": TailWagScanner(),
            "RSI": RsiScanner(),
            "TrapCandle": TrapCandleScanner(),
            "MidGame": MidGameScanner(),
            "LateReversal": LateReversalScanner(),
            "BullFlag": StaircaseBreakoutScanner(),
            "PostPump": PostPumpScanner(),
            "StepClimber": StepClimberScanner(),
            "Slingshot": SlingshotScanner(),
            "MinOne": MinOneScanner(),
            "Liquidity": LiquidityVacuumScanner(),
            "Cobra": CobraScanner(),
            "Mesa": MesaCollapseScanner(),
            "MeanReversion": MeanReversionScanner(),
            "GrindSnap": GrindSnapScanner(),
            "VolCheck": VolCheckScanner(),
            "Moshe": MosheSpecializedScanner(),
            "ZScore": ZScoreBreakoutScanner()
        }
        
        self.price_history = []
        self.active_signals = [] # List of {timestamp, algo, signal, entry_price, direction}
        self.pending_signals = [] # List of {algo, signal, direction, target_price, expires_at}
        self.all_results = [] # Track all results across entire run
        self.current_window_start = 0
        self.last_window_color = None
        self.last_window_data = None
        self.poly_ids = (None, None, 0) # (UP_ID, DOWN_ID, WINDOW_START)
        
        # New Context for Moshe Scanner
        self.trend_4h = "NEUTRAL"
        self.last_4h_update = 0

        # Init CSVs
        self.init_logs()
        
    def init_logs(self):
        # Create logs directory if it doesn't exist
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        script_name = "algo_logger_v2"
        
        self.txt_log_path = os.path.join(log_dir, f"{script_name}_{ts}_log.txt")
        self.csv_ticks_path = os.path.join(log_dir, f"{script_name}_{ts}_ticks.csv") # Granular Market Data
        self.csv_signals_path = os.path.join(log_dir, f"{script_name}_{ts}_signals.csv") # Signal Events
        self.csv_results_path = os.path.join(log_dir, f"{script_name}_{ts}_results.csv") # Window Results
        
        # Init TXT (Human Readable - Narrative Only)
        with open(self.txt_log_path, 'w') as f:
            f.write(f"ALGO LOGGER SESSION START: {ts}\n")
            f.write(f"Script: {script_name}.py\n")
            f.write(f"Version: V2 (Macro-Aware + Queue System)\n")
            f.write("="*60 + "\n\n")
            
        # Init Ticks CSV (Backtesting Source of Truth)
        with open(self.csv_ticks_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "WindowStart", "Elapsed", "BTC_Price", "Open_Price", "Diff", "Poly_Up", "Poly_Down", "Signal_Count"])

        # Init Signals CSV (Analytics)
        with open(self.csv_signals_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "WindowStart", "Algo", "EventType", "Direction", "Price", "Drift", "SignalText"])

        # Init Results CSV
        with open(self.csv_results_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["WindowStart", "Algo", "Signal", "Direction", "EntryPrice", "ClosePrice", "Result", "PnL"])
            
        print(f"Logging to:\n - {self.txt_log_path}\n - {self.csv_ticks_path}\n - {self.csv_signals_path}\n - {self.csv_results_path}")

    def log(self, msg):
        print(msg)
        try:
            with open(self.txt_log_path, 'a') as f:
                f.write(str(msg) + "\n")
        except: pass

    def log_signal(self, algo_name, signal_text, price, elapsed, is_pending=False):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        open_price = 0
        if self.price_history and self.current_window_start > 0:
            # Try to find the open price for this window from history
            win_data = [p for p in self.price_history if p['elapsed'] <= 5]
            if win_data: open_price = win_data[0]['price']
            
        drift = ((price - open_price) / open_price * 100) if open_price > 0 else 0
        event_type = "PENDING" if is_pending else "CONFIRMED"
        
        # Determine Direction
        direction = "UP" if "UP" in signal_text else "DOWN"
        if any(x in signal_text for x in ["BET_DOWN", "WHALE_LEADER_DOWN", "REVERSAL_DOWN", "SHORT"]):
            direction = "DOWN"
        elif any(x in signal_text for x in ["BET_UP", "WHALE_LEADER_UP", "REVERSAL_UP", "SNIPER_ENTRY_UP"]):
            direction = "UP"
            
        if not is_pending:
            # Make signal VERY visible in console and Text Log
            print(f"\n\n{'='*70}")
            print(f"🚨 SIGNAL TRIGGERED: {algo_name} → {direction}")
            print(f"{'='*70}")
            print(f"Time: {timestamp} (T+{elapsed}s)")
            print(f"Price: ${price:,.2f} (Drift: {drift:+.3f}%)")
            print(f"Logic: {signal_text}")
            print(f"{'='*70}\n")
            
            self.log(f"[{timestamp}] SIGNAL CONFIRMED: {algo_name} -> {direction} @ ${price:,.2f} (T+{elapsed}s, Drift: {drift:+.3f}%)")
        else:
            # For pending signals, just a small console note, no text log spam
            print(f"\n⏳ SIGNAL QUEUED: {algo_name} wants {direction} (Price ${price:,.2f}, Drift {drift:+.3f}%)")

        # Log to Signals CSV (Analytics)
        try:
            with open(self.csv_signals_path, 'a', newline='') as f:
                writer = csv.writer(f)
                # ["Timestamp", "WindowStart", "Algo", "EventType", "Direction", "Price", "Drift", "SignalText"]
                writer.writerow([timestamp, self.current_window_start, algo_name, event_type, direction, price, f"{drift:.4f}%", signal_text])
        except: pass
            
        if not is_pending:
            # Track for settlement result
            self.active_signals.append({
                "window_start": self.current_window_start,
                "algo": algo_name,
                "signal": signal_text,
                "direction": direction,
                "entry_price": price
            })

    def print_status(self, msg, log_to_file=False):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {msg}")

    def settlement_summary(self, close_price, open_price):
        win_side = "UP" if close_price >= open_price else "DOWN"
        
        # Calculate Window Stats for PostPump Scanner
        try:
            prices = [p['price'] for p in self.price_history]
            if not prices: prices = [open_price, close_price]
            high_p = max(prices)
            low_p = min(prices)
            self.last_window_data = {
                'open': open_price,
                'close': close_price,
                'high': high_p,
                'low': low_p,
                'height': high_p - low_p,
                'change_pct': abs((close_price - open_price) / open_price) if open_price > 0 else 0
            }
        except:
            self.last_window_data = None

        self.log(f"\n{'='*60}")
        self.log(f"WINDOW CLOSED: {self.current_window_start}")
        self.log(f"Open: ${open_price:.2f} | Close: ${close_price:.2f} | Winner: {win_side}")
        self.log(f"{'-'*60}")
        
        if not self.active_signals:
            self.log("No Signals Triggered this window.")
        else:
            self.log(f"{'ALGO':<20} | {'DIR':<5} | {'STATUS':<10}")
            self.log("-" * 50)
            
            wins = 0
            for sig in self.active_signals:
                if sig["window_start"] != self.current_window_start: continue
                
                result = "DISPROVEN"
                if sig["direction"] == "UP" and close_price > open_price: result = "PROVEN ✅"
                elif sig["direction"] == "DOWN" and close_price < open_price: result = "PROVEN ✅"
                elif close_price == open_price: result = "DRAW ➖"
                
                if "PROVEN" in result: wins += 1
                
                self.log(f"{sig['algo']:<20} | {sig['direction']:<5} | {result:<10}")

                # Track for final summary
                self.all_results.append({
                    'algo': sig['algo'],
                    'result': result
                })

                # Log to CSV
                with open(self.csv_results_path, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        sig["window_start"], sig["algo"], sig["signal"], 
                        sig["direction"], sig["entry_price"], close_price, result
                    ])
            
            win_rate = (wins / len(self.active_signals)) * 100
            self.log(f"{'-'*50}")
            self.log(f"Performance: {wins}/{len(self.active_signals)} ({win_rate:.1f}%) Correct")
        
        print(f"{'='*60}\n")
        self.active_signals = [] # Reset

    def print_final_summary(self):
        """Print final statistics for all algorithms across entire run"""
        if not self.all_results:
            self.log("\n" + "="*60)
            self.log("FINAL SUMMARY: No signals triggered during this run.")
            self.log("="*60)
            return
        
        # Calculate per-algorithm statistics
        # Merge active signals (unsettled) into results for the final summary display
        display_results = list(self.all_results)
        
        # Add a note if we are including pending signals
        if self.active_signals:
            self.log(f"\n[Note] Including {len(self.active_signals)} pending signals from the current window.")
            for sig in self.active_signals:
                display_results.append({
                    'algo': sig['algo'],
                    'result': 'PENDING'
                })

        algo_stats = {}
        for result in display_results:
            algo = result['algo']
            if algo not in algo_stats:
                algo_stats[algo] = {'wins': 0, 'losses': 0, 'pending': 0, 'signals': 0}
            
            algo_stats[algo]['signals'] += 1
            res_text = result['result']
            if "PROVEN" in res_text:
                algo_stats[algo]['wins'] += 1
            elif "DISPROVEN" in res_text:
                algo_stats[algo]['losses'] += 1
            elif res_text == 'PENDING':
                algo_stats[algo]['pending'] += 1
        
        # Print summary
        self.log("\n" + "="*60)
        self.log("FINAL RUN SUMMARY")
        self.log("="*60)
        self.log(f"{'ALGORITHM':<20} | {'SIGNALS':<8} | {'W/L/P':<12} | {'WIN%'}")
        self.log("-"*60)
        
        # Sort by win rate (best to worst)
        sorted_algos = sorted(algo_stats.items(), 
                             key=lambda x: ((x[1]['wins'] / (x[1]['signals'] - x[1]['pending'])) if (x[1]['signals'] - x[1]['pending']) > 0 else 0, x[1]['signals']), 
                             reverse=True)
        
        total_signals = 0
        total_wins = 0
        
        for algo, stats in sorted_algos:
            valid_signals = stats['signals'] - stats['pending']
            win_rate = (stats['wins'] / valid_signals * 100) if valid_signals > 0 else 0
            res_str = f"{stats['wins']}/{stats['losses']}/{stats['pending']}"
            self.log(f"{algo:<20} | {stats['signals']:<8} | {res_str:<12} | {win_rate:>5.1f}%")
            total_signals += stats['signals']
            total_wins += stats['wins']
        
        total_wins = sum(s['wins'] for s in algo_stats.values())
        total_losses = sum(s['losses'] for s in algo_stats.values())
        total_pending = sum(s['pending'] for s in algo_stats.values())
        total_valid = total_wins + total_losses
        
        overall_win_rate = (total_wins / total_valid * 100) if total_valid > 0 else 0
        self.log("-"*60)
        
        total_res = f"{total_wins}/{total_losses}/{total_pending}"
        self.log(f"{'OVERALL':<20} | {total_signals:<8} | {total_res:<12} | {overall_win_rate:>5.1f}%")
        self.log("="*60 + "\n")

    def signal_handler(self, sig, frame):
        """Handle graceful shutdown on Ctrl+C"""
        print("\n\n" + "="*70)
        print("SHUTTING DOWN GRACEFULLY (Ctrl+C detected)")
        print("="*70 + "\n")
        self.print_final_summary()
        print("\nGoodbye!\n")
        # Force hard exit to prevent lingering threads/loops
        os._exit(0)

    def fetch_polymarket_ids(self):
        try:
            slug = f"btc-updown-15m-{self.current_window_start}"
            url = f"{GAMMA_API_URL}/markets/slug/{slug}"
            print(f"\n[Poly] Fetching IDs for slug: {slug}...") 
            
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=5) as r:
                data = json.loads(r.read())
                
                ids = data.get('clobTokenIds', [])
                if isinstance(ids, str): ids = json.loads(ids)
                
                outcomes = data.get('outcomes', [])
                if isinstance(outcomes, str): outcomes = json.loads(outcomes)
                
                if not ids or len(ids) < 2: 
                    print(f"[Poly] Error: No IDs found in response for {slug}")
                    return None, None
                
                up_id = ids[0]
                down_id = ids[1]
                
                # Robust mapping
                for i, name in enumerate(outcomes):
                     if 'Up' in name or 'Yes' in name: up_id = ids[i]
                     elif 'Down' in name or 'No' in name: down_id = ids[i]
                
                print(f"[Poly] IDs Found! UP={up_id[:10]}... DOWN={down_id[:10]}...")
                return up_id, down_id
        except Exception as e:
            print(f"[Poly] Exception fetching {slug}: {e}")
            return None, None

    def fetch_polymarket_prices(self):
        # Cache IDs for the window
        if not hasattr(self, 'poly_ids') or self.poly_ids[2] != self.current_window_start:
             up_id, down_id = self.fetch_polymarket_ids()
             self.poly_ids = (up_id, down_id, self.current_window_start)
        
        up_id, down_id, _ = self.poly_ids
        if not up_id: return 0.50, 0.50
        
        try:
            u_p = 0.50; d_p = 0.50
            
            # Add User-Agent to avoid 403
            req_up = Request(f"{POLY_API_URL}/price?token_id={up_id}&side=buy", headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req_up, timeout=2) as r:
                raw = r.read()
                u_p = float(json.loads(raw).get('price', 0.50))
            
            req_down = Request(f"{POLY_API_URL}/price?token_id={down_id}&side=buy", headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req_down, timeout=2) as r:
                raw = r.read()
                d_p = float(json.loads(raw).get('price', 0.50))
                
            return u_p, d_p
        except Exception as e:
            # print(f"[Poly] Price Fetch Error: {e}") 
            # Suppress print if it's just noisy, but keep it for now as user asked to check myself.
            # If 403 is fixed, this shouldn't trigger.
            return 0.50, 0.50

    def fetch_polymarket_volume(self, token_id):
        """Fetch Polymarket order book volume for TailWag scanner."""
        if not token_id:
            return 0
        try:
            url = f"https://clob.polymarket.com/book?token_id={token_id}"
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req, timeout=3) as r:
                book = json.loads(r.read())
                # Sum bid sizes (first 10 levels) as volume approximation
                bids = book.get('bids', [])
                volume = sum(float(bid['size']) for bid in bids[:10] if 'size' in bid)
                return volume
        except:
            return 0

    def fetch_4h_trend(self):
        """Fetch 4H Trend Context for Moshe Scanner"""
        if (time.time() - self.last_4h_update) < 300: return # Cache 5 mins
        
        try:
            # Binance 4H Candles (Limit 10)
            url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=4h&limit=10"
            with urlopen(Request(url), timeout=3) as r:
                data = json.loads(r.read())
                if data:
                    closes = [float(x[4]) for x in data]
                    sma_short = sum(closes[-3:]) / 3
                    sma_long = sum(closes) / len(closes)
                    
                    if sma_short > sma_long * 1.002: self.trend_4h = "UP"
                    elif sma_short < sma_long * 0.998: self.trend_4h = "DOWN"
                    else: self.trend_4h = "NEUTRAL"
                    
                    print(f"[Context] Updated 4H Trend: {self.trend_4h} (Short:{sma_short:.0f} Long:{sma_long:.0f})")
                    self.last_4h_update = time.time()
        except Exception as e:
            # print(f"Context Update Error: {e}")
            pass

    def print_status_line(self, price, elapsed, up_p, down_p, open_price):
        remaining = 900 - elapsed
        mins = remaining // 60
        secs = remaining % 60
        signal_count = len(self.active_signals)
        
        # Color formatting
        leader = "UP" if up_p >= down_p else "DOWN"
        l_price = up_p if leader == "UP" else down_p
        
        diff = price - open_price
        sign = "+" if diff >= 0 else ""
        
        # Determine second-by-second trend for visual feedback
        prev_price = self.price_history[-1]['price'] if self.price_history else price
        trend_arrow = " "
        if price > prev_price: trend_arrow = "↑"
        elif price < prev_price: trend_arrow = "↓"
        
        # Using \r to overwrite line on console. 
        line = f"[T-{mins}:{secs:02d}] BTC:{price:,.2f} {trend_arrow} (Op:{open_price:,.2f} D:{sign}{diff:.2f}) | {leader}:${l_price:.2f} (U:{up_p:.2f} D:{down_p:.2f}) | Sigs:{signal_count}"
        print(f"\r{line}   ", end="", flush=True)
        
        # Log Granular Data to Ticks CSV (Backtesting Source of Truth)
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.csv_ticks_path, 'a', newline='') as f:
                writer = csv.writer(f)
                # ["Timestamp", "WindowStart", "Elapsed", "BTC_Price", "Open_Price", "Diff", "Poly_Up", "Poly_Down", "Signal_Count"]
                writer.writerow([timestamp, self.current_window_start, elapsed, price, open_price, diff, up_p, down_p, signal_count])
        except: pass

    def fetch_btc(self):
        """Fetch BTC price with fallback providers."""
        # Try Binance first (fastest)
        try:
            with urlopen(Request("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"), timeout=2) as r:
                return float(json.loads(r.read())['price'])
        except:
            pass
        
        # Fallback to CoinGecko
        try:
            with urlopen(Request("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"), timeout=3) as r:
                return float(json.loads(r.read())['bitcoin']['usd'])
        except:
            pass
        
        # Fallback to Kraken
        try:
            with urlopen(Request("https://api.kraken.com/0/public/Ticker?pair=XBTUSD"), timeout=3) as r:
                data = json.loads(r.read())
                return float(data['result']['XXBTZUSD']['c'][0])  # Last trade price
        except:
            return 0

    def fetch_candles_60m(self):
        """Fetch 60x 1m candles with fallback providers."""
        # Try Binance first
        try:
            url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=60"
            with urlopen(Request(url), timeout=2) as r:
                data = json.loads(r.read())
                return [float(x[4]) for x in data], [float(x[3]) for x in data]
        except:
            pass
        
        # Fallback to Kraken (60x 1m candles)
        try:
            url = "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=1"
            with urlopen(Request(url), timeout=3) as r:
                data = json.loads(r.read())
                if data.get('result') and data['result'].get('XXBTZUSD'):
                    candles = data['result']['XXBTZUSD'][-60:]  # Last 60 candles
                    closes = [float(x[4]) for x in candles]
                    lows = [float(x[3]) for x in candles]
                    return closes, lows
        except:
            pass
        
        return [], []

    def fetch_depth(self):
        """Fetch order book depth with fallback."""
        # Try Binance
        try:
            url = "https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=20"
            with urlopen(Request(url), timeout=2) as r:
                return json.loads(r.read())
        except:
            pass
        
        # Fallback to Kraken
        try:
            url = "https://api.kraken.com/0/public/Depth?pair=XBTUSD&count=20"
            with urlopen(Request(url), timeout=3) as r:
                data = json.loads(r.read())
                if data.get('result') and data['result'].get('XXBTZUSD'):
                    result = data['result']['XXBTZUSD']
                    return {
                        'bids': [[p, v] for p, v, _ in result.get('bids', [])],
                        'asks': [[p, v] for p, v, _ in result.get('asks', [])]
                    }
        except:
            pass
        
        return {}

    def fetch_window_history(self, start_ts, end_ts):
        try:
            # Fetch 1s candles for the window so far
            limit = end_ts - start_ts
            if limit <= 0: return []
            limit = min(limit, 1000) # Cap at Binance limit
            
            url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1s&startTime={start_ts*1000}&limit={limit}"
            with urlopen(Request(url), timeout=5) as r:
                data = json.loads(r.read())
                # Format: [timestamp, open, high, low, close, volume, ...]
                # We need dicts: {'timestamp': ts, 'elapsed': e, 'price': close}
                history = []
                for x in data:
                    ts_sec = int(x[0]/1000)
                    history.append({
                        'timestamp': ts_sec,
                        'elapsed': ts_sec - start_ts,
                        'price': float(x[4])
                    })
                return history
        except: return []

    def _fetch_prev_window_binance(self):
        """Fetch previous 15m candle from Binance."""
        url = f"{BINANCE_API_URL}/klines?symbol=BTCUSDT&interval=15m&limit=2"
        try:
            with urlopen(Request(url), timeout=5) as response:
                data = json.loads(response.read().decode())
                if len(data) >= 2:
                    prev = data[-2]
                    return (float(prev[1]), float(prev[4]), float(prev[2]), float(prev[3]))
        except:
            pass
        return None
    
    def _fetch_prev_window_coingecko(self):
        """Fetch previous 15m candle from CoinGecko."""
        # CoinGecko OHLC endpoint (15m granularity approximation)
        url = "https://api.coingecko.com/api/v3/coins/bitcoin/ohlc?vs_currency=usd&days=1"
        try:
            with urlopen(Request(url), timeout=5) as response:
                data = json.loads(response.read().decode())
                if data and len(data) >= 2:
                    # CoinGecko returns [timestamp, open, high, low, close]
                    prev = data[-2]
                    return (float(prev[1]), float(prev[4]), float(prev[2]), float(prev[3]))
        except:
            pass
        return None
    
    def _fetch_prev_window_kraken(self):
        """Fetch previous 15m candle from Kraken."""
        url = "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=15"
        try:
            with urlopen(Request(url), timeout=5) as response:
                data = json.loads(response.read().decode())
                if data.get('result') and data['result'].get('XXBTZUSD'):
                    candles = data['result']['XXBTZUSD']
                    if len(candles) >= 2:
                        # Kraken: [time, open, high, low, close, vwap, volume, count]
                        prev = candles[-2]
                        return (float(prev[1]), float(prev[4]), float(prev[2]), float(prev[3]))
        except:
            pass
        return None

    def run(self):
        # Register Signal Handler
        signal.signal(signal.SIGINT, self.signal_handler)
        
        self.log(f"\n{'='*60}")
        self.log(f"ALGO LOGGER v1.0 - MARKET ANALYSIS TOOL")
        self.log(f"{'='*60}")
        self.log(f"Active Scanners: {len(self.scanners)}")
        self.log("-" * 60)
        for name in self.scanners:
            self.log(f" • {name}")
        self.log(f"{'='*60}\n")
        
        # Initialize to 0.0 to prevent bad reads
        up_p = 0.0; down_p = 0.0
        closes_60m = []
        lows_60m = []
        depth_raw = {}
        poly_volume = 0  # For TailWag scanner
        
        # Initial Window Setup
        now = datetime.now()
        min15 = (now.minute // 15) * 15
        self.current_window_start = int(now.replace(minute=min15, second=0, microsecond=0).timestamp())
        
        start_elapsed = int(time.time() - self.current_window_start)
        if start_elapsed > 5:
            self.log(f"Starting mid-window (T+{start_elapsed}s). Backfilling history...")
            # We fetch history but DO NOT trigger signals on it
            self.price_history = self.fetch_window_history(self.current_window_start, int(time.time()))
            self.log(f"Backfilled {len(self.price_history)} data points.")
            open_price_now = self.price_history[0]['price'] if self.price_history else self.fetch_btc()
        else:
            open_price_now = self.fetch_btc()

        # Print initial window header
        window_end_ts = self.current_window_start + 900
        period_start = datetime.fromtimestamp(self.current_window_start).strftime('%H:%M')
        period_end = datetime.fromtimestamp(window_end_ts).strftime('%H:%M')
        
        self.log(f"\n" + "+" + "="*70 + "+")
        self.log(f"| NEW TRADING WINDOW: {period_start} → {period_end} ({self.current_window_start})")
        self.log(f"| Started at: {datetime.fromtimestamp(self.current_window_start).strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(f"| Open Price: ${open_price_now:,.2f}")
        self.log("+" + "="*70 + "+\n")
            
        # Initialize Last Window Color (Important for Fakeout Scanner)
        if self.last_window_color is None:
            # Try multiple providers in order: Binance -> CoinGecko -> Kraken
            providers = [
                ("Binance", lambda: self._fetch_prev_window_binance()),
                ("CoinGecko", lambda: self._fetch_prev_window_coingecko()),
                ("Kraken", lambda: self._fetch_prev_window_kraken())
            ]
            
            for provider_name, fetch_func in providers:
                try:
                    result = fetch_func()
                    if result:
                        pc_open, pc_close, pc_high, pc_low = result
                        self.last_window_color = "GREEN" if pc_close >= pc_open else "RED"
                        self.last_window_data = {
                            'open': pc_open,
                            'close': pc_close,
                            'high': pc_high,
                            'low': pc_low,
                            'height': pc_high - pc_low,
                            'change_pct': abs((pc_close - pc_open) / pc_open)
                        }
                        self.log(f"Initialized Previous Window via {provider_name}: {self.last_window_color} (O:{pc_open:.2f} C:{pc_close:.2f})")
                        break
                except Exception as e:
                    self.log(f"Warning: {provider_name} failed ({e}), trying next provider...")
                    continue
            else:
                # All providers failed
                self.log("Warning: All providers failed. Defaulting to GREEN.")
                self.log("Fakeout/PostPump scanners will wait for next window.")
                self.last_window_color = "GREEN"
                self.last_window_data = None
        
        while True:
            try:
                now = datetime.now()
                min15 = (now.minute // 15) * 15
                window_start = int(now.replace(minute=min15, second=0, microsecond=0).timestamp())
                
                if window_start != self.current_window_start:
                    # New Window Logic
                    if self.current_window_start > 0:
                        if self.price_history:
                            close_price = self.price_history[-1]['price']
                            open_price = self.price_history[0]['price']
                            self.settlement_summary(close_price, open_price)
                            self.last_window_color = "GREEN" if close_price >= open_price else "RED"
                    
                    self.current_window_start = window_start
                    self.price_history = []
                    for s in self.scanners.values(): s.reset()
                    
                    # Fetch initial price for the header
                    open_price_now = self.fetch_btc()
                    window_end_ts = window_start + 900
                    period_start = datetime.fromtimestamp(window_start).strftime('%H:%M')
                    period_end = datetime.fromtimestamp(window_end_ts).strftime('%H:%M')
                    
                    self.log(f"\n" + "+" + "="*70 + "+")
                    self.log(f"| NEW TRADING WINDOW: {period_start} → {period_end} ({window_start})")
                    self.log(f"| Started at: {now.strftime('%Y-%m-%d %H:%M:%S')}")
                    self.log(f"| Open Price: ${open_price_now:,.2f}")
                    self.log("+" + "="*70 + "+\n")
                
                # Fetch Data
                price = self.fetch_btc()
                if price == 0: 
                    time.sleep(1)
                    continue
                
                # Update Context
                self.fetch_4h_trend()

                # Fetch Poly prices (every 2s to avoid rate limit)
                elapsed = int(time.time() - window_start)
                if elapsed % 2 == 0:
                    up_p, down_p = self.fetch_polymarket_prices()

                self.price_history.append({
                    'timestamp': time.time(),
                    'elapsed': elapsed,
                    'price': price
                })
                
                # UPDATE: Prevent firing in the last 10 seconds (Wait Mode)
                # Relaxed from 840 to 890 to allow late Z-Score plays
                if elapsed > 890: 
                    if elapsed % 10 == 0:
                        self.print_status_line(price, elapsed, up_p, down_p, open_price)
                    time.sleep(1)
                    continue

                # Context Data (Only fetch every 5s to save API)
                if elapsed % 5 == 0:
                     closes_60m, lows_60m = self.fetch_candles_60m()
                     depth_raw = self.fetch_depth()
                     
                     # Fetch Polymarket volume for TailWag
                     if self.poly_ids and self.poly_ids[0]:  # If we have UP token ID
                         poly_volume = self.fetch_polymarket_volume(self.poly_ids[0])
                
                if not self.price_history: continue
                open_price = self.price_history[0]['price']

                # --- Calculate Derived Data ---
                rsi = calculate_rsi(closes_60m)
                upper_bb, mid_bb, lower_bb = calculate_bb(closes_60m)
                
                # Fast BB (last 20s of 1s-history) for MeanReversion
                fast_bb = (0, 0, 0)
                if len(self.price_history) >= 20:
                    fast_prices = [p['price'] for p in self.price_history[-20:]]
                    fast_bb = calculate_bb(fast_prices, period=20)

                swing_low = 0
                if lows_60m: swing_low = min(lows_60m)
                
                spot_depth = 0
                if depth_raw:
                    bids = depth_raw.get('bids', [])
                    asks = depth_raw.get('asks', [])
                    # Sum within 0.1% for "depth" metric
                    lower_bound = price * 0.999
                    upper_bound = price * 1.001
                    spot_depth += sum(float(p)*float(q) for p,q in bids if float(p) >= lower_bound)
                    spot_depth += sum(float(p)*float(q) for p,q in asks if float(p) <= upper_bound)
                
                # 0. CHECK PENDING SIGNALS
                # Use a copy to iterate safely while modifying
                for p_sig in self.pending_signals[:]:
                    # Check if expired (5 mins)
                    if (time.time() - p_sig['timestamp']) > 300:
                        self.pending_signals.remove(p_sig)
                        continue
                        
                    # Check if crossed
                    crossed = False
                    if p_sig['direction'] == "UP" and price > open_price: crossed = True
                    elif p_sig['direction'] == "DOWN" and price < open_price: crossed = True
                    
                    if crossed:
                        # Log the RELEASE/CONFIRMATION
                        self.log_signal(p_sig['algo'], p_sig['signal'], price, elapsed, is_pending=False)
                        self.pending_signals.remove(p_sig)

                # RUN SCANNERS
                for name, scanner in self.scanners.items():
                    res = "WAIT"
                    
                    # Routing
                    if name == "NPattern": res = scanner.analyze(self.price_history, open_price)
                    elif name == "Fakeout": res = scanner.analyze(self.price_history, open_price, self.last_window_color)
                    elif name == "TailWag": res = scanner.analyze(900-elapsed, poly_volume, spot_depth, "UP" if up_p >= down_p else "DOWN", price, self.price_history)
                    elif name == "RSI": res = scanner.analyze(rsi, price, lower_bb, 900-elapsed)
                    elif name == "TrapCandle": res = scanner.analyze(self.price_history, open_price)
                    elif name == "MidGame": res = scanner.analyze(self.price_history, open_price, elapsed)
                    elif name == "LateReversal": res = scanner.analyze(self.price_history, open_price, elapsed)
                    elif name == "BullFlag": res = scanner.analyze(closes_60m)
                    elif name == "StepClimber": res = scanner.analyze(closes_60m)
                    elif name == "Slingshot": res = scanner.analyze(closes_60m)
                    elif name == "MinOne": res = scanner.analyze(self.price_history, elapsed)
                    elif name == "Liquidity": res = scanner.analyze(price, swing_low, open_price)
                    elif name == "Cobra": res = scanner.analyze(closes_60m, price, elapsed)
                    elif name == "Mesa": res = scanner.analyze(self.price_history, open_price, elapsed)
                    elif name == "PostPump": res = scanner.analyze(price, open_price, self.last_window_data)
                    elif name == "MeanReversion": res = scanner.analyze(self.price_history, fast_bb)
                    elif name == "GrindSnap": res = scanner.analyze(self.price_history, elapsed)
                    elif name == "VolCheck": res = scanner.analyze(closes_60m, price, open_price, elapsed, up_p, down_p)
                    elif name == "Moshe": res = scanner.analyze(elapsed, price, open_price, self.trend_4h, up_p, down_p)
                    elif name == "ZScore": res = scanner.analyze(self.price_history, open_price, elapsed)
                    
                    if res and ("BET_" in res or "CONFIRMED" in res or "SNIPER" in res or "WHALE" in res or "SHORT" in res or "VOL_" in res):
                         if scanner.triggered_signal == res: 
                             # Check if already logged (active)
                             already_logged = any(s['algo'] == name and s['window_start'] == window_start for s in self.active_signals)
                             # Check if already pending
                             already_pending = any(s['algo'] == name for s in self.pending_signals)
                             
                             if not already_logged and not already_pending:
                                 # Determine Direction
                                 direction = "UP" if "UP" in res else "DOWN"
                                 if "BET_DOWN" in res or "WHALE_LEADER_DOWN" in res or "REVERSAL_DOWN" in res or "SHORT" in res:
                                     direction = "DOWN"
                                 elif "BET_UP" in res or "WHALE_LEADER_UP" in res or "REVERSAL_UP" in res or "SNIPER_ENTRY_UP" in res:
                                     direction = "UP"
                                     
                                 # CHECK TERRITORY
                                 is_winning = False
                                 if direction == "UP" and price > open_price: is_winning = True
                                 elif direction == "DOWN" and price < open_price: is_winning = True
                                 
                                 if is_winning:
                                     self.log_signal(name, res, price, elapsed)
                                 else:
                                     # Queue it and log it as PENDING
                                     self.log_signal(name, res, price, elapsed, is_pending=True)
                                     self.pending_signals.append({
                                         "algo": name,
                                         "signal": res,
                                         "direction": direction,
                                         "target": open_price,
                                         "timestamp": time.time()
                                     })
                
                self.print_status_line(price, elapsed, up_p, down_p, open_price)
                time.sleep(1)
                
            except KeyboardInterrupt:
                self.signal_handler(None, None)
            except Exception as e:
                self.log(f"\nLoop Error: {e}")
                time.sleep(1)

if __name__ == "__main__":
    import traceback
    try:
        logger = AlgoLogger()
        logger.run()
    except Exception as e:
        print(f"\n\n{'='*70}")
        print(f"FATAL ERROR - SCRIPT CRASHED")
        print(f"{'='*70}")
        print(f"Error: {e}")
        print(f"\nFull Traceback:")
        print(traceback.format_exc())
        print(f"{'='*70}\n")
        import sys
        sys.exit(1)
