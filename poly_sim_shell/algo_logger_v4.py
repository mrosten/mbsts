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

# --- PORTFOLIO & SCALING LOGIC ---

class AlgorithmPortfolio:
    def __init__(self, algo_name, initial_balance):
        self.algo_name = algo_name
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.total_wins = 0
        self.total_losses = 0
        self.total_draws = 0
        self.is_active = True
        self.consecutive_losses = 0
        # Tracks active trades for CURRENT window settlement
        self.active_trades = [] # List of {side, entry, cost, shares, timestamp}

    def calculate_bet_size(self, context, strategy_type):
        """
        Scaling logic inspired by sim_live_trend_linear_v4_2.py
        """
        if not self.is_active: return 0
        
        # Base percentage of current balance
        budget_pct = 0.12 # Default 12%
        
        # Boost for strong patterns
        strong_patterns = ["UPTREND", "STRONG_TREND", "COBRA", "LIQ_SWEEP", "LATE_REVERSAL"]
        if any(p in strategy_type for p in strong_patterns):
            budget_pct = 0.20
            
        cost = self.balance * budget_pct
        
        # 1. Macro 4H Adjustment
        trend_4h = context.get('trend_4h', 'NEUTRAL')
        direction = context.get('direction', 'UP')
        if trend_4h != 'NEUTRAL' and trend_4h != direction:
            cost *= 0.5 # Penalty for trading against 4H macro
            
        # 2. Consecutive Loss Penalty (Streak Filter)
        if self.consecutive_losses >= 2:
            cost *= 0.7
            
        # 3. Minimum & Maximum Safety Caps
        MIN_BET = 5.50
        MAX_BET = 100.0 # Session cap to prevent runaway bets
        
        if cost < MIN_BET:
            # If we have enough for Min, use Min. Otherwise 0 (Algorithm Dies).
            cost = MIN_BET if self.balance >= MIN_BET else 0
        
        if cost > MAX_BET:
            cost = MAX_BET
            
        return round(cost, 2)

    def record_trade(self, side, entry_price, cost, shares, contract_price=0.50):
        self.balance -= cost
        self.active_trades.append({
            "side": side,
            "entry_price": entry_price,
            "cost": cost,
            "shares": shares,
            "contract_price": contract_price,
            "timestamp": time.time()
        })

    
    def settle_window(self, win_side, close_price, open_price):
        total_payout = 0
        total_profit = 0
        
        if self.active_trades:
            for trade in self.active_trades:
                payout = 0
                if win_side != "DRAW" and trade['side'] == win_side:
                    # Logic: $1.00 payout per share on win
                    payout = trade['shares']
                    self.total_wins += 1
                    self.consecutive_losses = 0
                elif win_side == "DRAW":
                    # Refund cost on draw (0.50 scenario)
                    payout = trade['cost']
                    self.total_draws += 1
                else:
                    # Loss
                    payout = 0
                    self.total_losses += 1
                    self.consecutive_losses += 1
                
                total_payout += payout
                total_profit += (payout - trade['cost'])
                
            self.balance += total_payout
            self.active_trades = [] # Reset for next window
        
        # Minimum survival check
        if self.balance < 5.50:
            self.is_active = False
            
        return total_payout, total_profit

# --- SCANNERS ---

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
        phase1_prices = [p['price'] for p in history_objs if p['elapsed'] <= 180]
        if not phase1_prices: return "WAIT"
            
        first_peak = max(phase1_prices)
        impulse_height = first_peak - open_price
        if impulse_height < (open_price * self.min_impulse_size): return "WAIT" 
            
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
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, history_objs, open_price, prev_window_color):
        if self.triggered_signal: return self.triggered_signal
        if not history_objs or not prev_window_color: return "NO_SIGNAL"
        early_prices = [p['price'] for p in history_objs if p['elapsed'] <= 180]
        if not early_prices: return "NO_SIGNAL"
        spike_high = max(early_prices)
        current_price = history_objs[-1]['price']
        if (spike_high > open_price) and (current_price < open_price):
            if prev_window_color == "RED": self.triggered_signal = f"BET_DOWN_AGGRESSIVE|Rejected Rescue & Trend Align"
            elif prev_window_color == "GREEN": self.triggered_signal = f"WAIT_FOR_CONFIRMATION|Rejected Rescue vs Trend"
            return self.triggered_signal
        return "NO_SIGNAL"

class TailWagScanner:
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, time_remaining, poly_volume, spot_depth, leader_direction, spot_price, price_history):
        if self.triggered_signal: return self.triggered_signal
        if time_remaining >= 180: return "WAIT_TIME"
        if not poly_volume or not spot_depth or spot_depth == 0: return "NO_DATA"
        if float(poly_volume) > (float(spot_depth) * 1.5):
            recent_prices = [p['price'] for p in price_history if p['elapsed'] >= (900-time_remaining-30)]
            if not recent_prices: return "WAIT_DATA"
            move_pct = (recent_prices[-1] - recent_prices[0]) / recent_prices[0]
            confirmed = (leader_direction == "UP" and move_pct > 0.0005) or (leader_direction == "DOWN" and move_pct < -0.0005)
            if confirmed:
                self.triggered_signal = f"WHALE_LEADER_{leader_direction}|Whale vol > 1.5x Cost + Spot Reacted"
                return self.triggered_signal
        return "NO_SIGNAL"

class RsiScanner:
    def __init__(self): self.triggered_signal = None
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
                if (start_move / open_price > 0.003) and (current_move < start_move * 0.25):
                    self.triggered_signal = "BET_DOWN_FADE_BREAKOUT|Flash Crash >75% retraced"
                    return self.triggered_signal
        except: pass
        return "WAIT"

class MidGameScanner:
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, price_history, open_price, elapsed, trend_4h):
        if self.triggered_signal: return self.triggered_signal
        
        # Trend Gate: Don't short if Trend is UP
        if trend_4h == "UP": return "WAIT_TREND_MISMATCH"

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
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, close_prices):
        if self.triggered_signal: return self.triggered_signal
        if len(close_prices) < 20: return "WAIT_DATA"
        window = close_prices[-15:]
        lows = [window[i] for i in range(1, len(window) - 1) if window[i] <= window[i-1] and window[i] <= window[i+1]]
        if len(lows) < 3: return "WAIT_PATTERN"
        if all(lows[i] < lows[i+1] for i in range(len(lows)-1)):
            recent_high = max(window)
            if (recent_high - min(window)) > (min(window) * 0.002):
                if window[-1] >= (recent_high * 0.9995):
                     self.triggered_signal = "BET_UP_AGGRESSIVE|Staircase Breakout Confirmed"
                     return self.triggered_signal
        return "WAIT"

class PostPumpScanner:
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, current_price, current_open, last_window):
        if self.triggered_signal: return self.triggered_signal
        if not last_window or last_window.get('change_pct', 0) < 0.005: return "WAIT"
        midpoint = last_window['open'] + (last_window['height'] * 0.5)
        if last_window['close'] > last_window['open'] and current_price < midpoint and current_price < current_open:
            self.triggered_signal = "BET_DOWN|Post-Pump Fade Below Midpoint"
            return self.triggered_signal
        elif last_window['close'] < last_window['open'] and current_price > midpoint and current_price > current_open:
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
        if abs(close_prices[-1] - ma20) < (close_prices[-1] * 0.0015) and close_prices[-1] > ma20:
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
        
        # EXISTING: Bullish Reclaim (Cross UP)
        if close_prices[-1] > ma and (close_prices[-2] < ma or close_prices[-3] < ma):
             self.triggered_signal = "MAX_BET_UP_RECLAIM|Reclaimed MA20"
             return self.triggered_signal
             
        # NEW: Bearish Breakdown (Cross DOWN)
        if close_prices[-1] < ma and (close_prices[-2] > ma or close_prices[-3] > ma):
             self.triggered_signal = "MAX_BET_DOWN_BREAKDOWN|Lost MA20 Support"
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
        h = max(x['price'] for x in min1); l = min(x['price'] for x in min1)
        c = min1[-1]['price']; o = min1[0]['price']; body = abs(c - o)
        
        # INCREASED THRESHOLD: 1.5 -> 2.0
        if (h - max(o, c)) > body * 2.0: self.triggered_signal = "BET_DOWN_WICK|Liar's Wick Detected"; return self.triggered_signal
        if (min(o, c) - l) > body * 2.0: self.triggered_signal = "BET_UP_WICK|Liar's Wick Detected"; return self.triggered_signal
        return "WAIT"

class LiquidityVacuumScanner:
    def __init__(self):
        self.triggered_signal = None
        self.swept = False
        self.sweep_high = 0
    def reset(self): self.triggered_signal = None; self.swept = False; self.sweep_high = 0
    def analyze(self, current_price, swing_low, open_price):
        if self.triggered_signal: return self.triggered_signal
        if swing_low == 0: return "WAIT"
        if current_price < swing_low:
            self.swept = True
            if current_price > self.sweep_high: self.sweep_high = current_price
            return "SWEEP_DETECTED"
        if self.swept and current_price > swing_low * 1.0002:
            self.triggered_signal = f"BET_UP_LIQ_SWEEP|Swept {swing_low:.2f} then broke structure"
            return self.triggered_signal
        return "WAIT"

class CobraScanner:
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, closes_60m, current_price, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if elapsed > 180 or len(closes_60m) < 20: return "WAIT"
        slice_ = closes_60m[-20:]; sma = sum(slice_) / 20
        std = (sum((x - sma) ** 2 for x in slice_) / 20) ** 0.5
        if current_price > (sma + 2*std): self.triggered_signal = "BET_UP_COBRA|Explosive breakout"; return self.triggered_signal
        if current_price < (sma - 2*std): self.triggered_signal = "BET_DOWN_COBRA|Explosive breakdown"; return self.triggered_signal
        return "WAIT"

class MesaCollapseScanner:
    def __init__(self):
        self.triggered_signal = None
        self.state = "SEARCHING"
        self.mesa_floor = None
        self.pump_start_time = None
    def reset(self): self.triggered_signal = None; self.state = "SEARCHING"; self.mesa_floor = None; self.pump_start_time = None
    def analyze(self, price_history, open_price, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if elapsed < 180: return "WAIT_TIME"
        current_price = price_history[-1]['price']
        if self.state == "SEARCHING":
            if elapsed <= 180 and (current_price - open_price) / open_price > 0.0015:
                self.state = "WATCHING_TOP"; self.pump_start_time = elapsed; return "PUMP_DETECTED"
        elif self.state == "WATCHING_TOP":
            if elapsed < (self.pump_start_time + 120): return "WAIT_DEVELOP"
            mesa_window = [p['price'] for p in price_history if (elapsed - 180) <= p['elapsed'] <= elapsed]
            if len(mesa_window) < 10: return "WAIT_DATA"
            ma = sum(mesa_window) / len(mesa_window); crosses = sum(1 for i in range(1, len(mesa_window)) if (mesa_window[i-1] > ma) != (mesa_window[i] > ma))
            self.mesa_floor = min(mesa_window)
            if crosses >= 3: self.state = "HUNTING_BREAK"; return "MESA_ARMED"
            if current_price > ma * 1.001: self.reset(); return "ABORT_BULL_FLAG"
        elif self.state == "HUNTING_BREAK":
            last_5 = [p['price'] for p in price_history[-5:]]
            if last_5 and max(last_5) < self.mesa_floor:
                self.triggered_signal = "BET_DOWN_HEAVY|Mesa Collapse Confirmed"; self.state = "EXECUTED"; return self.triggered_signal
        return "WAIT"

class MeanReversionScanner:
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, price_history, fast_bb, trend_4h):
        if self.triggered_signal: return self.triggered_signal
        
        # Trend Gate: Don't short if Trend is UP
        if trend_4h == "UP": return "WAIT_TREND_MISMATCH"

        if not fast_bb or len(price_history) < 20: return "WAIT"
        upper_band = fast_bb[0]; current_price = price_history[-1]['price']
        if any(p['price'] > upper_band for p in price_history[-20:]) and current_price < upper_band:
            peak_price = max(p['price'] for p in price_history[-20:])
            if (peak_price - current_price) / peak_price > 0.0005:
                self.triggered_signal = f"SHORT_THE_SNAP|Rejection from Top"; return self.triggered_signal
        return "WAIT"

class GrindSnapScanner:
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, price_history, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if elapsed < 390: return "WAIT_TIME"
        p_now = price_history[-1]['price']
        p_snap_end = next((x['price'] for x in reversed(price_history) if x['elapsed'] <= (elapsed - 30)), None)
        p_snap_start = next((x['price'] for x in reversed(price_history) if x['elapsed'] <= (elapsed - 90)), None)
        p_grind_start = next((x['price'] for x in reversed(price_history) if x['elapsed'] <= (elapsed - 390)), None)
        if not p_snap_end or not p_snap_start or not p_grind_start: return "WAIT"
        grind_move = p_snap_start - p_grind_start
        if abs(grind_move / p_grind_start) < 0.001: return "WAIT_FLAT"
        snap_move = p_snap_end - p_snap_start
        recent_30s = [p['price'] for p in price_history if p['elapsed'] > (elapsed - 30)]
        if grind_move > 0 and any(p > p_snap_start for p in recent_30s): return "WAIT_FAILED_HOLD"
        elif grind_move < 0 and any(p < p_snap_start for p in recent_30s): return "WAIT_FAILED_HOLD"
        if abs(snap_move / grind_move) > 0.60:
             self.triggered_signal = f"BET_{'DOWN' if grind_move > 0 else 'UP'}_SNAP|Grind Snapped"; return self.triggered_signal
        return "WAIT"

class VolCheckScanner:
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, closes_60m, current_price, open_price, elapsed, up_p, down_p):
        if self.triggered_signal: return self.triggered_signal
        if (900-elapsed) > 300 or (900-elapsed) < 30: return "WAIT_TIME"
        target_side = "UP" if 0.85 <= up_p <= 0.90 else ("DOWN" if 0.85 <= down_p <= 0.90 else None)
        if not target_side: return "WAIT_PRICE"
        if len(closes_60m) < 45: return "WAIT_DATA"
        ranges = []
        for i in range(0, 42, 3): chunk = closes_60m[-45+i:-45+i+3]; ranges.append(max(chunk)-min(chunk))
        avg_3m = sum(ranges)/len(ranges)
        dist = abs(current_price - open_price)
        if dist > avg_3m and ((target_side == "UP" and current_price > open_price) or (target_side == "DOWN" and current_price < open_price)):
             self.triggered_signal = f"VOL_SAFE_{target_side}|Gap > Avg3m Range"; return self.triggered_signal
        return "WAIT"

class MosheSpecializedScanner:
    def __init__(self): self.triggered_signal = None; self.checkpoints = {}
    def reset(self): self.triggered_signal = None; self.checkpoints = {}
    def analyze(self, elapsed, price, open_price, trend_4h, up_p, down_p):
        if self.triggered_signal: return self.triggered_signal
        leader_p = up_p if price > open_price else down_p
        drift = abs(price - open_price) / open_price if open_price > 0 else 0
        if 300 <= elapsed <= 780 and elapsed not in self.checkpoints: self.checkpoints[elapsed] = leader_p
        if 300 <= elapsed <= 540:
            times = sorted(self.checkpoints.keys()); recent = [self.checkpoints[t] for t in times if elapsed - t <= 90]
            if len(recent) >= 3:
                consec = 0; max_consec = 0
                for i in range(1, len(recent)):
                    if recent[i] > recent[i-1]: consec += 1
                    else: consec = 0
                    max_consec = max(max_consec, consec)
                if max_consec >= 3 and (recent[-1] - recent[0]) >= 0.25 and drift > 0.0004 and 0.10 < leader_p < 0.85:
                    self.triggered_signal = f"MOSHE_STRONG_TREND_{'UP' if price > open_price else 'DOWN'}|Surge Detected"; return self.triggered_signal
        elif 660 <= elapsed <= 780:
            if 0.80 <= leader_p <= 0.92 and drift > 0.003:
                if (price > open_price and trend_4h == "UP") or (price < open_price and trend_4h == "DOWN"):
                    self.triggered_signal = f"MOSHE_SNIPER_{'UP' if price > open_price else 'DOWN'}|Trend Match"; return self.triggered_signal
        return "WAIT"

class ZScoreBreakoutScanner:
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, price_history, open_price, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if elapsed < 660: return "WAIT_TIME"
        early_data = [p['price'] for p in price_history if p['elapsed'] <= 660]
        if not early_data: return "WAIT"
        avg = sum(early_data)/len(early_data); std = (sum((p-avg)**2 for p in early_data)/len(early_data))**0.5 or 0.01
        if (max(early_data)-min(early_data))/open_price > 0.001: return "WAIT_NO_COIL"
        z = (price_history[-1]['price'] - avg) / std
        thresh = 3.5 if elapsed < 780 else 3.0
        if abs(z) > thresh:
            if (z > 0 and price_history[-1]['price'] > max(early_data)) or (z < 0 and price_history[-1]['price'] < min(early_data)):
                self.triggered_signal = f"BET_{'UP' if z > 0 else 'DOWN'}_ZSCORE|Breakout Z={z:.1f}"; return self.triggered_signal
        return "WAIT"

# --- HELPER FUNCTIONS ---

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return 50
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    up = sum(d for d in deltas[:period] if d > 0) / period
    down = sum(-d for d in deltas[:period] if d < 0) / period
    if down == 0: return 100
    for i in range(period, len(deltas)):
        d = deltas[i]; g = d if d > 0 else 0; l = -d if d < 0 else 0
        up = (up * (period - 1) + g) / period; down = (down * (period - 1) + l) / period
    if down == 0: return 100
    return 100 - (100 / (1 + up/down))

def calculate_bb(prices, period=20):
    if len(prices) < period: return 0, 0, 0
    slice_ = prices[-period:]; sma = sum(slice_) / period
    std = (sum((x - sma) ** 2 for x in slice_) / period) ** 0.5
    return sma + (std*2), sma, sma - (std*2)

# --- TEST DATA GENERATOR ---

class TestDataGenerator:
    def __init__(self):
        self.current_price = 50000.0
        self.start_price = 50000.0
        self.trend = random.choice(["UP", "DOWN", "CHOP"])
        self.volatility = 0.001
        self.elapsed = 0
        
    def reset(self):
        self.current_price = 50000.0
        self.start_price = 50000.0
        self.trend = random.choice(["UP", "DOWN", "CHOP"])
        self.elapsed = 0
        
    def next_tick(self):
        self.elapsed += 1
        change = random.gauss(0, self.volatility)
        if self.trend == "UP": change += 0.0001
        elif self.trend == "DOWN": change -= 0.0001
        
        self.current_price *= (1 + change)
        return self.current_price, self.elapsed

# --- MAIN LOGGING CLASS ---

class AlgoLogger:
    def __init__(self, initial_balance=None):
        self.test_mode = False
        self.verbose = False
        self.test_gen = TestDataGenerator()

        # 1. Interactive Startup
        if initial_balance is None:
            print("\n" + "="*60)
            print("ALGO LOGGER V4 - INTELLIGENT TRADING SYSTEM")
            print("="*60)
            
            # Balance
            while True:
                try:
                    raw_bal = input("Enter starting USD balance (e.g. 100): ")
                    self.initial_balance = float(raw_bal)
                    if self.initial_balance < 5.50:
                        print("Error: Balance must be >= $5.50.")
                        continue
                    break
                except ValueError: print("Invalid input.")

            # Test Mode
            tm = input("Run in TEST MODE with random data? (y/N): ").lower()
            if tm == 'y': self.test_mode = True
            
            # Verbose
            vb = input("Enable VERBOSE logging? (y/N): ").lower()
            if vb == 'y': self.verbose = True
            
        else:
            self.initial_balance = initial_balance

        self.scanners = {
            "NPattern": NPatternScanner(), "Fakeout": FakeoutScanner(), "TailWag": TailWagScanner(),
            "RSI": RsiScanner(), "TrapCandle": TrapCandleScanner(), "MidGame": MidGameScanner(),
            "LateReversal": LateReversalScanner(), "BullFlag": StaircaseBreakoutScanner(),
            "PostPump": PostPumpScanner(), "StepClimber": StepClimberScanner(), "Slingshot": SlingshotScanner(),
            "MinOne": MinOneScanner(), "Liquidity": LiquidityVacuumScanner(), "Cobra": CobraScanner(),
            "Mesa": MesaCollapseScanner(), "MeanReversion": MeanReversionScanner(), "GrindSnap": GrindSnapScanner(),
            "VolCheck": VolCheckScanner(), "Moshe": MosheSpecializedScanner(), "ZScore": ZScoreBreakoutScanner()
        }
        
        # Initialize Portfolios
        self.portfolios = {name: AlgorithmPortfolio(name, self.initial_balance) for name in self.scanners}
        
        self.price_history = []
        self.active_signals = [] 
        self.pending_signals = [] # List of {algo, signal, direction, timestamp}
        self.live_scanning_active = False # Gate for backfill vs live
        self.all_results = [] 
        self.current_window_start = 0
        self.last_window_color = None
        self.last_window_data = None
        self.poly_ids = (None, None, 0)
        self.trend_4h = "NEUTRAL"
        self.last_4h_update = 0

        self.init_logs()
        
    def init_logs(self):
        log_dir = "logs"
        if not os.path.exists(log_dir): os.makedirs(log_dir)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        script_name = "algo_logger_v3"
        
        self.txt_log_path = os.path.join(log_dir, f"{script_name}_{ts}_log.txt")
        self.csv_ticks_path = os.path.join(log_dir, f"{script_name}_{ts}_ticks.csv")
        self.csv_signals_path = os.path.join(log_dir, f"{script_name}_{ts}_signals.csv")
        self.csv_results_path = os.path.join(log_dir, f"{script_name}_{ts}_results.csv")
        
        with open(self.txt_log_path, 'w') as f:
            f.write(f"ALGO LOGGER SESSION START: {ts}\n")
            f.write(f"Balance per Algo: ${self.initial_balance:.2f}\n")
            f.write(f"Version: V4 (Fixes + Test Mode)\n")
            f.write(f"Test Mode: {self.test_mode}\n")
            f.write("="*60 + "\n\n")
            
        with open(self.csv_ticks_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "WindowStart", "Elapsed", "BTC_Price", "Open_Price", "Poly_Up", "Poly_Down", "Portfolio_Total"])

        with open(self.csv_signals_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "WindowStart", "Algo", "EventType", "Direction", "Price", "BetSize", "RemainingBal", "SignalText"])

        with open(self.csv_results_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["WindowStart", "Algo", "Direct", "Entry", "Close", "Status", "Cost", "Payout", "Profit", "FinalBal"])
            
        print(f"Logging to: {log_dir}/{script_name}_{ts}_*")

    def log(self, msg):
        print(msg)
        try:
            with open(self.txt_log_path, 'a') as f: f.write(str(msg) + "\n")
        except: pass

    def log_signal(self, algo_name, signal_text, price, elapsed, is_pending=False, poly_price=0.50):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        open_price = self.price_history[0]['price'] if self.price_history else price
        drift = ((price - open_price) / open_price * 100) if open_price > 0 else 0
        event_type = "PENDING" if is_pending else "CONFIRMED"
        
        # Determine Direction
        direction = "UP" if "UP" in signal_text else "DOWN"
        if any(x in signal_text for x in ["BET_DOWN", "WHALE_LEADER_DOWN", "REVERSAL_DOWN", "SHORT", "FADE"]):
            direction = "DOWN"
        elif any(x in signal_text for x in ["BET_UP", "WHALE_LEADER_UP", "REVERSAL_UP", "SNIPER_ENTRY_UP", "WINNING"]):
            direction = "UP"
            
        portfolio = self.portfolios.get(algo_name)
        bet_size = 0
        
        if not is_pending and portfolio and portfolio.is_active:
            # Calculate Bet Size
            context = {
                'trend_4h': self.trend_4h,
                'direction': direction,
                'is_winning': (direction == "UP" and price > open_price) or (direction == "DOWN" and price < open_price)
            }
            bet_size = portfolio.calculate_bet_size(context, signal_text)
            
            if bet_size > 0:
                shares = bet_size / poly_price if poly_price > 0 else bet_size / 0.50
                portfolio.record_trade(direction, price, bet_size, shares, poly_price)
                
                # Make signal VERY visible in console and Text Log
                print(f"\n\n{'='*70}")
                print(f"🚨 SIGNAL TRIGGERED: {algo_name} → {direction}")
                print(f"💰 BET PLACED: ${bet_size:.2f} @ {poly_price:.2f} (Shares: {shares:,.2f})")
                print(f"{'='*70}")
                print(f"Time: {timestamp} (T+{elapsed}s)")
                print(f"Price: ${price:,.2f} (Drift: {drift:+.3f}%)")
                print(f"Logic: {signal_text}")
                print(f"Equity: ${portfolio.balance:.2f} remaining")
                print(f"{'='*70}\n")
                
                self.log(f"[{timestamp}] SIGNAL: {algo_name} -> {direction} | Bet: ${bet_size:.2f} @ ${poly_price:.2f} | Bal: ${portfolio.balance:.2f} (T+{elapsed}s)")
            else:
                self.log(f"[{timestamp}] SKIP: {algo_name} insufficient balance or scaling logic returned 0.")
        elif is_pending:
            # For pending signals, just a small console note
            print(f"\n⏳ SIGNAL QUEUED: {algo_name} wants {direction} (Price ${price:,.2f}, Drift {drift:+.3f}%)")

        # Log to Signals CSV (Analytics)
        try:
            with open(self.csv_signals_path, 'a', newline='') as f:
                writer = csv.writer(f)
                # ["Timestamp", "WindowStart", "Algo", "EventType", "Direction", "Price", "BetSize", "RemainingBal", "SignalText"]
                writer.writerow([timestamp, self.current_window_start, algo_name, event_type, direction, price, bet_size, portfolio.balance if portfolio else 0, signal_text])
        except: pass
            
        if not is_pending:
            # Track for settlement result
            self.active_signals.append({
                "window_start": self.current_window_start,
                "algo": algo_name,
                "signal": signal_text,
                "direction": direction,
                "entry_price": price,
                "poly_price": poly_price,
                "bet_size": bet_size
            })

    def settlement_summary(self, close_price, open_price):
        win_side = "UP" if close_price > open_price else ("DOWN" if close_price < open_price else "DRAW")
        
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

        self.log(f"\n{'='*80}")
        self.log(f"WINDOW CLOSED: {self.current_window_start} | Winner: {win_side}")
        self.log(f"BTC Op: ${open_price:.2f} | Cl: ${close_price:.2f}")
        self.log(f"{'-'*80}")
        
        if not self.active_signals:
            self.log("No trades executed this window.")
        else:
            self.log(f"{'ALGO':<15} | {'DIR':<4} | {'STATUS':<10} | {'COST':<8} | {'PNL':<8} | {'BALANCE'}")
            self.log("-" * 80)
            
            for sig in self.active_signals:
                if sig["window_start"] != self.current_window_start: continue
                
                p = self.portfolios.get(sig['algo'])
                payout, profit = (0, 0)
                if p:
                    payout, profit = p.settle_window(win_side, close_price, open_price)
                
                status = "DISPROVEN"
                if win_side != "DRAW" and sig['direction'] == win_side: status = "PROVEN ✅"
                elif win_side == "DRAW": status = "DRAW ➖"
                
                # Show Price Paid (Contract Cost) in settlement log if available
                contract_cost = f"${sig['poly_price']:.2f}"
                self.log(f"{sig['algo']:<15} | {sig['direction']:<4} | {status:<10} | ${sig['bet_size']:<7.2f} (@{contract_cost}) | ${profit:<7.2f} | ${p.balance if p else 0:.2f}")

                # Log to CSV (Results)
                # ["WindowStart", "Algo", "Direct", "Entry", "Close", "Status", "Cost", "Payout", "Profit", "FinalBal"]
                try:
                    with open(self.csv_results_path, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            sig["window_start"], sig["algo"], sig["direction"], 
                            sig["entry_price"], close_price, status, sig["bet_size"], payout, profit, p.balance if p else 0
                        ])
                except: pass
            
        print(f"{'='*80}\n")
        self.active_signals = [] # Reset

    def print_final_summary(self):
        """Print final statistics for all algorithms across entire run"""
        self.log("\n" + "="*80)
        self.log("FINAL PERFORMANCE SUMMARY (USD)")
        self.log("="*80)
        self.log(f"{'ALGORITHM':<15} | {'W/L/D':<10} | {'INITIAL':<10} | {'FINAL':<10} | {'NET PNL'}")
        self.log("-" * 80)
        
        grand_total_initial = 0
        grand_total_final = 0
        
        # Sort by Balance descending
        sorted_portfolios = sorted(self.portfolios.values(), key=lambda x: x.balance, reverse=True)
        
        for p in sorted_portfolios:
            net_pnl = p.balance - p.initial_balance
            res_str = f"{p.total_wins}/{p.total_losses}/{p.total_draws}"
            status_tag = "" if p.is_active else " [DEAD]"
            self.log(f"{p.algo_name + status_tag:<15} | {res_str:<10} | ${p.initial_balance:<9.2f} | ${p.balance:<9.2f} | ${net_pnl:+.2f}")
            
            grand_total_initial += p.initial_balance
            grand_total_final += p.balance
            
        self.log("-" * 80)
        total_pnl = grand_total_final - grand_total_initial
        self.log(f"{'TOTAL PORTFOLIO':<15} | {'':<10} | ${grand_total_initial:<9.2f} | ${grand_total_final:<9.9f} | ${total_pnl:+.2f}")
        self.log("="*80 + "\n")

    def signal_handler(self, sig, frame):
        """Handle graceful shutdown on Ctrl+C"""
        print("\n\n" + "="*70)
        print("SHUTTING DOWN GRACEFULLY (Ctrl+C detected)")
        print("="*70 + "\n")
        self.print_final_summary()
        print("\nGoodbye!\n")
        os._exit(0)

    def fetch_polymarket_prices(self):
        if not hasattr(self, 'poly_ids') or self.poly_ids[2] != self.current_window_start:
             slug = f"btc-updown-15m-{self.current_window_start}"
             try:
                 with urlopen(Request(f"{GAMMA_API_URL}/markets/slug/{slug}", headers={'User-Agent': 'Mozilla/5.0'}), timeout=5) as r:
                     data = json.loads(r.read())
                     ids = data.get('clobTokenIds', [])
                     if isinstance(ids, str): ids = json.loads(ids)
                     outcomes = data.get('outcomes', [])
                     if isinstance(outcomes, str): outcomes = json.loads(outcomes)
                     
                     up_id = ids[0]; down_id = ids[1]
                     for i, name in enumerate(outcomes):
                         if 'Up' in name or 'Yes' in name: up_id = ids[i]
                         elif 'Down' in name or 'No' in name: down_id = ids[i]
                     self.poly_ids = (up_id, down_id, self.current_window_start)
             except:
                 self.poly_ids = (None, None, self.current_window_start)
        
        up_id, down_id, _ = self.poly_ids
        if not up_id: return 0.50, 0.50
        try:
            u_p = 0.50; d_p = 0.50
            with urlopen(Request(f"{POLY_API_URL}/price?token_id={up_id}&side=buy", headers={'User-Agent': 'Mozilla/5.0'}), timeout=2) as r:
                u_p = float(json.loads(r.read()).get('price', 0.50))
            with urlopen(Request(f"{POLY_API_URL}/price?token_id={down_id}&side=buy", headers={'User-Agent': 'Mozilla/5.0'}), timeout=2) as r:
                d_p = float(json.loads(r.read()).get('price', 0.50))
            return u_p, d_p
        except:
            return 0.50, 0.50

    def print_status_line(self, price, elapsed, up_p, down_p, open_price):
        remaining = 900 - elapsed
        mins = remaining // 60; secs = remaining % 60
        leader = "UP" if up_p >= down_p else "DOWN"
        l_price = up_p if leader == "UP" else down_p
        diff = price - open_price
        sign = "+" if diff >= 0 else ""
        
        # Trend feedback
        prev_price = self.price_history[-1]['price'] if self.price_history else price
        arrow = "↑" if price > prev_price else ("↓" if price < prev_price else " ")
        
        # Portfolio aggregate
        total_bal = sum(p.balance for p in self.portfolios.values())
        
        line = f"[T-{mins}:{secs:02d}] BTC:{price:,.2f} {arrow} | {leader}:${l_price:.2f} (U:{up_p:.2f} D:{down_p:.2f}) | Eq:${total_bal:,.0f}"
        print(f"\r{line}   ", end="", flush=True)
        
        try:
            with open(self.csv_ticks_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), self.current_window_start, elapsed, price, open_price, up_p, down_p, total_bal])
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
            return self.price_history[-1]['price'] if self.price_history else 0

    def fetch_4h_trend(self):
        if (time.time() - self.last_4h_update) < 300: return
        try:
            url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=4h&limit=10"
            with urlopen(Request(url), timeout=3) as r:
                data = json.loads(r.read())
                closes = [float(x[4]) for x in data]
                short = sum(closes[-3:]) / 3
                long_ = sum(closes) / len(closes)
                self.trend_4h = "UP" if short > long_ * 1.002 else ("DOWN" if short < long_ * 0.998 else "NEUTRAL")
                self.last_4h_update = time.time()
        except: pass

    def run(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        
        self.log(f"\n{'='*60}")
        self.log(f"ALGO LOGGER v4.0 - RUNNING")
        if self.test_mode: self.log("!!! RUNNING IN TEST MODE (SYNTHETIC DATA) !!!")
        self.log(f"{'='*60}")
        self.log(f"Active Scanners: {len(self.scanners)}")
        self.log(f"Initial Balance: ${self.initial_balance:.2f} per algorithm")
        self.log("-" * 60)
        for name in self.scanners:
            self.log(f" • {name}")
        self.log(f"{'='*60}\n")
        
        # Initial Window Setup
        now = datetime.now()
        min15 = (now.minute // 15) * 15
        self.current_window_start = int(now.replace(minute=min15, second=0, microsecond=0).timestamp())
        
        start_elapsed = int(time.time() - self.current_window_start)
        if start_elapsed > 5:
            self.log(f"Starting mid-window (T+{start_elapsed}s). Backfilling history...")
            limit = min(start_elapsed, 1000)
            url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1s&startTime={self.current_window_start*1000}&limit={limit}"
            try:
                with urlopen(Request(url), timeout=5) as r:
                    data = json.loads(r.read())
                    self.price_history = [{'timestamp': int(x[0]/1000), 'elapsed': int(x[0]/1000) - self.current_window_start, 'price': float(x[4])} for x in data]
                    self.log(f"Backfilled {len(self.price_history)} data points.")
            except: pass
            open_price_now = self.price_history[0]['price'] if self.price_history else self.fetch_btc()
        else:
            open_price_now = self.fetch_btc()
        
        # Reset live flag on new window start or script start
        self.live_scanning_active = False

        # Header
        p_start = datetime.fromtimestamp(self.current_window_start).strftime('%H:%M')
        p_end = datetime.fromtimestamp(self.current_window_start + 900).strftime('%H:%M')
        self.log(f"\n" + "+" + "="*70 + "+")
        self.log(f"| NEW TRADING WINDOW: {p_start} → {p_end} ({self.current_window_start})")
        self.log(f"| Open Price: ${open_price_now:,.2f}")
        self.log(f"| Open Price: ${open_price_now:,.2f}")
        self.log("+" + "="*70 + "+\n")
            
        # Initial Fetch to avoid 0.50 start
        try:
            if not self.test_mode:
                up_p, down_p = self.fetch_polymarket_prices()
                spot_depth = self.fetch_depth()
            else:
                up_p, down_p = 0.50, 0.50
        except:
            up_p, down_p = 0.50, 0.50
            
        while True:
            try:
                now = datetime.now(); window_start = int(now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0).timestamp())
                
                if window_start != self.current_window_start:
                    if self.current_window_start > 0 and self.price_history:
                        self.settlement_summary(self.price_history[-1]['price'], self.price_history[0]['price'])
                    self.current_window_start = window_start; self.price_history = []
                    for s in self.scanners.values(): s.reset()
                    self.live_scanning_active = False # Reset for new window
                    open_price_now = self.fetch_btc()
                    self.log(f"\n" + "+" + "="*70 + "+")
                    self.log(f"| NEW TRADING WINDOW: {datetime.fromtimestamp(window_start).strftime('%H:%M')} start")
                    self.log(f"| Open Price: ${open_price_now:,.2f}")
                    self.log("+" + "="*70 + "+\n")

                if self.test_mode:
                    # Synthetic Data Loop
                    price, t_elapsed = self.test_gen.next_tick()
                    # Sync Trend from Generator
                    self.trend_4h = self.test_gen.trend
                    elapsed = t_elapsed
                    time.sleep(0.01) # Fast forward in test mode
                    if elapsed >= 900: self.test_gen.reset(); elapsed = 0
                else:
                    # Live Data Loop
                    price = self.fetch_btc(); elapsed = int(time.time() - window_start)
                    self.fetch_4h_trend()
                if elapsed % 2 == 0: 
                    up_p, down_p = self.fetch_polymarket_prices()
                    spot_depth = self.fetch_depth()
                if not self.price_history: self.price_history.append({'timestamp': time.time(), 'elapsed': elapsed, 'price': price})
                else: self.price_history.append({'timestamp': time.time(), 'elapsed': elapsed, 'price': price})
                
                self.print_status_line(price, elapsed, up_p, down_p, self.price_history[0]['price'])

                # Activate live scanning only after we digest the first live tick
                if not self.live_scanning_active:
                    self.live_scanning_active = True
                    self.log(f"Synced with Live Market. Scanning Active.")

                # Scanners logic (Full)
                if 0 <= elapsed <= 890 and self.live_scanning_active:
                    open_p = self.price_history[0]['price']
                    # Placeholder for missing scanner data
                    closes_60m, lows_60m = self.fetch_candles_60m()
                    rsi = calculate_rsi(closes_60m)
                    _, _, low_bb = calculate_bb(closes_60m)
                    fast_bb = calculate_bb([p['price'] for p in self.price_history[-20:]]) if len(self.price_history) >= 20 else (0,0,0)

                    # Check Pendings
                    for p_sig in self.pending_signals[:]:
                        crossed = (p_sig['direction']=="UP" and price > open_p) or (p_sig['direction']=="DOWN" and price < open_p)
                        if crossed:
                            self.log_signal(p_sig['algo'], p_sig['signal'], price, elapsed, False, up_p if p_sig['direction']=="UP" else down_p)
                            self.pending_signals.remove(p_sig)

                    for name, scanner in self.scanners.items():
                        if not self.portfolios[name].is_active: continue
                        res = "WAIT"
                        if name == "NPattern": res = scanner.analyze(self.price_history, open_p)
                        elif name == "Fakeout": res = scanner.analyze(self.price_history, open_p, self.last_window_color)
                        elif name == "TailWag":
                            # Calculate simple bid/ask size for Whale detection
                            bid_sum = sum(float(x[1]) for x in spot_depth.get('bids', []))
                            res = scanner.analyze(900-elapsed, 0, bid_sum, "UP" if up_p > down_p else "DOWN", price, self.price_history)
                        elif name == "RSI": res = scanner.analyze(rsi, price, low_bb, 900-elapsed)
                        elif name == "TrapCandle": res = scanner.analyze(self.price_history, open_p)
                        elif name == "MidGame": res = scanner.analyze(self.price_history, open_p, elapsed, self.trend_4h)
                        elif name == "LateReversal": res = scanner.analyze(self.price_history, open_p, elapsed)
                        elif name == "BullFlag": res = scanner.analyze(closes_60m)
                        elif name == "PostPump": res = scanner.analyze(price, open_p, self.last_window_data)
                        elif name == "StepClimber": res = scanner.analyze(closes_60m)
                        elif name == "Slingshot": res = scanner.analyze(closes_60m)
                        elif name == "MinOne": res = scanner.analyze(self.price_history, elapsed)
                        elif name == "Liquidity": res = scanner.analyze(price, min(lows_60m) if lows_60m else 0, open_p)
                        elif name == "Cobra": res = scanner.analyze(closes_60m, price, elapsed)
                        elif name == "Mesa": res = scanner.analyze(self.price_history, open_p, elapsed)
                        elif name == "MeanReversion": res = scanner.analyze(self.price_history, fast_bb, self.trend_4h)
                        elif name == "GrindSnap": res = scanner.analyze(self.price_history, elapsed)
                        elif name == "VolCheck": res = scanner.analyze(closes_60m, price, open_p, elapsed, up_p, down_p)
                        elif name == "Moshe": res = scanner.analyze(elapsed, price, open_p, self.trend_4h, up_p, down_p)
                        elif name == "ZScore": res = scanner.analyze(self.price_history, open_p, elapsed)

                        if res and "BET_" in str(res):
                            # (Simplified logic for brevity in this piece, full in final)
                            direction = "UP" if "UP" in str(res) else "DOWN"
                            is_safe = (direction == "UP" and price > open_p) or (direction == "DOWN" and price < open_p)
                            if not any(s['algo'] == name for s in self.active_signals if s['window_start'] == window_start):
                                if is_safe: self.log_signal(name, res, price, elapsed, False, up_p if direction=="UP" else down_p)
                                else: 
                                    if not any(s['algo'] == name for s in self.pending_signals):
                                        self.pending_signals.append({'algo': name, 'signal': res, 'direction': direction, 'timestamp': time.time()})
                                        self.log_signal(name, res, price, elapsed, True)

                time.sleep(1)
            except Exception as e: time.sleep(1)

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

if __name__ == "__main__":
    logger = AlgoLogger()
    logger.run()
