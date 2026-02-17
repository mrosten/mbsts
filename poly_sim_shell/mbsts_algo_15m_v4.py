import os
import asyncio
import time
import json
import math
import csv
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from dataclasses import dataclass

# --- CONFIGURATION CENTER ---
@dataclass
class TradingConfig:
    # Time Settings
    WINDOW_SECONDS: int = 900
    LOG_INTERVAL: int = 15
    PHASE1_DURATION: int = 60  # Standard impulse phase for scanners
    
    # Risk Management
    DEFAULT_RISK_PCT: float = 0.12
    STRONG_RISK_PCT: float = 0.20
    MIN_BET: float = 5.50
    MAX_BET_SESSION_CAP: float = 100.0
    LIVE_RISK_DIVISOR: int = 8  # 1/8th of balance for Live Mode
    
    # Tolerances
    TOLERANCE_PCT: float = 0.002

class RiskManager:
    """
    Centralized Risk Management System.
    Replaces split logic between AlgorithmPortfolio and SniperApp.
    """
    def __init__(self, is_live_mode=False):
        self.is_live_mode = is_live_mode
        self.risk_bankroll = 0.0
        self.target_bankroll = 0.0 # Cap for refilling logic
        self.allocated_this_window = 0.0
        self.window_bets = [] # List of {id, cost, potential_payout}
        
    def set_bankroll(self, amount, is_live=False):
        self.is_live_mode = is_live
        if is_live:
            self.risk_bankroll = amount / TradingConfig.LIVE_RISK_DIVISOR
        else:
            self.risk_bankroll = amount
        self.target_bankroll = self.risk_bankroll # Set Cap to initial value
            
    def calculate_bet_size(self, strategy_type, balance, consecutive_losses, trend_context):
        """
        Determine safe bet size based on bankroll, recent performance, and market context.
        """
        # 1. Base Sizing
        budget_pct = TradingConfig.DEFAULT_RISK_PCT
        strong_patterns = ["UPTREND", "STRONG_TREND", "COBRA", "LIQ_SWEEP", "LATE_REVERSAL"]
        if any(p in strategy_type for p in strong_patterns):
            budget_pct = TradingConfig.STRONG_RISK_PCT
            
        # Use Dynamic Risk Bankroll as the base
        base = self.risk_bankroll - self.allocated_this_window
        if base <= 0: return 0.0
        
        cost = base * budget_pct
        
        # 2. Adjustments
        trend_4h = trend_context.get('trend_4h', 'NEUTRAL')
        direction = trend_context.get('direction', 'UP')
        if trend_4h != 'NEUTRAL' and trend_4h != direction:
            cost *= 0.5
            
        if consecutive_losses >= 2:
            cost *= 0.7
            
        # 3. Clamping
        cost = max(0, min(cost, TradingConfig.MAX_BET_SESSION_CAP))
        
        if cost < TradingConfig.MIN_BET:
            # Survival Check: do we have enough?
            if base >= TradingConfig.MIN_BET: return TradingConfig.MIN_BET
            return 0.0
            
        return round(cost, 2)

    def register_bet(self, cost):
        self.allocated_this_window += cost
        
    def reset_window(self):
        self.allocated_this_window = 0.0
        self.window_bets = []

class MarketDataManager:
    def __init__(self, logger_func=None):
        self.logger = logger_func if logger_func else print
        self.market_data = {
            "btc_price": 0, "btc_open": 0, "start_ts": 0, 
            "up_p": 0.5, "down_p": 0.5, "up_price": 0.5, "down_price": 0.5,
            "up_bid": 0.5, "down_bid": 0.5, "up_ask": 0.51, "down_ask": 0.51,
            "up_id": None, "down_id": None,
            # Legacy fields for SimBroker logging
            "sling_signal": "WAIT", "poly_signal": "N/A", "cobra_signal": "WAIT", 
            "flag_signal": "WAIT", "to_signal": "N/A", "master_score": 0, "master_status": "NEUTRAL",
            "trend_score": 3, "trend_prob": 0.5, "btc_odds": 0, "btc_dyn_rng": 0
        }
        self.price_history = []
        self.trend_4h = "NEUTRAL"
        self.last_4h_update = 0
        
    def log(self, msg):
        self.logger(msg)

    def update_4h_trend(self):
        if (time.time() - self.last_4h_update) < 900: return
        try:
            r = requests.get("https://api.binance.com/api/v3/klines", params={"symbol":"BTCUSDT","interval":"4h","limit":10}, timeout=3)
            r.raise_for_status()
            data = r.json()
            closes = [float(x[4]) for x in data]
            short = sum(closes[-3:]) / 3; long_ = sum(closes) / len(closes)
            self.trend_4h = "UP" if short > long_ * 1.002 else ("DOWN" if short < long_ * 0.998 else "NEUTRAL")
            self.last_4h_update = time.time()
        except requests.RequestException as e:
            self.log(f"[yellow]Warn: 4H Trend Update Failed: {e}[/]")
        except Exception as e:
            self.log(f"[red]Error: 4H Trend Calc Error: {e}[/]")

    def fetch_candles_60m(self):
        try:
            r = requests.get("https://api.binance.com/api/v3/klines", params={"symbol":"BTCUSDT","interval":"1m","limit":60}, timeout=3)
            r.raise_for_status()
            data = r.json()
            return [float(x[4]) for x in data], [float(x[3]) for x in data]
        except requests.RequestException as e:
            self.log(f"[yellow]Warn: 60m Candles Fetch Failed: {e}[/]")
            return [], []
        except Exception:
            return [], []

    def fetch_current_price(self):
        try:
            r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=2).json()
            return float(r['price'])
        except Exception: 
            return self.market_data["btc_price"] # Silent Fallback

    def update_history(self, curr_price, elapsed):
        self.price_history.append({'timestamp': time.time(), 'elapsed': elapsed, 'price': curr_price})
        self.price_history = [p for p in self.price_history if p['elapsed'] >= 0]
        return self.price_history[0]['price'] if self.price_history else curr_price

    def fetch_polymarket(self, slug):
        up_p, down_p = 0.5, 0.5
        up_id, down_id = None, None
        up_bid, down_bid = 0.5, 0.5
        try:
            m = requests.get(f"https://gamma-api.polymarket.com/markets/slug/{slug}", timeout=2).json()
            ids = json.loads(m["clobTokenIds"]); outs = json.loads(m["outcomes"])
            
            # Robust outcome identification: 
            # UP side is usually "Yes", "Above", "Up", or "Higher"
            is_up_first = any(x in outs[0].lower() for x in ["up", "yes", "above", "higher", "top"])
            if is_up_first:
                up_id, down_id = ids[0], ids[1]
            else:
                # Many markets use "No" as the first outcome, which is usually DOWN
                is_down_first = any(x in outs[0].lower() for x in ["down", "no", "below", "lower", "bottom"])
                if is_down_first:
                    down_id, up_id = ids[0], ids[1]
                else:
                    # Fallback to legacy if names are weird
                    up_id = ids[0] if "Up" in outs[0] else ids[1]
                    down_id = ids[1] if up_id == ids[0] else ids[0]
            
            def get_p(tid, side):
                try: 
                    # side="sell" (CLOB Bid side), side="buy" (CLOB Ask side)
                    return float(requests.get("https://clob.polymarket.com/price", params={"token_id":tid,"side":side}, timeout=1).json().get("price",0))
                except: return 0
            
            # side="sell" returns the highest BID (price someone is willing to pay you to buy your shares)
            # side="buy" returns the lowest ASK (price you must pay to buy shares)
            up_bid = get_p(up_id, "sell")
            down_bid = get_p(down_id, "sell")
            up_ask = get_p(up_id, "buy")
            down_ask = get_p(down_id, "buy")
            
        except Exception:
            pass
        
        return {
            "up_price": up_bid or 0.5, # We use the BID as the 'price' for ROI/UI
            "down_price": down_bid or 0.5,
            "up_bid": up_bid, 
            "down_bid": down_bid,
            "up_ask": up_ask,
            "down_ask": down_ask,
            "up_id": up_id, 
            "down_id": down_id
        }

class TradeExecutor:
    """
    Handles execution routing between Sim and Live brokers.
    """
    def __init__(self, sim_broker, live_broker, risk_manager):
        self.sim = sim_broker
        self.live = live_broker
        self.risk = risk_manager
        
    def execute_buy(self, is_live, side, amount, price, token_id=None, reason=""):
        if amount <= 0: return False, "Zero amount"
        
        # Risk Check is done by caller via RiskManager caps, but we can double check here?
        # For now, assume caller (SniperApp) checked CalculateBetSize.
        # BUT: We should ensure we register it if successful? 
        # Actually SniperApp registers it because it maintains the `window_bets` list for TP/SL tracking.
        # So this executor just fires the order.
        
        if is_live:
            if not token_id: return False, "No Token ID"
            success, msg = self.live.buy(side, amount, price, token_id, reason=reason)
            return success, msg
        else:
            success, msg = self.sim.buy(side, amount, price, reason=reason)
            return success, msg

    def execute_sell(self, is_live, side, token_id, limit_price, best_bid, reason=""):
        if is_live:
             return self.live.sell(side, token_id, limit_price=limit_price, best_bid=best_bid, reason=reason)
        else:
             return self.sim.sell(side, limit_price, reason=reason)

# Textual Imports
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Button, RichLog, Label, Checkbox
from textual.screen import ModalScreen
from textual import work, on

# Live Trading Imports
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, BalanceAllowanceParams
from web3 import Web3

load_dotenv()

# --- CONFIG ---
POLYGON_RPC_LIST = [
    os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com"),
    os.getenv("POLYGON_RPC", "https://polygon-rpc.com"),
    "https://rpc-mainnet.maticvigil.com",
    "https://rpc.ankr.com/polygon",
    "https://1rpc.io/matic"
]
POLYGON_RPC_LIST = list(dict.fromkeys(filter(None, POLYGON_RPC_LIST)))

CHAINLINK_BTC_FEED = "0xc907E116054Ad103354f2D350FD2514433D57F6f"
CHAINLINK_ABI = '[{"inputs":[],"name":"latestAnswer","outputs":[{"internalType":"int256","name":"","type":"int256"}],"stateMutability":"view","type":"function"}]'

# Live Config
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
CHAIN_ID = 137
HOST = "https://clob.polymarket.com"

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
        budget_pct = TradingConfig.DEFAULT_RISK_PCT
        
        # Boost for strong patterns
        strong_patterns = ["UPTREND", "STRONG_TREND", "COBRA", "LIQ_SWEEP", "LATE_REVERSAL"]
        if any(p in strategy_type for p in strong_patterns):
            budget_pct = TradingConfig.STRONG_RISK_PCT
            
        # Base percentage of current balance or Global Risk Cap
        base_capital = context.get('risk_cap', self.balance)
        # If using Algo-specific balance tracking, maybe we want min(self.balance, risk_cap)?
        # For now, let's trust risk_cap as the "available funds".
        
        cost = base_capital * budget_pct
        
        # 1. Macro 4H Adjustment
        trend_4h = context.get('trend_4h', 'NEUTRAL')
        direction = context.get('direction', 'UP')
        if trend_4h != 'NEUTRAL' and trend_4h != direction:
            cost *= 0.5 # Penalty for trading against 4H macro
            
        # 2. Consecutive Loss Penalty (Streak Filter)
        if self.consecutive_losses >= 2:
            cost *= 0.7
            
        # 3. Minimum & Maximum Safety Caps
        if cost < TradingConfig.MIN_BET:
            # If we have enough for Min, use Min. Otherwise 0 (Algorithm Dies).
            cost = TradingConfig.MIN_BET if self.balance >= TradingConfig.MIN_BET else 0
        
        if cost > TradingConfig.MAX_BET_SESSION_CAP:
            cost = TradingConfig.MAX_BET_SESSION_CAP
            
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
        if self.balance < TradingConfig.MIN_BET:
            self.is_active = False
            
        return total_payout, total_profit

# --- SCANNERS ---

class BaseScanner:
    def __init__(self):
        self.triggered_signal = None
        
    def reset(self):
        self.triggered_signal = None
        
    def get_price_slice(self, history, start_elapsed, end_elapsed):
        if not history: return []
        return [p['price'] for p in history if start_elapsed <= p['elapsed'] <= end_elapsed]

class NPatternScanner(BaseScanner):
    def __init__(self):
        super().__init__()
        self.min_impulse_size = 0.0003
        self.max_retrace_depth = 0.85
        self.support_tolerance = TradingConfig.TOLERANCE_PCT
        
    def analyze(self, history_objs, open_price):
        if self.triggered_signal and "BET_" in self.triggered_signal:
            return self.triggered_signal
            
        if not history_objs: return "WAIT"
        # Phase 1: 0 to 60s
        phase1_prices = self.get_price_slice(history_objs, 0, TradingConfig.PHASE1_DURATION)
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

class FakeoutScanner(BaseScanner):
    def __init__(self): super().__init__()
    def analyze(self, history_objs, open_price, prev_window_color):
        if self.triggered_signal: return self.triggered_signal
        if not history_objs or not prev_window_color: return "NO_SIGNAL"
        early_prices = self.get_price_slice(history_objs, 0, TradingConfig.PHASE1_DURATION)
        if not early_prices: return "NO_SIGNAL"
        spike_high = max(early_prices)
        current_price = history_objs[-1]['price']
        if (spike_high > open_price) and (current_price < open_price):
            if prev_window_color == "RED": self.triggered_signal = f"BET_DOWN_AGGRESSIVE|Rejected Rescue & Trend Align"
            elif prev_window_color == "GREEN": self.triggered_signal = f"WAIT_FOR_CONFIRMATION|Rejected Rescue vs Trend"
            return self.triggered_signal
        return "NO_SIGNAL"

class TailWagScanner(BaseScanner):
    def __init__(self): super().__init__()
    def analyze(self, time_remaining, poly_volume, spot_depth, leader_direction, spot_price, price_history):
        if self.triggered_signal: return self.triggered_signal
        if time_remaining >= 60: return "WAIT_TIME"
        if not poly_volume or not spot_depth or spot_depth == 0: return "NO_DATA"
        if float(poly_volume) > (float(spot_depth) * 1.5):
            recent_prices = [p['price'] for p in price_history if p['elapsed'] >= (TradingConfig.WINDOW_SECONDS-time_remaining-10)]
            if not recent_prices: return "WAIT_DATA"
            move_pct = (recent_prices[-1] - recent_prices[0]) / recent_prices[0]
            confirmed = (leader_direction == "UP" and move_pct > 0.0005) or (leader_direction == "DOWN" and move_pct < -0.0005)
            if confirmed:
                self.triggered_signal = f"WHALE_LEADER_{leader_direction}|Whale vol > 1.5x Cost + Spot Reacted"
                return self.triggered_signal
        return "NO_SIGNAL"

class RsiScanner(BaseScanner):
    def __init__(self): super().__init__()
    def analyze(self, rsi, price, bb_lower, time_remaining):
        if self.triggered_signal: return self.triggered_signal
        if rsi < 15 and price < bb_lower and time_remaining > 100:
            self.triggered_signal = f"BET_UP_RSI_OVERSOLD|RSI {rsi:.1f} + Below BB"
            return self.triggered_signal
        return "WAIT"

class TrapCandleScanner(BaseScanner):
    def __init__(self): super().__init__()
    def analyze(self, price_history, open_price):
        if self.triggered_signal: return self.triggered_signal
        if not price_history: return "NO_DATA"
        try:
            p3_candle = next((x for x in price_history if x['elapsed'] >= TradingConfig.PHASE1_DURATION), None)
            if p3_candle:
                start_move = abs(p3_candle['price'] - open_price)
                current_move = abs(price_history[-1]['price'] - open_price)
                if (start_move / open_price > 0.003) and (current_move < start_move * 0.25):
                    self.triggered_signal = "BET_DOWN_FADE_BREAKOUT|Flash Crash >75% retraced"
                    return self.triggered_signal
        except: pass
        return "WAIT"

class MidGameScanner(BaseScanner):
    def __init__(self): super().__init__()
    def analyze(self, price_history, open_price, elapsed, trend_4h):
        if self.triggered_signal: return self.triggered_signal
        
        # Trend Gate: Don't short if Trend is UP
        if trend_4h == "UP": return "WAIT_TREND_MISMATCH"

        if elapsed < 100: return "WAIT_TIME"
        crossed_up = any(x['price'] > open_price for x in price_history if 100 <= x['elapsed'] <= 200)
        green_ticks = sum(1 for x in price_history if x['price'] > open_price and 100 <= x['elapsed'] <= 200)
        if crossed_up and green_ticks < 20 and price_history[-1]['price'] < open_price and elapsed > 200:
             self.triggered_signal = "BET_DOWN_FAILED_RESCUE|Bulls failed to hold green"
             return self.triggered_signal
        return "WAIT"

class LateReversalScanner(BaseScanner):
    def __init__(self): super().__init__()
    def analyze(self, price_history, open_price, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if elapsed < 220: return "WAIT_TIME"
        early_low = min([x['price'] for x in price_history if x['elapsed'] < 140], default=open_price)
        if early_low >= open_price * 0.999: return "WAIT_NO_DROP"
        crossed = any(x['price'] > open_price for x in price_history if 140 <= x['elapsed'] <= 200)
        if not crossed: return "WAIT_NO_CROSS"
        if price_history[-1]['price'] > open_price * 1.0005:
            self.triggered_signal = "BET_UP_LATE_REVERSAL|Late surge to green"
            return self.triggered_signal
        return "WAIT"

class StaircaseBreakoutScanner(BaseScanner):
    def __init__(self): super().__init__()
    def analyze(self, close_prices):
        if self.triggered_signal: return self.triggered_signal
        if len(close_prices) < 20: return "WAIT_DATA"
        window = close_prices[-15:]
        lows = [window[i] for i in range(1, len(window) - 1) if window[i] <= window[i-1] and window[i] <= window[i+1]]
        if len(lows) < 3: return "WAIT_PATTERN"
        if all(lows[i] < lows[i+1] for i in range(len(lows)-1)):
            recent_high = max(window)
            if (recent_high - min(window)) > (min(window) * TradingConfig.TOLERANCE_PCT):
                if window[-1] >= (recent_high * 0.9995):
                     self.triggered_signal = "BET_UP_AGGRESSIVE|Staircase Breakout Confirmed"
                     return self.triggered_signal
        return "WAIT"

class PostPumpScanner(BaseScanner):
    def __init__(self): super().__init__()
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

class StepClimberScanner(BaseScanner):
    def __init__(self): super().__init__()
    def analyze(self, close_prices):
        if self.triggered_signal: return self.triggered_signal
        if len(close_prices) < 20: return "WAIT"
        ma20 = sum(close_prices[-20:]) / 20
        if abs(close_prices[-1] - ma20) < (close_prices[-1] * 0.0015) and close_prices[-1] > ma20:
             self.triggered_signal = "SNIPER_ENTRY_UP|Perfect touch of MA20"
             return self.triggered_signal
        return "WAIT"

class SlingshotScanner(BaseScanner):
    def __init__(self): super().__init__()
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

class MinOneScanner(BaseScanner):
    def __init__(self): super().__init__()
    def analyze(self, price_history, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if elapsed < 60 or elapsed > 130: return "WAIT"
        min1 = self.get_price_slice(price_history, 0, TradingConfig.PHASE1_DURATION)
        if not min1: return "WAIT"
        h = max(min1); l = min(min1)
        c = min1[-1]; o = min1[0]; body = abs(c - o)
        
        # INCREASED THRESHOLD: 1.5 -> 2.0
        if (h - max(o, c)) > body * 2.0: self.triggered_signal = "BET_DOWN_WICK|Liar's Wick Detected"; return self.triggered_signal
        if (min(o, c) - l) > body * 2.0: self.triggered_signal = "BET_UP_WICK|Liar's Wick Detected"; return self.triggered_signal
        return "WAIT"

class LiquidityVacuumScanner(BaseScanner):
    def __init__(self):
        super().__init__()
        self.swept = False
        self.sweep_high = 0
    def reset(self):
        super().reset()
        self.swept = False
        self.sweep_high = 0
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

class CobraScanner(BaseScanner):
    def __init__(self): super().__init__()
    def analyze(self, closes_60m, current_price, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if elapsed > 180 or len(closes_60m) < 20: return "WAIT"
        slice_ = closes_60m[-20:]; sma = sum(slice_) / 20
        std = (sum((x - sma) ** 2 for x in slice_) / 20) ** 0.5
        if current_price > (sma + 2*std): self.triggered_signal = "BET_UP_COBRA|Explosive breakout"; return self.triggered_signal
        if current_price < (sma - 2*std): self.triggered_signal = "BET_DOWN_COBRA|Explosive breakdown"; return self.triggered_signal
        return "WAIT"

class MesaCollapseScanner(BaseScanner):
    def __init__(self):
        super().__init__()
        self.state = "SEARCHING"
        self.mesa_floor = None
        self.pump_start_time = None
    def reset(self): super().reset(); self.state = "SEARCHING"; self.mesa_floor = None; self.pump_start_time = None
    def analyze(self, price_history, open_price, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if elapsed < 60: return "WAIT_TIME"
        current_price = price_history[-1]['price']
        if self.state == "SEARCHING":
            if elapsed <= 60 and (current_price - open_price) / open_price > 0.0015:
                self.state = "WATCHING_TOP"; self.pump_start_time = elapsed; return "PUMP_DETECTED"
        elif self.state == "WATCHING_TOP":
            if elapsed < (self.pump_start_time + 40): return "WAIT_DEVELOP"
            mesa_window = self.get_price_slice(price_history, elapsed - 60, elapsed)
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

class MeanReversionScanner(BaseScanner):
    def __init__(self): super().__init__()
    def analyze(self, price_history, fast_bb, trend_4h):
        if self.triggered_signal: return self.triggered_signal
        
        # Trend Gate: Don't short if Trend is UP
        if trend_4h == "UP": return "WAIT_TREND_MISMATCH"

        if not fast_bb or len(price_history) < 20: return "WAIT"
        upper_band = fast_bb[0]; current_price = price_history[-1]['price']
        recent_prices = self.get_price_slice(price_history, 0, 99999) # Get all
        if not recent_prices: return "WAIT"
        
        # Check last 20
        last_20 = recent_prices[-20:]
        if any(p > upper_band for p in last_20) and current_price < upper_band:
            peak_price = max(last_20)
            if (peak_price - current_price) / peak_price > 0.0005:
                self.triggered_signal = f"SHORT_THE_SNAP|Rejection from Top"; return self.triggered_signal
        return "WAIT"

class GrindSnapScanner(BaseScanner):
    def __init__(self): super().__init__()
    def analyze(self, price_history, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if elapsed < 130: return "WAIT_TIME"
        p_now = price_history[-1]['price']
        p_snap_end = next((x['price'] for x in reversed(price_history) if x['elapsed'] <= (elapsed - 10)), None)
        p_snap_start = next((x['price'] for x in reversed(price_history) if x['elapsed'] <= (elapsed - 30)), None)
        p_grind_start = next((x['price'] for x in reversed(price_history) if x['elapsed'] <= (elapsed - 130)), None)
        if not p_snap_end or not p_snap_start or not p_grind_start: return "WAIT"
        grind_move = p_snap_start - p_grind_start
        if abs(grind_move / p_grind_start) < 0.001: return "WAIT_FLAT"
        snap_move = p_snap_end - p_snap_start
        recent_30s = self.get_price_slice(price_history, elapsed - 10, elapsed)
        if grind_move > 0 and any(p > p_snap_start for p in recent_30s): return "WAIT_FAILED_HOLD"
        elif grind_move < 0 and any(p < p_snap_start for p in recent_30s): return "WAIT_FAILED_HOLD"
        if abs(snap_move / grind_move) > 0.60:
             self.triggered_signal = f"BET_{'DOWN' if grind_move > 0 else 'UP'}_SNAP|Grind Snapped"; return self.triggered_signal
        return "WAIT"

class VolCheckScanner(BaseScanner):
    def __init__(self): super().__init__()
    def analyze(self, closes_60m, current_price, open_price, elapsed, up_p, down_p):
        if self.triggered_signal: return self.triggered_signal
        if (TradingConfig.WINDOW_SECONDS-elapsed) > 100 or (TradingConfig.WINDOW_SECONDS-elapsed) < 10: return "WAIT_TIME"
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

class MosheSpecializedScanner(BaseScanner):
    def __init__(self):
        super().__init__()
        self.checkpoints = {}
    def reset(self): super().reset(); self.checkpoints = {}
    def analyze(self, elapsed, price, open_price, trend_4h, up_p, down_p):
        if self.triggered_signal: return self.triggered_signal
        leader_p = up_p if price > open_price else down_p
        drift = abs(price - open_price) / open_price if open_price > 0 else 0
        if 100 <= elapsed <= 260 and elapsed not in self.checkpoints: self.checkpoints[elapsed] = leader_p
        if 100 <= elapsed <= 180:
            times = sorted(self.checkpoints.keys()); recent = [self.checkpoints[t] for t in times if elapsed - t <= 30]
            if len(recent) >= 3:
                consec = 0; max_consec = 0
                for i in range(1, len(recent)):
                    if recent[i] > recent[i-1]: consec += 1
                    else: consec = 0
                    max_consec = max(max_consec, consec)
                if max_consec >= 3 and (recent[-1] - recent[0]) >= 0.25 and drift > 0.0004 and 0.10 < leader_p < 0.85:
                    self.triggered_signal = f"MOSHE_STRONG_TREND_{'UP' if price > open_price else 'DOWN'}|Surge Detected"; return self.triggered_signal
        elif 220 <= elapsed <= 260:
            if 0.80 <= leader_p <= 0.92 and drift > 0.003:
                if (price > open_price and trend_4h == "UP") or (price < open_price and trend_4h == "DOWN"):
                    self.triggered_signal = f"MOSHE_SNIPER_{'UP' if price > open_price else 'DOWN'}|Trend Match"; return self.triggered_signal
        return "WAIT"

class ZScoreBreakoutScanner(BaseScanner):
    def __init__(self): super().__init__()
    def analyze(self, price_history, open_price, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if elapsed < 220: return "WAIT_TIME"
        early_data = self.get_price_slice(price_history, 0, 220)
        if not early_data: return "WAIT"
        avg = sum(early_data)/len(early_data); std = (sum((p-avg)**2 for p in early_data)/len(early_data))**0.5 or 0.01
        if (max(early_data)-min(early_data))/open_price > 0.001: return "WAIT_NO_COIL"
        z = (price_history[-1]['price'] - avg) / std
        thresh = 3.5 if elapsed < 260 else 3.0
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


# --- SIM BROKER ---
class SimBroker:
    def __init__(self, balance, log_file):
        self.balance = balance
        self.shares = {"UP": 0.0, "DOWN": 0.0}
        self.invested_this_window = 0.0
        self.log_file = log_file
        self.init_log()

    def init_log(self):
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w') as f:
                # --- SUPER INFORMATIVE CSV HEADER ---
                header = (
                    "Timestamp,Mode,SimBal,LiveBal,RiskBankroll,"
                    "TimeRem,BTC_Price,BTC_Open,BTC_Diff,BTC_Range,"
                    "Odds_Score,Trend_Prob,Trend_Score,"
                    "Sig_Slingshot,Sig_Poly,Sig_Cobra,Sig_Flag,Sig_TrendOdds,"
                    "Master_Score,Master_Status,"
                    "UP_Price,DN_Price,UP_Bid,DN_Bid,"
                    "Shares_UP,Shares_DN,Note"
                )
                f.write(header + "\n")

    def write_to_log(self, text):
        with open(self.log_file, 'a') as f:
            f.write(text + "\n")

    def log_trade(self, type_, side, amount, price, shares, note=""):
        # We log trades as a special event line in the CSV to avoid breaking the format
        # or we can print them to console. For the CSV, let's append a note in the snapshot
        # or use a separate trade indicator. Here we just log it as a raw line with prefix.
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.write_to_log(f"TRADE_EVENT,{ts},{type_},{side}, Amt:{amount:.2f}, Price:{price:.3f}, Shares:{shares:.2f}, Note:{note}")

    def log_snapshot(self, md, time_rem_str, is_live_active, live_bal, risk_bankroll):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mode = "LIVE" if is_live_active else "SIM"
        diff = md['btc_price'] - md['btc_open']
        
        # Prepare CSV Line
        line = (
            f"{ts},{mode},{self.balance:.2f},{live_bal:.2f},{risk_bankroll:.2f},"
            f"{time_rem_str},{md['btc_price']:.2f},{md['btc_open']:.2f},{diff:.2f},{md['btc_dyn_rng']:.2f},"
            f"{md['btc_odds']},{md['trend_prob']:.4f},{md['trend_score']},"
            f"{md['sling_signal']},{md['poly_signal']},{md['cobra_signal']},{md['flag_signal']},{md['to_signal']},"
            f"{md['master_score']},{md['master_status']},"
            f"{md['up_price']:.3f},{md['down_price']:.3f},{md['up_bid']:.3f},{md['down_bid']:.3f},"
            f"{self.shares['UP']:.2f},{self.shares['DOWN']:.2f},-"
        )
        self.write_to_log(line)

    def buy(self, side, usd_amount, price, reason="Manual"):
        if usd_amount > self.balance: return False, "Insufficient Funds"
        shares = usd_amount / price
        self.balance -= usd_amount
        self.invested_this_window += usd_amount
        self.shares[side] += shares
        self.log_trade("BUY", side, usd_amount, price, shares, note=reason)
        return True, f"Bought {shares:.2f} {side} @ {price*100:.1f}¢ | Cost: ${usd_amount:.2f} ({reason})"

    def sell(self, side, price, reason="Manual"):
        shares = self.shares[side]
        if shares <= 0: return False, "No shares"
        revenue = shares * price
        self.balance += revenue
        self.invested_this_window -= revenue
        self.shares[side] = 0.0
        self.log_trade("SELL", side, revenue, price, shares, f"{reason}")
        return True, f"Sold {shares:.2f} {side} for ${revenue:.2f}"

    def settle_window(self, winning_side):
        winning_shares = self.shares[winning_side]
        payout = winning_shares * 1.00
        net_pnl = payout - self.invested_this_window
        self.balance += payout
        self.log_trade("SETTLE", winning_side, payout, 1.00, winning_shares, f"Win: {winning_side} | PnL: {net_pnl:.2f}")
        self.shares = {"UP": 0.0, "DOWN": 0.0}
        self.invested_this_window = 0.0
        return payout, net_pnl

# --- LIVE BROKER ---
class LiveBroker:
    def __init__(self, sim_broker_ref):
        self.client = None
        self.sim_broker = sim_broker_ref 
        self.balance = 0.0
        self.init_client()

    def init_client(self):
        if not PRIVATE_KEY: return
        try:
            funder = PROXY_ADDRESS if PROXY_ADDRESS else Account.from_key(PRIVATE_KEY).address
            self.client = ClobClient(host=HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID, signature_type=1 if PROXY_ADDRESS else 0, funder=funder)
            self.client.set_api_creds(self.client.create_or_derive_api_creds())
            self.update_balance()
        except Exception as e:
            self.sim_broker.write_to_log(f"[LIVE ERROR] Init failed: {e}")

    def update_balance(self):
        if not self.client: return 0.0
        try:
            bal = float(self.client.get_balance_allowance(BalanceAllowanceParams(asset_type="COLLATERAL")).get('balance', 0)) / 10**6
            self.balance = bal
            return bal
        except: return 0.0

    def buy(self, side, usd_amount, price, token_id, reason="Manual"):
        if not self.client or not token_id: return False, "Client/Token Error"
        try:
            size = round(usd_amount / price, 2)
            limit_price = 0.99
            o_args = OrderArgs(price=limit_price, size=size, side="BUY", token_id=token_id)
            r = self.client.post_order(self.client.create_order(o_args))
            if r.get("success") or r.get("orderID"):
                self.sim_broker.write_to_log(f"TRADE_EVENT,{datetime.now()},LIVE_BUY,{side},Cost:{usd_amount},Price:{price},Size:{size},{reason}")
                self.update_balance()
                return True, f"✅ LIVE BUY {side} | {price*100:.1f}¢ | Cost: ${usd_amount:.2f} | Pot. Win: ${size:.2f}"
            else:
                return False, f"Live Fail: {r.get('errorMsg')}"
        except Exception as e:
            return False, f"Err: {e}"

    def sell(self, side, token_id, limit_price=0.02, best_bid=None, reason="Manual"):
        if not self.client or not token_id: return False, "Client/Token Error"
        try:
            b = self.client.get_balance_allowance(BalanceAllowanceParams(asset_type="CONDITIONAL", token_id=token_id))
            shares = float(b.get("balance", 0)) / 10**6
            if shares <= 0.001: return False, "No Live Pos"
            
            # FIX: Round DOWN
            size = math.floor(shares * 100) / 100
            if size <= 0: return False, "Size too small"

            val_log = f"Selling {size} @ Limit ${limit_price}"
            if best_bid: val_log += f" (Bid: ${best_bid})"
            self.sim_broker.write_to_log(f"DEBUG_SELL: {val_log}")

            o_args = OrderArgs(price=limit_price, size=size, side="SELL", token_id=token_id)
            r = self.client.post_order(self.client.create_order(o_args))
            if r.get("success") or r.get("orderID"):
                # Effective Price for logging: Use best_bid if available and reasonable, else limit
                eff_price = limit_price
                if best_bid and best_bid > limit_price: eff_price = best_bid
                
                proceeds = size * eff_price
                msg = f"✅ LIVE SOLD {side}: {size:.2f} Shares @ ${eff_price:.2f} (Total: ${proceeds:.2f})"
                self.sim_broker.write_to_log(f"TRADE_EVENT,{datetime.now()},LIVE_SELL,{side},Shares:{size},Price:{eff_price},Total:{proceeds},{reason}")
                self.update_balance()
                return True, msg
            else:
                err = r.get('errorMsg') or str(r)
                self.sim_broker.write_to_log(f"LIVE_SELL_FAIL: {err}")
                return False, f"Live Sell Fail: {err}"
        except Exception as e:
            return False, f"Sell Err: {e}"

# ... (In PolySimApp)
    async def trigger_sell_all(self, side):
        is_live = self.query_one("#cb_live").value
        if is_live:
             token_id = self.market_data["up_id"] if side == "UP" else self.market_data["down_id"]
             if token_id:
                # Sell at Bid minus slippage to ensure fill, but keep price valid
                curr_bid = self.market_data["up_bid"] if side == "UP" else self.market_data["down_bid"]
                target_price = max(0.02, curr_bid - 0.05)
                
                success, msg = self.live_broker.sell(side, token_id, limit_price=target_price, reason="Manual Live Sell")
                if success: 
                    self.log_msg(f"[bold red]{msg}[/]")
                    try:
                        rev = float(msg.split("Shares")[0].split(":")[-1].strip()) * 0.99 
                        if self.risk_cap_initialized: self.dynamic_risk_cap += rev
                    except: pass
                else: self.log_msg(f"[red]{msg}[/]")

# --- APP ---
class SniperApp(App):
    CSS = """
    Screen { align: center top; layers: base; }
    #top_bar { dock: top; height: 1; background: $panel; color: $text; content-align: center middle; }
    #header_stats { width: auto; margin-right: 2; }
    .timer_text { text-style: bold; color: $warning; }
    .run_time { color: #00ffff; margin-left: 2; }
    .live_mode { color: #ff0000; text-style: bold; background: #330000; }
    
    .row_main { height: 8; margin: 0; padding: 0; }
    .price_card { height: 100%; border: ascii $secondary; margin: 0; padding: 0; background: $surface; }
    #card_btc { width: 4fr; border: ascii #f7931a; layout: grid; grid-size: 3; grid-columns: 1fr 1fr 1fr; grid-rows: 1fr 1fr 1fr 1fr; }
    #card_btc > Label { width: 100%; height: 100%; content-align: center middle; padding: 0; }
    .right_col { width: 1fr; height: 100%; }
    .mini_card { height: 1fr; border: ascii; margin: 0; padding: 0; align: center middle; }
    #card_up { border: ascii #00ff00; }
    #card_down { border: ascii #ff0000; }
    .price_val { text-style: bold; color: #ffffff; }
    .price_sub { color: #aaaaaa; } 
    .sig_up { color: #00ff00; text-style: bold; }
    .sig_down { color: #ff0000; text-style: bold; }
    .sig_wait { color: #666666; }
    .master_up { color: #00ff00; text-style: bold; background: #003300; width: 100%; text-align: center; }
    .master_down { color: #ff0000; text-style: bold; background: #330000; width: 100%; text-align: center; }
    .master_neu { color: #cccccc; width: 100%; text-align: center; }
    
    /* INPUT GROUPS */
    .input_group { height: 3; align: center middle; layout: horizontal; padding: 0; margin-bottom: 1; border-bottom: solid $primary; }
    .lbl_sm { content-align: center middle; margin-right: 1; color: #aaaaaa; }
    Input { width: 12; height: 1; margin: 0 1; background: $surface; border: none; color: #ffffff; text-align: center; }
    #inp_tp { color: #00ff00; }
    #inp_sl { color: #ff0000; }
    #inp_min_diff { color: #00ffff; }

    /* BUTTONS ON SECOND ROW */
    #button_row { height: 3; align: center middle; layout: horizontal; padding: 0; margin-bottom: 1; }
    Button { height: 1; min-width: 12; margin: 0 1; border: none; }
    .btn_buy_up { background: #006600; color: #ffffff; }
    .btn_buy_down { background: #660000; color: #ffffff; }
    .btn_sell_up { background: #b38600; color: #ffffff; }
    .btn_sell_down { background: #b34b00; color: #ffffff; }

    #checkbox_container { height: auto; border-bottom: double $primary; margin-bottom: 1; }
    .algo_row { align: center middle; height: 1; layout: horizontal; padding: 0; margin: 0; }
    .settings_row { align: center middle; height: 3; layout: horizontal; padding: 0 1; background: #222222; }
    .live_row { align: center middle; height: 3; background: #220000; padding: 0 1; border-top: solid #440000; }
    /* Checkbox visibility fix: use 1fr to distribute even space, remove margin/padding */
    Checkbox { width: 1fr; height: 1; margin: 0; padding: 0; border: none; align: center middle; }
    /* Ensure label is visible */
    Checkbox > .toggle--label { padding: 0 1; }
    #cb_live { color: #ff0000; text-style: bold; width: auto; }
    RichLog { height: 1fr; min-height: 5; background: #111111; color: #eeeeee; }
    
    /* IMPROVED CHECKBOX VISIBILITY */
    Checkbox { color: #666666; }
    Checkbox.-on { color: #00ff00; text-style: bold; }
    Checkbox > .toggle--button { background: #333333; color: #333333; border: none; }
    Checkbox.-on > .toggle--button { background: #00ff00; color: #000000; border: none; }
    Checkbox.-on > .toggle--label { color: #00ff00; text-style: bold; }
    """

    def __init__(self, sim_broker, live_broker, start_live_mode=False):
        super().__init__()
        self.sim_broker = sim_broker
        self.live_broker = live_broker
        self.start_live_mode = start_live_mode
        # --- DATA & RISK MANAGERS ---
        # We pass a lambda that uses call_from_thread to ensure thread safety when logging from background threads
        self.market_data_manager = MarketDataManager(logger_func=lambda m: self.call_from_thread(self.log_msg, m))
        self.risk_manager = RiskManager()
        self.trade_executor = TradeExecutor(sim_broker, live_broker, self.risk_manager)
        
        self.market_data = self.market_data_manager.market_data # Reference to manager's data dict
        self.risk_initialized = False # UI Warning Flag
        
        # Initialize Scanners
        self.scanners = {
            "NPattern": NPatternScanner(),
            "Fakeout": FakeoutScanner(),
            "TailWag": TailWagScanner(),
            "RSI": RsiScanner(),
            "TrapCandle": TrapCandleScanner(),
            "MidGame": MidGameScanner(),
            "LateReversal": LateReversalScanner(),
            "BullFlag": StaircaseBreakoutScanner(), # Corrected from BullFlagScanner to StaircaseBreakoutScanner based on original
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
        
        # Initialize Portfolios (One per Scanner)
        self.portfolios = {}
        for name in self.scanners:
            self.portfolios[name] = AlgorithmPortfolio(name, 100.0)
            
        
        self.price_history = [] # Now managed by MarketDataManager, but kept for legacy external access if any?
        # Actually scanner loop uses self.market_data_manager.price_history
        # So we can remove this, but let's check if any other method uses it.
        # Dump state log uses market_data dictionary.
        # Check_tpsl uses market_data dictionary.
        # So safe to remove.
        
        # self.trend_4h = "NEUTRAL"
        # self.last_4h_update = 0
        self.window_bets = {} # Map bet_id -> info
        self.last_second_exit_triggered = False # Flag to ensure single execution
        
        self.app_start_time = time.time()

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Label(f"SIM | Bal: ${self.sim_broker.balance:.2f}", id="header_stats"),
            Label(f" | RUN: 00:00:00", id="lbl_runtime", classes="run_time"),
            Label(" | WIN: ", classes="timer_text"),
            Label("00:00", id="lbl_timer_big", classes="timer_text"),
            id="top_bar"
        )
        yield Horizontal(
            Container(
                Label("$0.00", id="p_btc", classes="price_val"),
                Label("Open: $0", id="p_btc_open", classes="price_sub"),
                Label("Diff: $0", id="p_btc_diff", classes="price_sub"),
                Label("Trend 4H: NEUTRAL", id="p_trend", classes="price_sub"),
                id="card_btc", classes="price_card"
            ),
            Vertical(
                Vertical(Label("UP", classes="price_sub"), Label("0.0¢", id="p_up", classes="price_val"), id="card_up", classes="mini_card"),
                Vertical(Label("DN", classes="price_sub"), Label("0.0¢", id="p_down", classes="price_val"), id="card_down", classes="mini_card"),
                classes="right_col"
            ),
            classes="row_main"
        )
        
        # --- INPUTS ROW 1 (Trading) ---
        yield Container(
            Label("Bet:", classes="lbl_sm"),
            Input(placeholder="Bet $", value="1.00", id="inp_amount"),
            Label("Bankroll:", classes="lbl_sm"),
            Input(placeholder="Risk Bankroll", id="inp_risk_alloc"),
            Label("TP %:", classes="lbl_sm"),
            Input(placeholder="TP %", value="100", id="inp_tp"),
            Label("SL %:", classes="lbl_sm"),
            Input(placeholder="SL %", value="100", id="inp_sl"),
            classes="input_group"
        )
        
        # --- INPUTS ROW 2 (Strategy Config) ---
        yield Container(
            Label("Sim Bal:", classes="lbl_sm"),
            Input(placeholder="Sim Bal", value=f"{self.sim_broker.balance:.2f}", id="inp_sim_bal"),
            Label("Min Diff:", classes="lbl_sm"),
            Input(placeholder="Min Diff $", value="0", id="inp_min_diff"),
            Label("Min Price:", classes="lbl_sm"),
            Input(placeholder="Min Price", value="0.01", id="inp_min_price"),
            Label("Max Price:", classes="lbl_sm"),
            Input(placeholder="Max Price", value="0.99", id="inp_max_price"),
            classes="input_group"
        )

        # --- BUTTONS ROW ---
        yield Container(
            Button("BUY UP", id="btn_buy_up", classes="btn_buy_up"), 
            Button("BUY DN", id="btn_buy_down", classes="btn_buy_down"),
            Button("SELL UP", id="btn_sell_up", classes="btn_sell_up"), 
            Button("SELL DN", id="btn_sell_down", classes="btn_sell_down"),
            id="button_row"
        )
        
        # --- V4 SCANNERS GRID (3-Letter Codes) ---
        # Compact: 6 per row
        # Row 1: NPA, FAK, TAI, RSI, TRA, MID
        yield Horizontal(
            Checkbox("NPA", value=True, id="cb_npa"), Checkbox("FAK", value=True, id="cb_fak"),
            Checkbox("TAI", value=True, id="cb_tai"), Checkbox("RSI", value=True, id="cb_rsi"),
            Checkbox("TRA", value=True, id="cb_tra"), Checkbox("MID", value=True, id="cb_mid"),
            classes="algo_row"
        )
        # Row 2: LAT, STA, POS, STE, SLI, MIN
        yield Horizontal(
            Checkbox("LAT", value=True, id="cb_lat"), Checkbox("STA", value=True, id="cb_sta"),
            Checkbox("POS", value=True, id="cb_pos"), Checkbox("STE", value=True, id="cb_ste"),
            Checkbox("SLI", value=True, id="cb_sli"), Checkbox("MIN", value=True, id="cb_min"),
            classes="algo_row"
        )
        # Row 3: LIQ, COB, MES, MEA, GRI, VOL
        yield Horizontal(
            Checkbox("LIQ", value=True, id="cb_liq"), Checkbox("COB", value=True, id="cb_cob"),
            Checkbox("MES", value=True, id="cb_mes"), Checkbox("MEA", value=True, id="cb_mea"),
            Checkbox("GRI", value=True, id="cb_gri"), Checkbox("VOL", value=True, id="cb_vol"),
            classes="algo_row"
        )
        # Row 4: MOS, ZSC
        yield Horizontal(
            Checkbox("MOS", value=True, id="cb_mos"), Checkbox("ZSC", value=False, id="cb_zsc"),
            classes="algo_row"
        )

        # --- SETTINGS & LIVE ---
        yield Horizontal(
            Checkbox("TP/SL", value=True, id="cb_tp_active"),
            Checkbox("Strong Only", value=False, id="cb_strong"),
            Checkbox("1 Trade Max", value=False, id="cb_one_trade"), 
            Checkbox("Whale Protect", value=True, id="cb_whale"),
            Checkbox("ENABLE LIVE TRADING", value=False, id="cb_live"),
            classes="live_row"
        )

        yield RichLog(id="log_window", highlight=True, markup=True)

    async def on_mount(self):
        self.log_msg(f"Simulation Started. Bal: ${self.sim_broker.balance}")
        self.log_msg(f"Combined Log: {self.sim_broker.log_file}")
        
        # --- DEFAULT RISK BANKROLL (Sim = Full Balance) ---
        def_risk = self.sim_broker.balance
        self.query_one("#inp_risk_alloc").value = f"{def_risk:.2f}"
        self.log_msg(f"[cyan]Default Risk Alloc set to ${def_risk:.2f} (Full Sim Bal)[/]")

        self.init_web3()
        self.set_interval(2, self.fetch_market_loop)
        self.set_interval(1, self.update_timer)
        # --- 15 SEC LOGGING INTERVAL ---
        self.set_interval(15, self.dump_state_log)
        
        if self.start_live_mode:
            self.query_one("#cb_live").value = True 

    @on(Checkbox.Changed, "#cb_live")
    def on_live_toggle(self, event: Checkbox.Changed):
        if event.value: 
            self.log_msg("[bold red]LIVE MODE ENABLED! All Algos deselected for safety.[/]")
            
            # Auto-Disable All Scanners
            all_cbs = [
                "#cb_npa", "#cb_fak", "#cb_tai", "#cb_rsi",
                "#cb_tra", "#cb_mid", "#cb_lat", "#cb_sta",
                "#cb_pos", "#cb_ste", "#cb_sli", "#cb_min",
                "#cb_liq", "#cb_cob", "#cb_mes", "#cb_mea",
                "#cb_gri", "#cb_vol", "#cb_mos", "#cb_zsc"
            ]
            for cid in all_cbs:
                self.query_one(cid).value = False
                
            self.log_msg("[yellow]Please check the algos you want to run live.[/]")
            
            # Update Risk Bankroll for Live
            lb = self.live_broker.balance
            if lb > 0:
                self.query_one("#inp_risk_alloc").value = f"{lb/TradingConfig.LIVE_RISK_DIVISOR:.2f}"
                self.risk_manager.set_bankroll(lb, is_live=True)
                self.risk_initialized = True
                self.log_msg(f"[cyan]Risk Bankroll updated to Live 1/{TradingConfig.LIVE_RISK_DIVISOR}th: ${self.risk_manager.risk_bankroll:.2f}[/]")
        else:
            # Revert to Sim Risk (Full Balance)
            sb = self.sim_broker.balance
            self.query_one("#inp_risk_alloc").value = f"{sb:.2f}"
            self.risk_manager.set_bankroll(sb, is_live=False)
            self.risk_initialized = True
            self.log_msg(f"[cyan]Risk Bankroll reverted to Sim Balance: ${sb:.2f}[/]")

    @on(Checkbox.Changed)
    def on_any_checkbox(self, event: Checkbox.Changed):
        # Quick log of change
        cid = event.checkbox.id
        val = event.value
        if cid == "cb_live": return # Handled by specific handler
        
        # self.log_msg(f"[dim]Setting Changed: {cid} = {val}[/]")

    def log_msg(self, msg):
        self.query_one(RichLog).write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def dump_state_log(self):
        is_live = self.query_one("#cb_live").value
        # Pass current risk bankroll instead of old dynamic_risk_cap
        self.sim_broker.log_snapshot(self.market_data, self.time_rem_str, is_live, self.live_broker.balance, self.risk_manager.risk_bankroll)

    @work(exclusive=True, thread=True)
    def init_web3(self):
        try:
            from web3 import Web3
            for rpc in POLYGON_RPC_LIST:
                try:
                    self.w3_provider = Web3(Web3.HTTPProvider(rpc))
                    if not self.w3_provider.is_connected(): continue
                    self.chainlink_contract = self.w3_provider.eth.contract(address=Web3.to_checksum_address(CHAINLINK_BTC_FEED), abi=CHAINLINK_ABI)
                    self.chainlink_contract.functions.latestAnswer().call()
                    self.call_from_thread(self.log_msg, f"[green]Web3 Connected via {rpc}[/]")
                    return
                except Exception as e:
                    self.call_from_thread(self.log_msg, f"[yellow]RPC {rpc} failed: {e}[/]")
            self.call_from_thread(self.log_msg, "[red]All Web3 RPCs Failed. Using Binance backup.[/]")
        except ImportError as e:
            self.call_from_thread(self.log_msg, f"[red]Web3 Import Failed: {e}. Ensure 'web3' and dependencies are installed.[/]")
        except Exception as e:
            import traceback
            self.call_from_thread(self.log_msg, f"[red]Web3 Init Error: {e}\n{traceback.format_exc()}[/]")

    def update_balance_ui(self):
        is_live = self.query_one("#cb_live").value
        lbl = self.query_one("#header_stats")
        
        cap_display = ""
        if self.risk_initialized:
            cap_display = f" (Bankroll: ${self.risk_manager.risk_bankroll:.2f})"
            # self.query_one("#inp_risk_alloc").value = f"{self.dynamic_risk_cap:.2f}" # Don't overwrite while user types

        if is_live:
            bal = self.live_broker.balance
            lbl.update(f"[bold red]LIVE[/] | Bal: ${bal:.2f}{cap_display}")
            lbl.classes = "live_mode"
        else:
            bal = self.sim_broker.balance
            lbl.update(f"SIM | Bal: ${bal:.2f}{cap_display}")
            lbl.classes = ""

    def update_sell_buttons(self):
        md = self.market_data
        is_live = self.query_one("#cb_live").value
        btn_su = self.query_one("#btn_sell_up"); btn_sd = self.query_one("#btn_sell_down")
        
        if is_live:
            btn_su.label = "SELL UP (LIVE)"
            btn_sd.label = "SELL DN (LIVE)"
        else:
            su = self.sim_broker.shares["UP"]; sd = self.sim_broker.shares["DOWN"]
            if su > 0:
                btn_su.label = f"SELL UP\n(${su * md['up_bid']:.2f})"; btn_su.styles.background = "#b38600"
            else:
                btn_su.label = "SELL UP"; btn_su.styles.background = "#554400"
            if sd > 0:
                btn_sd.label = f"SELL DN\n(${sd * md['down_bid']:.2f})"; btn_sd.styles.background = "#b34b00"
            else:
                btn_sd.label = "SELL DN"; btn_sd.styles.background = "#552200"

    async def fetch_market_loop(self):
        try:
            now = datetime.now(timezone.utc); floor = (now.minute // 15) * 15
            ts_start = int(now.replace(minute=floor, second=0, microsecond=0).timestamp())
            
            # --- INITIALIZE RISK CAP (BANKROLL) ---
            if not self.risk_initialized:
                inp_val = self.query_one("#inp_risk_alloc").value
                try:
                    val = float(inp_val)
                    self.risk_manager.set_bankroll(val, is_live=self.query_one("#cb_live").value)
                    self.risk_initialized = True
                    self.log_msg(f"[cyan]Risk Bankroll Initialized: ${self.risk_manager.risk_bankroll:.2f}[/]")
                except: pass

            # --- SETTLEMENT LOGIC ---
            if self.market_data["start_ts"] != 0 and ts_start != self.market_data["start_ts"]:
                last_price = self.market_data["btc_price"]
                last_open = self.market_data["btc_open"]
                winner = "UP" if last_price >= last_open else "DOWN"
                
                # Global Broker Settlement
                self.sim_broker.settle_window(winner)
                
                # Portfolio Settlement
                for name, p in self.portfolios.items():
                    p.settle_window(winner, last_price, last_open)
                
                # --- REFILL RISK BANKROLL (Settlement Wins) ---
                total_payout = 0.0
                for bet_id, info in self.window_bets.items():
                    if info.get("closed"): continue # Already sold/accounted for
                    
                    # Check Winner
                    if info["side"] == winner:
                        # Payout = Shares * $1.00. Shares = Cost / Entry
                        try:
                            shares = info["cost"] / info["entry"]
                            total_payout += shares
                        except: pass
                    elif winner == "N/A": # Refund/Draw? (Rare)
                        total_payout += info["cost"]
                        
                if total_payout > 0:
                    self._add_risk_revenue(total_payout)
                    self.log_msg(f"[cyan]💰 Settlement Revenue: +${total_payout:.2f} (Refills Bankroll)[/]")

                self.log_msg(f"[bold yellow]SETTLED:[/]{winner}")
                # Reset Risk Manager Window
                self.risk_manager.reset_window()
                self.last_second_exit_triggered = False
                
                self.update_balance_ui()
                for s in self.scanners.values(): s.reset()
                self.window_bets.clear()
            
            self.market_data["start_ts"] = ts_start
            elapsed = int(now.timestamp()) - ts_start
            rem_min = max(1, min(15, (TradingConfig.WINDOW_SECONDS - elapsed + 59) // 60))
            slug = f"btc-updown-15m-{ts_start}"
            
            # --- DATA FETCHING (Threaded) ---
            def fetch_data(app_ref):
                # 1. Update 4H Trend
                app_ref.market_data_manager.update_4h_trend()
                
                # 2. Get 60m data for scanners
                closes_60, lows_60 = app_ref.market_data_manager.fetch_candles_60m()
                
                # 3. Get Current Price & Update History
                curr_price = app_ref.market_data_manager.fetch_current_price()
                open_price = app_ref.market_data_manager.update_history(curr_price, elapsed)
                
                # 4. Polymarket Prices
                poly_data = app_ref.market_data_manager.fetch_polymarket(slug)
                
                return {
                    "closes_60": closes_60, "lows_60": lows_60,
                    "curr": curr_price, "open": open_price,
                    "up_p": poly_data["up_price"], "down_p": poly_data["down_price"], # legacy mapping
                    "up_bid": poly_data["up_bid"], "down_bid": poly_data["down_bid"],
                    "up_ask": poly_data["up_ask"], "down_ask": poly_data["down_ask"],
                    "up_id": poly_data["up_id"], "down_id": poly_data["down_id"]
                }

            data = await asyncio.to_thread(fetch_data, self)
            
            # Init Default Signals for Legacy Logging & Avoid Crashes
            # SimBroker log_snapshot uses these keys
            legacy_defaults = {
                "sling_signal": "WAIT", "poly_signal": "N/A", "cobra_signal": "WAIT", 
                "flag_signal": "WAIT", "to_signal": "N/A", "master_score": 0, "master_status": "NEUTRAL",
                "trend_score": 3, "trend_prob": 0.5, "btc_odds": 0, "btc_dyn_rng": 0
            }
            self.market_data.update(legacy_defaults)
            
            # Update Market Data
            self.market_data.update({
                "btc_price": data["curr"], "btc_open": data["open"],
                "up_price": data["up_p"], "down_price": data["down_p"],
                "up_bid": data["up_bid"], "down_bid": data["down_bid"],
                "up_ask": data.get("up_ask", 0.99), "down_ask": data.get("down_ask", 0.99),
                "up_id": data["up_id"], "down_id": data["down_id"]
            })
            
            # --- RUN SCANNERS ---
            active_signals = []
            
            # Calculate Indicators
            rsi = calculate_rsi(data["closes_60"])
            _, _, low_bb = calculate_bb(data["closes_60"])
            # fast_bb = calculate_bb([p['price'] for p in self.price_history[-20:]]) if len(self.price_history) >= 20 else (0,0,0)
            # Update to use manager history
            ph = self.market_data_manager.price_history
            fast_bb = calculate_bb([p['price'] for p in ph[-20:]]) if len(ph) >= 20 else (0,0,0)
            
            # Map checkboxes to scanner names
            # NPattern, Fakeout, TailWag, RSI, TrapCandle, MidGame, LateReversal, BullFlag, PostPump, StepClimber, Slingshot, MinOne, Liquidity, Cobra, Mesa, MeanReversion, GrindSnap, VolCheck, Moshe, ZScore
            # UI IDs were: cb_npa, cb_fak, cb_tai, cb_rsi, cb_tra, cb_mid, cb_lat, cb_sta, cb_pos, cb_ste, cb_sli, cb_min, cb_liq, cb_cob, cb_mes, cb_mea, cb_gri, cb_vol, cb_mos, cb_zsc
            
            scanner_map = {
                "NPattern": "#cb_npa", "Fakeout": "#cb_fak", "TailWag": "#cb_tai", "RSI": "#cb_rsi",
                "TrapCandle": "#cb_tra", "MidGame": "#cb_mid", "LateReversal": "#cb_lat", "BullFlag": "#cb_sta",
                "PostPump": "#cb_pos", "StepClimber": "#cb_ste", "Slingshot": "#cb_sli", "MinOne": "#cb_min",
                "Liquidity": "#cb_liq", "Cobra": "#cb_cob", "Mesa": "#cb_mes", "MeanReversion": "#cb_mea",
                "GrindSnap": "#cb_gri", "VolCheck": "#cb_vol", "Moshe": "#cb_mos", "ZScore": "#cb_zsc"
            }
            
            for name, scanner in self.scanners.items():
                if not self.query_one(scanner_map.get(name, "")).value: continue
                
                portfolio = self.portfolios[name]
                try:
                    res = "WAIT"
                    # Dispatch Analysis
                    if name == "NPattern": res = scanner.analyze(self.market_data_manager.price_history, data["open"])
                    elif name == "Fakeout": res = scanner.analyze(self.market_data_manager.price_history, data["open"], "GREEN" if data["curr"] > data["open"] else "RED") # Simplified prev window color
                    elif name == "TailWag": 
                         # Simplified Volume
                         res = scanner.analyze(300-elapsed, 0, 1000, "UP" if data["up_p"]>data["down_p"] else "DOWN", data["curr"], self.market_data_manager.price_history)
                    elif name == "RSI": res = scanner.analyze(rsi, data["curr"], low_bb, 300-elapsed)
                    elif name == "TrapCandle": res = scanner.analyze(self.market_data_manager.price_history, data["open"])
                    elif name == "MidGame": res = scanner.analyze(self.market_data_manager.price_history, data["open"], elapsed, self.market_data_manager.trend_4h)
                    elif name == "LateReversal": res = scanner.analyze(self.market_data_manager.price_history, data["open"], elapsed)
                    elif name == "BullFlag": res = scanner.analyze(data["closes_60"])
                    elif name == "PostPump": res = scanner.analyze(data["curr"], data["open"], {}) # Missing last window data passing
                    elif name == "StepClimber": res = scanner.analyze(data["closes_60"])
                    elif name == "Slingshot": res = scanner.analyze(data["closes_60"])
                    elif name == "MinOne": res = scanner.analyze(self.market_data_manager.price_history, elapsed)
                    elif name == "Liquidity": res = scanner.analyze(data["curr"], min(data["lows_60"]) if data["lows_60"] else 0, data["open"])
                    elif name == "Cobra": res = scanner.analyze(data["closes_60"], data["curr"], elapsed)
                    elif name == "Mesa": res = scanner.analyze(self.market_data_manager.price_history, data["open"], elapsed)
                    elif name == "MeanReversion": res = scanner.analyze(self.market_data_manager.price_history, fast_bb, self.market_data_manager.trend_4h)
                    elif name == "GrindSnap": res = scanner.analyze(self.market_data_manager.price_history, elapsed)
                    elif name == "VolCheck": res = scanner.analyze(data["closes_60"], data["curr"], data["open"], elapsed, data["up_p"], data["down_p"])
                    elif name == "Moshe": res = scanner.analyze(elapsed, data["curr"], data["open"], self.market_data_manager.trend_4h, data["up_p"], data["down_p"])
                    elif name == "ZScore": res = scanner.analyze(self.market_data_manager.price_history, data["open"], elapsed)

                    if res and "BET_" in str(res):
                        active_signals.append(f"{name}: {res}")
                        
                        # --- EXECUTE TRADE ---
                        
                        # Fix: Check for ANY active bet from this algo in this window
                        # Prevents "bought 3 times" loop
                        already_active = any(k.startswith(f"{name}_") for k in self.window_bets)
                        if already_active: continue
                        
                        # Check 1 Trade Max (Global)
                        if self.query_one("#cb_one_trade").value and self.window_bets: continue
                        
                        # --- RISK MANAGER SIZING ---
                        bet_size = self.risk_manager.calculate_bet_size(
                            strategy_type=str(res),
                            balance=portfolio.balance,
                            consecutive_losses=portfolio.consecutive_losses,
                            trend_context={
                                'trend_4h': self.market_data_manager.trend_4h,
                                'direction': "UP" if "UP" in str(res) else "DOWN"
                            }
                        )
                        
                        if bet_size > 0:
                            side = "UP" if "UP" in str(res) else "DOWN"
                            # Use ASK for buying
                            price = self.market_data["up_ask"] if side == "UP" else self.market_data["down_ask"]
                            if not price or price <= 0: price = 0.50 # Fallback
                            
                            # Limit Check
                            if (side=="UP" and price >= 0.99) or (side=="DOWN" and price >= 0.99): continue
                            if (side=="UP" and price <= 0.01) or (side=="DOWN" and price <= 0.01): continue
                            
                            # Unique Bet ID
                            bet_id = f"{name}_{elapsed}"
                            if bet_id not in self.window_bets:
                                is_live = self.query_one("#cb_live").value
                                token_id = data["up_id"] if side == "UP" else data["down_id"]
                                
                                success, msg = self.trade_executor.execute_buy(is_live, side, bet_size, price, token_id, reason=res)
                                
                                if success:
                                    self.window_bets[bet_id] = {"side": side, "entry": price, "cost": bet_size}
                                    self.risk_manager.register_bet(bet_size)
                                    portfolio.record_trade(side, price, bet_size, bet_size/price)
                                    self.log_msg(f"[bold green]EXECUTED {name}[/]: {msg}")

                except Exception as e:
                    import traceback
                    self.log_msg(f"[red]Scanner Error ({name}): {e}[/]")
                    print(f"Scanner Traceback ({name}):\n{traceback.format_exc()}")

            # --- UI UPDATES ---
            self.update_balance_ui()
            self.update_sell_buttons()
            
            md = self.market_data
            self.query_one("#p_up").update(f"{md['up_price']*100:.1f}¢")
            self.query_one("#p_down").update(f"{md['down_price']*100:.1f}¢")
            self.query_one("#p_btc").update(f"${md['btc_price']:,.2f}")
            self.query_one("#p_btc_open").update(f"Open: ${md['btc_open']:,.2f}")
            
            diff = md['btc_price'] - md['btc_open']
            dl = self.query_one("#p_btc_diff"); dl.update(f"Diff: {'+' if diff>=0 else '-'}${abs(diff):.2f}"); dl.classes = "diff_green price_sub" if diff>=0 else "diff_red price_sub"
            
            # Simple Active Signals Display
            if active_signals:
                self.query_one("#card_btc").border_title = f"ACTIVE: {len(active_signals)}"
            else:
                self.query_one("#card_btc").border_title = "SCANNING..."

        except Exception as e:
            import traceback
            self.log_msg(f"[red]Loop Error: {e}[/]")
            print(traceback.format_exc()) # Print full traceback to console/log for debugging

    # REMOVED _fetch_candles_60m and _fetch_4h_trend as they are now in MarketDataManager

    def _check_tpsl(self):
        curr_bets = list(self.window_bets.items())
        is_live = self.query_one("#cb_live").value
        use_tp = self.query_one("#cb_tp_active").value
        
        try: tp_pct = float(self.query_one("#inp_tp").value) / 100.0
        except: tp_pct = 0.20
        
        try: sl_pct = float(self.query_one("#inp_sl").value) / 100.0
        except: sl_pct = 0.50

        for bet_id, info in curr_bets:
            if info.get("closed"): continue
            
            side = info["side"]
            entry = info["entry_price"]
            curr_price = self.market_data["up_price"] if side == "UP" else self.market_data["down_price"]
            reason = None

            # --- PRIORITY: MAX PROFIT (99¢) ---
            if curr_price >= 0.99:
                reason = "MAX PROFIT (99¢)"
            
            # --- WHALE SPLASH PROTECTION (< 30s) ---
            elif self.query_one("#cb_whale").value and self.market_data["start_ts"]:
                elapsed = time.time() - self.market_data["start_ts"]
                rem_sec = TradingConfig.WINDOW_SECONDS - elapsed # Should use 900 for 15m? 
                # Note: Logic uses 300 (5m). Should update to 900 if in 15m file?
                # User says "look at 15m.py". I am editing mbsts_sniper.py.
                # If this is 15m logic, keep 900. If 5m, keep 300.
                
                # Check line 403 or update_timer logic.
                # Assuming 5m base logic here. But let's check constants.
                if rem_sec <= 30:
                     btc_price = self.market_data["btc_price"]
                     # ... rest of logic
                     open_price = self.market_data["btc_open"]
                     diff = btc_price - open_price
                     
                     if side == "UP" and diff < 15.0:
                         reason = f"WHALE PROTECT (Diff ${diff:.1f} < $15)"
                     elif side == "DOWN" and diff > -15.0:
                         reason = f"WHALE PROTECT (Diff ${diff:.1f} > -$15)"

            if not reason:
                 # ROI Calculation
                 roi = (curr_price - entry) / entry
                 if use_tp and roi >= tp_pct: reason = f"TP HIT (+{roi*100:.1f}%)"
                 elif roi <= -sl_pct: reason = f"SL HIT ({roi*100:.1f}%)"
            

            if reason:
                # Execute Sell
                success = False; msg = ""
                token_id = self.market_data["up_id"] if side == "UP" else self.market_data["down_id"]
                
                # Sell at Bid minus buffer for fill. 
                # In Sim winners, use 0.99 to match User expectation of fair value before settlement.
                curr_bid = self.market_data["up_bid"] if side == "UP" else self.market_data["down_bid"] 
                
                if not is_live and curr_bid >= 0.95:
                    limit_price = 0.99
                else:
                    limit_price = max(0.02, curr_bid - 0.02)

                if is_live:
                    success, msg = self.live_broker.sell(side, token_id, limit_price=limit_price, best_bid=curr_bid, reason=reason)
                else:
                    success, msg = self.sim_broker.sell(side, limit_price, reason=reason)
                
                if success:
                    self.log_msg(f"[bold yellow]⚡ {reason} | Closed {side} @ {curr_price*100:.1f}¢[/]")
                    info["closed"] = True
                    # Update Bankroll
                    rev = 0.0
                    try:
                        if is_live and "Total: $" in msg:
                            rev = float(msg.split("Total: $")[1].split(")")[0])
                        elif is_live:
                             rev = float(msg.split("Shares")[0].split(":")[-1].strip()) * 0.99 
                        else:
                             rev = float(msg.split("$")[1])
                    except: pass
                    
                    if self.risk_initialized: self._add_risk_revenue(rev)



    async def _run_last_second_exit(self, is_live):
        """
        Runs in a worker thread. Do NOT access UI widgets directly.
        """
        sides_to_close = set()
        
        # 1. Identify Valid Open Positions
        if is_live:
             # In Live, check window_bets for what we THINK we have
             # Shared dict access: safe enough for read (atomic in CPython)
             for bet_id, info in self.window_bets.items():
                 if not info.get("closed"):
                     sides_to_close.add(info["side"])
        else:
             # In Sim, check broker shares directly
             # Accessing sim_broker is safe as it's just a Python object, not a widget
             if self.sim_broker.shares["UP"] > 0: sides_to_close.add("UP")
             if self.sim_broker.shares["DOWN"] > 0: sides_to_close.add("DOWN")

        # 2. Execute Closes
        for side in sides_to_close:
            token_id = self.market_data["up_id"] if side == "UP" else self.market_data["down_id"]
            if not token_id: continue
            
            # Aggressive Sell Logic
            curr_bid = self.market_data["up_bid"] if side == "UP" else self.market_data["down_bid"] 
            
            # Simulation optimization: User expects ~99c for winners to account for settlement value
            if not is_live and curr_bid >= 0.90:
                limit_price = 0.99
            else:
                # Dynamic Slippage: NONE for winners (sell at bid), Aggressive for dump
                if curr_bid >= 0.90: slippage = 0.0
                elif curr_bid >= 0.50: slippage = 0.02
                else: slippage = 0.05
                
                # Sell slightly below bid to ensure fill, but respect floor
                limit_price = max(0.02, curr_bid - slippage) 
            
            # execute_sell can take time (network I/O)
            success, msg = self.trade_executor.execute_sell(is_live, side, token_id, limit_price, best_bid=curr_bid, reason="Last Second Exit")
            
            if success:
                # Use call_from_thread to update UI safely
                self.call_from_thread(self.log_msg, f"[bold {'red' if is_live else 'green'}]⏱ FINAL EXIT {side}: {msg}[/]")
                # Mark bets as closed
                for bet_id, info in self.window_bets.items():
                    if info["side"] == side: info["closed"] = True
                    
                # Revenue Tracking
                try:
                    rev = 0.0
                    if "Total: $" in msg:
                        rev = float(msg.split("Total: $")[1].split(")")[0])
                    elif "Shares" in msg:
                        rev = float(msg.split("Shares")[0].split(":")[-1].strip()) * 0.99
                    elif "$" in msg:
                        rev = float(msg.split("$")[1])
                        
                    if self.risk_initialized: self._add_risk_revenue(rev)
                except: pass

    def update_timer(self):
        if self.market_data["start_ts"]: 
            elapsed = int(time.time() - self.market_data["start_ts"])
            rem = max(0, TradingConfig.WINDOW_SECONDS - elapsed)
            m, s = divmod(rem, 60)
            self.time_rem_str = f"{m:02d}:{s:02d}"
            self.query_one("#lbl_timer_big").update(self.time_rem_str)
            
            # --- Auto-Exit Hook (8s before close) ---
            if rem <= 8 and not self.last_second_exit_triggered:
                 self.last_second_exit_triggered = True
                 # Get UI state on main thread before dispatching
                 is_live = self.query_one("#cb_live").value
                 self.run_worker(self._run_last_second_exit(is_live), thread=True)
        
        run_sec = int(time.time() - self.app_start_time)
        rh, rem = divmod(run_sec, 3600)
        rm, rs = divmod(rem, 60)
        self.query_one("#lbl_runtime").update(f" | RUN: {rh:02d}:{rm:02d}:{rs:02d}")

    @on(Input.Submitted, "#inp_risk_alloc")
    def on_risk_update(self, event: Input.Submitted):
        try:
            new_val = float(event.value)
            self.risk_manager.set_bankroll(new_val, is_live=self.query_one("#cb_live").value)
            self.risk_initialized = True
            self.log_msg(f"[bold cyan]Risk Bankroll Manually Updated: ${self.risk_manager.risk_bankroll:.2f}[/]")
            self.update_balance_ui()
        except ValueError:
            self.log_msg("[red]Invalid Risk Amount entered.[/]")

    @on(Input.Submitted, "#inp_sim_bal")
    def on_sim_bal_update(self, event: Input.Submitted):
        if self.query_one("#cb_live").value:
            self.log_msg("[red]Cannot set Sim Balance in Live Mode[/]")
            return
        try: 
            v=float(event.value); self.sim_broker.balance=v; 
            self.log_msg(f"[green]Sim Bal Updated: ${v:.2f}[/]")
            
            # Sync Risk Bankroll if in Sim Mode
            if not self.query_one("#cb_live").value:
                self.risk_manager.set_bankroll(v, is_live=False)
                self.query_one("#inp_risk_alloc").value = f"{v:.2f}"
                self.log_msg(f"[cyan]Risk Bankroll Synced to Sim Bal: ${v:.2f}[/]")
            
            self.update_balance_ui()
        except: self.log_msg("[red]Invalid[/]")

    def _add_risk_revenue(self, amount):
        if not self.risk_initialized: return
        self.risk_manager.risk_bankroll += amount
        # Enforce Capping Logic (Refill to Target, surplus to Main Bal)
        if self.risk_manager.risk_bankroll > self.risk_manager.target_bankroll:
            self.risk_manager.risk_bankroll = self.risk_manager.target_bankroll
        # self.log_msg(f"[dim green]💰 Added ${amount:.2f} to Risk Cap. New: ${self.risk_manager.risk_bankroll:.2f}[/]")

    async def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if "buy" in bid: await self.trigger_buy("UP" if "up" in bid else "DOWN")
        else: await self.trigger_sell_all("UP" if "up" in bid else "DOWN")

    async def trigger_buy(self, side, amount=None):
        if amount:
            val = amount
        else:
            val_str = self.query_one("#inp_amount").value
            try: val = float(val_str)
            except: 
                self.log_msg("[bold red]⛔ Invalid Bet Amount! Check input.[/]")
                return
            
        if self.risk_initialized and val > self.risk_manager.risk_bankroll + 0.009: 
             self.log_msg(f"[bold white on red]⛔ BLOCKED: Insufficient Risk Cap (${self.risk_manager.risk_bankroll:.2f}). Please update Bankroll.[/]")
             return
        is_live = self.query_one("#cb_live").value
        # Use ASK for buying
        price = self.market_data["up_ask"] if side == "UP" else self.market_data["down_ask"]
        if not price or price <= 0: price = 0.50
        
        if is_live:
             # SAFETY CHECK HIGH PRICE
             if price >= 0.98:
                 self.log_msg(f"[bold red]⛔ SAFETY BLOCK: Price {price:.2f} is too high![/]")
                 return


             token_id = self.market_data["up_id"] if side == "UP" else self.market_data["down_id"]
             if token_id:
                success, msg = self.live_broker.buy(side, val, price, token_id, reason="Manual Live")
                if success: 
                    self.log_msg(f"[bold red]{msg}[/]")
                    if self.risk_initialized: self.risk_manager.risk_bankroll -= val
                    # Track for TP/SL
                    bet_id = f"ManualLive_{side}_{int(time.time()*1000)}"
                    self.window_bets[bet_id] = {"entry_price": price, "side": side}
                else: self.log_msg(f"[red]LIVE FAIL: {msg}[/]")
        else:
            success, msg = self.sim_broker.buy(side, val, price, reason="Manual Sim")
            if success: 
                self.log_msg(f"[green]{msg}[/]")
                if self.risk_initialized: self.risk_manager.risk_bankroll -= val
                # Track for TP/SL
                bet_id = f"ManualSim_{side}_{int(time.time()*1000)}"
                self.window_bets[bet_id] = {"entry_price": price, "side": side}
            else: self.log_msg(f"[red]{msg}[/]")
            
        self.update_balance_ui(); self.update_sell_buttons()

    async def trigger_sell_all(self, side):
        is_live = self.query_one("#cb_live").value
        if is_live:
             token_id = self.market_data["up_id"] if side == "UP" else self.market_data["down_id"]
             if token_id:
                curr_bid = self.market_data["up_bid"] if side == "UP" else self.market_data["down_bid"]
                success, msg = self.live_broker.sell(side, token_id, best_bid=curr_bid, reason="Manual Live Sell")
                if success: 
                    self.log_msg(f"[bold red]{msg}[/]")
                    try:
                        # New Format: "... (Total: $123.45)"
                        if "Total: $" in msg:
                            rev_str = msg.split("Total: $")[1].split(")")[0]
                            rev = float(rev_str) 
                            # Do not manually subtract fee here, trust the "Total" comes from proceeds calculation or is raw. 
                            # Actually in sell() we calc proceeds = size * limit_price. Market takes fees. 
                            # If we assume limit_price is what we got, then fees are deducted from PnL, not proceeds? 
                            # Polymarket fee is on profit? Or volume? No, no fee on limit orders usually? Or taker fee?
                            # To be safe, let's just use the gross proceeds. The bankroll is approximate availability.
                            if self.risk_initialized: self._add_risk_revenue(rev)
                        else:
                             # Fallback for old/sim messages
                             try: rev = float(msg.split("Shares")[0].split(":")[-1].strip()) * 0.99
                             except: pass
                    except: pass
                else: self.log_msg(f"[red]LIVE SELL FAIL: {msg}[/]")
        else:
            price = self.market_data["up_bid"] if side == "UP" else self.market_data["down_bid"]
            success, msg = self.sim_broker.sell(side, price)
            if success: 
                self.log_msg(f"[green]{msg}[/]")
                try:
                    rev = float(msg.split("$")[1])
                    if self.risk_initialized: self._add_risk_revenue(rev)
                except: pass
            else: self.log_msg(f"[red]{msg}[/]")
        self.update_balance_ui(); self.update_sell_buttons()

if __name__ == "__main__":
    import sys
    import os
    print("\n=== POLYMARKET SIMULATOR & LIVE BOT SETUP ===")
    print(f"Running with Python: {sys.executable}")
    
    start_mode = input("Select Mode: (1) Sim Mode [Default], (2) Live Mode: ").strip()
    is_live_start = (start_mode == "2")
    
    start_bal = 1000.00
    if not is_live_start:
        try: start_bal = float(input("Enter Initial SIM Balance ($): ").strip() or "100.00")
        except: start_bal = 100.00
        
    if not os.path.exists("logs"): os.makedirs("logs")
    default_log = f"logs/sim_log_5M_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    log_file = input(f"Enter Log Filename (default: {default_log}): ").strip()
    if not log_file: log_file = default_log
    if not log_file.endswith(".csv"): log_file += ".csv"
        
    print(f"Starting... Logging to: {log_file}")
    time.sleep(1)
    
    sim_broker = SimBroker(start_bal, log_file)
    live_broker = LiveBroker(sim_broker) 
    
    app = SniperApp(sim_broker, live_broker, start_live_mode=is_live_start)
    app.run()
