from .config import TradingConfig

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
    def analyze(self, history_objs, open_price, prev_window_color):
        if self.triggered_signal: return self.triggered_signal
        if not history_objs or not prev_window_color: return "NO_SIGNAL"
        early_prices = self.get_price_slice(history_objs, 0, TradingConfig.PHASE1_DURATION)
        if not early_prices: return "NO_SIGNAL"
        spike_high = max(early_prices)
        current_price = history_objs[-1]['price']
        if (spike_high > open_price) and (current_price < open_price):
            if prev_window_color == "RED": self.triggered_signal = f"BET_DOWN_FAKEOUT|Rejected Rescue & Trend Align"
            elif prev_window_color == "GREEN": self.triggered_signal = f"WAIT_FOR_CONFIRMATION|Rejected Rescue vs Trend"
            return self.triggered_signal
        return "NO_SIGNAL"

class MomentumScanner(BaseScanner):
    def __init__(self):
        super().__init__()
        self.mode = "TIME"      # "TIME", "PRICE", or "DURATION"
        self.threshold = 0.60   # For PRICE / DURATION mode (¢ / 100)
        self.base_threshold = 0.60 # Persistent base for adjustments
        self.duration = 10      # Seconds a side must stay above threshold (DURATION mode)
        self.last_skip_reason = None
        # Internal tracking for DURATION mode
        self._above_ts = {}     # {side: timestamp_first_seen_above}

    def reset(self):
        super().reset()
        self._above_ts = {}
        self.last_skip_reason = None

    def analyze(self, elapsed, up_bid, down_bid, atr_5m=None, trend_4h=None, atr_floor=25.0, trend_penalty_val=0.02, decisive_diff_val=0.02, odds_score=0.0):
        if self.triggered_signal: return self.triggered_signal
        # End-of-window safety guard: don't fire in last 20 seconds to avoid turnover noise
        if elapsed > 280: return "WAIT_EOW"

        # 1. Volatility Gate (Focus on Decisive Markets)
        if atr_5m is not None and atr_5m < atr_floor:
            self.last_skip_reason = f"Low Vol (<${atr_floor})"
            return "NONE"

        # 2. Trend Squeeze Logic (Protect against Bull Traps in Downtrends)
        # Requirement: To bet UP in a Strong DOWN trend, the UP side must lead by an extra bonus lead.
        up_penalty = trend_penalty_val if trend_4h == "S-DOWN" else 0.0

        # 3. Sentiment Guard (Don't fight the Tape)
        # If Odds Score is strong (>40), block momentum signals in the opposite direction.
        if odds_score > 40: # Strong Bullish
            if down_bid > (up_bid + 0.05): # Attempting to bet DOWN
                self.last_skip_reason = f"Sentiment Guard: Fighting Bullish Odds ({odds_score:.1f})"
                return "SKIP_SENTIMENT"
        elif odds_score < -40: # Strong Bearish
            if up_bid > (down_bid + 0.05): # Attempting to bet UP
                self.last_skip_reason = f"Sentiment Guard: Fighting Bearish Odds ({odds_score:.1f})"
                return "SKIP_SENTIMENT"

        if self.mode == "PRICE":
            if up_bid >= (self.threshold + up_penalty):
                self.triggered_signal = f"BET_UP_MOM|Price Threshold HIT: UP {up_bid*100:.1f}¢"
                return self.triggered_signal
            if down_bid >= self.threshold:
                self.triggered_signal = f"BET_DOWN_MOM|Price Threshold HIT: DOWN {down_bid*100:.1f}¢"
                return self.triggered_signal
            return "WAIT_PRICE"

        elif self.mode == "DURATION":
            import time as _time
            now = _time.time()
            for side, bid in (("UP", up_bid), ("DOWN", down_bid)):
                thresh = self.threshold
                if side == "UP": thresh += up_penalty
                
                if bid >= thresh:
                    if side not in self._above_ts:
                        self._above_ts[side] = now
                    elif now - self._above_ts[side] >= self.duration:
                        self.triggered_signal = f"BET_{side}_MOM|Duration {self.duration}s above {thresh*100:.0f}¢ HIT"
                        return self.triggered_signal
                else:
                    # Reset timer if it drops below threshold
                    self._above_ts.pop(side, None)
            return "WAIT_DUR"

        else:  # TIME mode (default)
            if elapsed < 10: return "WAIT_TIME"
            
            # 4. Decisive Lead Rule (Filter out coin-flips)
            # If at 10s mark the spread is < decisive_diff_val, wait for a clearer lead (up to 20s)
            bid_diff = abs(up_bid - down_bid)
            if elapsed < 20 and bid_diff < decisive_diff_val:
                return "WAIT_DECISIVE"
            
            if up_bid > (down_bid + up_penalty):
                self.triggered_signal = f"BET_UP_MOM|Leader @ {elapsed}s: UP {up_bid*100:.1f}¢"
                return self.triggered_signal
            elif down_bid > up_bid:
                self.triggered_signal = f"BET_DOWN_MOM|Leader @ {elapsed}s: DOWN {down_bid*100:.1f}¢"
                return self.triggered_signal
            return "WAIT_TIE"

class RsiScanner(BaseScanner):
    def analyze(self, rsi, price, bb_lower, time_remaining):
        if self.triggered_signal: return self.triggered_signal
        if rsi < 15 and price < bb_lower and time_remaining > 100:
            self.triggered_signal = f"BET_UP_RSI_OVERSOLD|RSI {rsi:.1f} + Below BB"
            return self.triggered_signal
        return "WAIT"

class TrapCandleScanner(BaseScanner):
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
    def analyze(self, price_history, open_price, elapsed, trend_4h):
        if self.triggered_signal: return self.triggered_signal
        if not price_history: return "WAIT"
        if trend_4h == "UP": return "WAIT_TREND_MISMATCH"
        if elapsed < 100: return "WAIT_TIME"
        crossed_up = any(x['price'] > open_price for x in price_history if 100 <= x['elapsed'] <= 200)
        green_ticks = sum(1 for x in price_history if x['price'] > open_price and 100 <= x['elapsed'] <= 200)
        if crossed_up and green_ticks < 20 and price_history[-1]['price'] < open_price and elapsed > 200:
             self.triggered_signal = "BET_DOWN_FAILED_RESCUE|Bulls failed to hold green"
             return self.triggered_signal
        return "WAIT"

class LateReversalScanner(BaseScanner):
    def analyze(self, price_history, open_price, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if not price_history: return "WAIT"
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
    def __init__(self):
        super().__init__()
        self.max_price = 80.0  # Default max price threshold
        self.volume_confirm = False  # Default volume confirmation off
        self.entry_timing = "AGGRESSIVE"  # Default aggressive entry
        self.pullback = False  # Default pullback detection off
        self.tolerance_pct = 0.1  # Default tolerance 10%
        self.atr_multiplier = 1.5  # Default ATR multiplier
        self.research_enabled = False  # Research logging off by default
        self.research_logger = None  # Research logger instance
        self.entry_price = None  # Track entry price for research logging
        self.step_times = []  # Track timestamps of pivot lows
        self.last_interval = None
        
    def analyze(self, close_prices, atr_5m=None):
        if self.triggered_signal: return self.triggered_signal
        if len(close_prices) < 20: return "WAIT_DATA"
        
        # Check max price threshold
        current_price = close_prices[-1]
        if current_price > self.max_price:
            return f"SKIP|Price {current_price*100:.1f}c > Max {self.max_price}c"
        
        window = close_prices[-15:]
        # Identify pivot lows (indices in window)
        low_indices = [i for i in range(1, len(window) - 1) if window[i] <= window[i-1] and window[i] <= window[i+1]]
        lows = [window[i] for i in low_indices]

        if len(lows) < 3: return "WAIT_PATTERN"
        
        # Verify Staircase (Rising Lows)
        if all(lows[i] < lows[i+1] for i in range(len(lows)-1)):
            # --- New: Step Velocity Logic ---
            if len(low_indices) >= 3:
                # Calculate intervals between steps (in terms of window ticks)
                intervals = [low_indices[i+1] - low_indices[i] for i in range(len(low_indices)-1)]
                if len(intervals) >= 2:
                    current_interval = intervals[-1]
                    prev_interval = intervals[-2]
                    if current_interval > 1.5 * prev_interval:
                        return "WAIT_EXHAUSTED|Steps slowing down (>1.5x interval)"
            
            recent_high = max(window)
            
            # --- New: ATR-Relative Tolerance ---
            base_tolerance = TradingConfig.TOLERANCE_PCT
            if atr_5m is not None and atr_5m > 0:
                # scale tolerance based on ATR relative to a "normal" $10 ATR
                atr_scaler = max(0.5, min(2.0, atr_5m / 10.0))
                adjusted_tolerance = base_tolerance * self.atr_multiplier * atr_scaler
            else:
                adjusted_tolerance = base_tolerance * self.atr_multiplier
            
            if (recent_high - min(window)) > (min(window) * adjusted_tolerance):
                if self.pullback:
                    # Wait for pullback before entering
                    if window[-1] < (recent_high * 0.995):
                        self.triggered_signal = "BET_UP_AGGRESSIVE|Staircase Breakout Confirmed (Pullback)"
                        self.entry_price = current_price  # Store for research logging
                        return self.triggered_signal
                    else:
                        return "WAIT_PULLBACK"
                elif self.entry_timing == "CONSERVATIVE":
                    # Conservative entry - wait for confirmation
                    if window[-1] >= (recent_high * 0.999):
                        self.triggered_signal = "BET_UP_CONSERVATIVE|Staircase Breakout Confirmed"
                        self.entry_price = current_price  # Store for research logging
                        return self.triggered_signal
                    else:
                        return "WAIT_CONSERVATIVE"
                else:
                    # Aggressive entry - original logic
                    if window[-1] >= (recent_high * 0.9995):
                        self.triggered_signal = "BET_UP_AGGRESSIVE|Staircase Breakout Confirmed"
                        self.entry_price = current_price  # Store for research logging
                        return self.triggered_signal
        return "WAIT"
    
    def log_research_trade(self, exit_price, result, window_id, rsi_1m, btc_velocity, atr_5m):
        """Log trade to research file if enabled."""
        if self.research_enabled and self.research_logger and self.entry_price:
            settings = {
                "max_price": self.max_price,
                "volume_confirm": self.volume_confirm,
                "entry_timing": self.entry_timing,
                "pullback": self.pullback,
                "tolerance_pct": self.tolerance_pct,
                "atr_multiplier": self.atr_multiplier,
                "research_enabled": self.research_enabled
            }
            
            side = "UP" if "UP" in self.triggered_signal else "DOWN"
            self.research_logger.log_trade(
                settings, self.entry_price, exit_price, side, 
                result, window_id, rsi_1m, btc_velocity, atr_5m
            )

class PostPumpScanner(BaseScanner):
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
    def analyze(self, close_prices):
        if self.triggered_signal: return self.triggered_signal
        if len(close_prices) < 20: return "WAIT"
        ma20 = sum(close_prices[-20:]) / 20
        if abs(close_prices[-1] - ma20) < (close_prices[-1] * 0.0015) and close_prices[-1] > ma20:
             self.triggered_signal = "SNIPER_ENTRY_UP|Perfect touch of MA20"
             return self.triggered_signal
        return "WAIT"

class SlingshotScanner(BaseScanner):
    def analyze(self, close_prices):
        if self.triggered_signal: return self.triggered_signal
        if len(close_prices) < 10: return "WAIT"
        ma = sum(close_prices[-20:]) / 20
        if close_prices[-1] > ma and (close_prices[-2] < ma or close_prices[-3] < ma):
             self.triggered_signal = "MAX_BET_UP_RECLAIM|Reclaimed MA20"
             return self.triggered_signal
        if close_prices[-1] < ma and (close_prices[-2] > ma or close_prices[-3] > ma):
             self.triggered_signal = "MAX_BET_DOWN_BREAKDOWN|Lost MA20 Support"
             return self.triggered_signal
        return "WAIT"

class MinOneScanner(BaseScanner):
    def analyze(self, price_history, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if elapsed < 60 or elapsed > 130: return "WAIT"
        min1 = self.get_price_slice(price_history, 0, TradingConfig.PHASE1_DURATION)
        if not min1: return "WAIT"
        h = max(min1); l = min(min1)
        c = min1[-1]; o = min1[0]; body = abs(c - o)
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
    def analyze(self, closes_60m, current_price, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if elapsed > 180 or len(closes_60m) < 20: return "WAIT"
        slice_ = closes_60m[-20:]; sma = sum(slice_) / 20
        std = (sum((x - sma) ** 2 for x in slice_) / 20) ** 0.5
        if current_price > (sma + 2*std): self.triggered_signal = "BET_UP_COBRA|Explosive breakout"; return self.triggered_signal
        if current_price < (sma - 2*std): self.triggered_signal = "BET_DOWN_COBRA|Explosive breakdown"; return self.triggered_signal
        return "WAIT"

class CoiledCobraScanner(BaseScanner):
    def __init__(self):
        super().__init__()
        self.vol_history = []  # Track 20-period StdDev over the window
        
        # Adjustable parameters
        self.coil_threshold_pct = 0.25
        self.coil_lookback_history = 60
        self.coil_lookback_recent = 10
        
    def analyze(self, closes_60m, current_price, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if len(closes_60m) < 40: return "WAIT_DATA"
        
        # 1. Calculate Standard Deviation for the "Coiled" check
        slice_ = closes_60m[-20:]
        sma = sum(slice_) / 20
        std = (sum((x-sma)**2 for x in slice_) / 20) ** 0.5
        self.vol_history.append(std)
        
        # 2. Check for "Coiled" state
        # (StdDev in bottom X% of history, requiring at least Y samples for validity)
        if len(self.vol_history) < self.coil_lookback_history: return "WAIT_COIL_DATA"
        
        sorted_vol = sorted(self.vol_history)
        threshold = sorted_vol[int(len(sorted_vol) * self.coil_threshold_pct)]
        is_coiled = std <= threshold
        
        # We look back Z seconds for the "Coil" if we are currently breaking out
        was_recently_coiled = any(v <= threshold for v in self.vol_history[-self.coil_lookback_recent:])
        
        
        # 3. MA20 Reclaim/Bollinger Expansion Logic
        # Reclaim check (Slingshot style)
        reclaimed_up = current_price > sma and any(p < sma for p in closes_60m[-3:-1])
        reclaimed_down = current_price < sma and any(p > sma for p in closes_60m[-3:-1])
        
        # Bollinger Breakout check
        upper_bb = sma + (2 * std)
        lower_bb = sma - (2 * std)
        
        if was_recently_coiled:
            if reclaimed_up and current_price >= upper_bb:
                self.triggered_signal = "BET_UP_CCO|Coiled Cobra Breakout"
                return self.triggered_signal
            if reclaimed_down and current_price <= lower_bb:
                self.triggered_signal = "BET_DOWN_CCO|Coiled Cobra Breakdown"
                return self.triggered_signal
                
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
        if not price_history: return "WAIT"
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
    def analyze(self, price_history, fast_bb, trend_4h):
        if self.triggered_signal: return self.triggered_signal
        if trend_4h == "UP": return "WAIT_TREND_MISMATCH"
        if not fast_bb or len(price_history) < 20: return "WAIT"
        upper_band = fast_bb[0]; current_price = price_history[-1]['price']
        recent_prices = [p['price'] for p in price_history]
        if not recent_prices: return "WAIT"
        last_20 = recent_prices[-20:]
        if any(p > upper_band for p in last_20) and current_price < upper_band:
            peak_price = max(last_20)
            if (peak_price - current_price) / peak_price > 0.0005:
                self.triggered_signal = f"SHORT_THE_SNAP|Rejection from Top"; return self.triggered_signal
        return "WAIT"

class GrindSnapScanner(BaseScanner):
    def analyze(self, price_history, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if not price_history: return "WAIT"
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
        # 3-Point Time Remaining and Min Diff Curve
        self.bet_size = 2.0
        self.t1 = 290; self.d1 = 2000.0
        self.t2 = 80; self.d2 = 80.0
        self.t3 = 15;  self.d3 = 25.0
        
    def reset(self): super().reset(); self.checkpoints = {}
    
    def analyze(self, elapsed, price, open_price, trend_4h, up_p, down_p):
        if self.triggered_signal: return self.triggered_signal
        
        time_rem = 300 - elapsed
        
        # Check if we have a valid 3-point sequence defined
        has_curve = (self.t1 > 0 or self.t2 > 0 or self.t3 > 0)
        
        if has_curve:
            # Block if time remaining is outside the outer boundaries (t1 to t3)
            # Assuming standard input where t1 is highest, t3 is lowest remaining time
            if time_rem > max(self.t1, self.t2, self.t3) or time_rem < min(self.t1, self.t2, self.t3):
                return "WAIT"
                
            required_diff = 0.0
            
            # Phase 1: Between T1 and T2
            if time_rem <= self.t1 and time_rem >= self.t2 and self.t1 > self.t2:
                window_duration = self.t1 - self.t2
                progress = (self.t1 - time_rem) / window_duration
                required_diff = self.d1 + ((self.d2 - self.d1) * progress)
                
            # Phase 2: Between T2 and T3
            elif time_rem <= self.t2 and time_rem >= self.t3 and self.t2 > self.t3:
                window_duration = self.t2 - self.t3
                progress = (self.t2 - time_rem) / window_duration
                required_diff = self.d2 + ((self.d3 - self.d2) * progress)
                
            # Ensure price difference meets the interpolated curve calculation
            actual_diff = abs(price - open_price)
            if actual_diff < required_diff:
                return "WAIT"
        # Ensure actual_diff is calculated for logging
        actual_diff = abs(price - open_price)
        
        # User Request: Buy when a side reaches >= 86 cents (Target Lim $0.90)
        # Removed the artificial ceiling to prevent missing massive spikes
        if 0.86 <= up_p < 1.0:
            self.triggered_signal = f"BET_UP_MOSHE_90|High Probability Win (BTC Diff: ${actual_diff:.2f})"
            return self.triggered_signal
            
        if 0.86 <= down_p < 1.0:
            self.triggered_signal = f"BET_DOWN_MOSHE_90|High Probability Win (BTC Diff: ${actual_diff:.2f})"
            return self.triggered_signal

        return "WAIT"

class ZScoreBreakoutScanner(BaseScanner):
    def analyze(self, price_history, open_price, elapsed):
        if self.triggered_signal: return self.triggered_signal
        if not price_history: return "WAIT"
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

ALGO_INFO = {
    "NPA": {"name": "N-Pattern", "desc": "Detects impulse moves followed by a retracement support and subsequent breakout of the new high."},
    "FAK": {"name": "Fakeout", "desc": "Spots rejected 'rescue' attempts where price spikes above open but fails and sinks back below."},
    "MOM": {"name": "Momentum", "desc": "Dual Mode: TIME (Default 10s lead) or PRICE (Threshold trigger 51-70¢)."},
    "RSI": {"name": "RSI Oversold", "desc": "Standard RSI < 15 check combined with a Bollinger Band lower-touch for extreme reversals."},
    "TRA": {"name": "Trap Candle", "desc": "Fades aggressive breakouts that get >75% retraced within the same 5-minute window."},
    "MID": {"name": "Mid-Game", "desc": "Identifies bulls failing to hold green in the middle of the round, leading to a 'Failed Rescue' drop."},
    "LAT": {"name": "Late Reversal", "desc": "Spots late-window surges that cross from red to green after an early-window drop was established."},
    "STA": {"name": "Staircase", "desc": "Detects orderly, rising lows (steps) followed by an aggressive breakout of the local high."},
    "POS": {"name": "Post-Pump", "desc": "Mean reversion logic that trades the fade after a massive, single-bar pump or dump."},
    "STE": {"name": "Step Climber", "desc": "The 'Sniper Entry' - looks for a perfect touch of the 20-period Moving Average from above."},
    "SLI": {"name": "Slingshot", "desc": "Triggers on the reclaim (UP) or breakdown (DOWN) of the 20-period Moving Average line."},
    "MIN": {"name": "Min-One", "desc": "Checks the 1-minute candle for 'Long Wicks' (2x body size) to detect deceptive exhaustion."},
    "LIQ": {"name": "Liq Vacuum", "desc": "Sweeps a previous swing low to grab liquidity before reversing aggressively."},
    "COB": {"name": "Cobra Break", "desc": "Detects explosive, high-volatility breakouts outside the 2-Sigma Bollinger Bands."},
    "CCO": {"name": "Coiled Cobra", "desc": "Refined Vol-Crossover: MA20 reclaim following a low-volatility 'coiled' phase."},
    "MES": {"name": "Mesa Collapse", "desc": "Spots a flat/choppy distribution top ('Mesa') that unexpectedly collapses below its floor."},
    "MEA": {"name": "Mean Reversion", "desc": "Standard rejection from the upper/lower 20-period Bollinger Bands toward the mean."},
    "GRI": {"name": "Grind-Snap", "desc": "Detects a tight, 2-minute 'grind' phase followed by a sharp impulse snap in either direction."},
    "VOL": {"name": "Vol-Check", "desc": "Calculates if the move distance is greater than the average 3-minute range to ensure volatility exists."},
    "MOS": {"name": "Moshe Sniper", "desc": "Surge detection based on 30-second price checkpoints and 4H macro trend alignment."},
    "ZSC": {"name": "Z-Score", "desc": "Statistical breakout scanner triggering when price deviates >3.5 Standard Deviations from the window mean."}
}
