from .config import TradingConfig

class BaseScanner:
    def __init__(self, config: TradingConfig = None):
        self.config = config
        self.triggered_signal = None
        
    def reset(self):
        self.triggered_signal = None
        
    def get_price_slice(self, history, start_elapsed, end_elapsed):
        if not history: return []
        return [p['price'] for p in history if start_elapsed <= p['elapsed'] <= end_elapsed]
        
    def get_signal(self, context: dict) -> str:
        """
        Unified interface for all algorithms.
        Returns a string instruction: "WAIT", "BUY_UP", "BUY_DOWN", "PRE_BUY_UP", etc.
        """
        return "WAIT"

class NPatternScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None, min_impulse_size=0.0003, max_retrace_depth=0.85):
        super().__init__(config)
        self.min_impulse_size = min_impulse_size
        self.max_retrace_depth = max_retrace_depth
        self.support_tolerance = self.config.TOLERANCE_PCT if self.config else 0.002
        
    def get_signal(self, context: dict):
        if self.triggered_signal and "BET_" in self.triggered_signal:
            return self.triggered_signal
            
        history_objs = context.get("history_objs", [])
        open_price = context.get("open_price", 0.5)
        
        if not history_objs: return "WAIT"
        phase1_dur = self.config.PHASE1_DURATION if self.config else 60
        phase1_prices = self.get_price_slice(history_objs, 0, phase1_dur)
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
    def __init__(self, config: TradingConfig = None, phase1_duration=60):
        super().__init__(config)
        self.phase1_duration = phase1_duration

    def get_signal(self, context: dict):
        if self.triggered_signal: return self.triggered_signal
        
        history_objs = context.get("history_objs", [])
        open_price = context.get("open_price", 0.5)
        prev_window_color = context.get("prev_window_color", None)
        
        if not history_objs or not prev_window_color: return "NO_SIGNAL"
        early_prices = self.get_price_slice(history_objs, 0, self.phase1_duration)
        if not early_prices: return "NO_SIGNAL"
        spike_high = max(early_prices)
        current_price = history_objs[-1]['price']
        if (spike_high > open_price) and (current_price < open_price):
            if prev_window_color == "RED": self.triggered_signal = f"BET_DOWN_FAKEOUT|Rejected Rescue & Trend Align"
            elif prev_window_color == "GREEN": self.triggered_signal = f"WAIT_FOR_CONFIRMATION|Rejected Rescue vs Trend"
            return self.triggered_signal
        return "NO_SIGNAL"

class MomentumScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None):
        super().__init__(config)
        self.mode = "TIME"      # "TIME", "PRICE", or "DURATION"
        self.buy_mode = "STD"   # "STD", "PRE", "HYBRID", "ADV"
        self.threshold = 0.60   # For PRICE / DURATION mode (¢ / 100)
        self.base_threshold = 0.60 # Persistent base for adjustments
        self.duration = 10      # Seconds a side must stay above threshold (DURATION mode)
        self.last_skip_reason = None
        self.pre_buy_triggered = False
        
        # Advanced Volatility & ATR Logic defaults
        self.adv_settings = {
            "atr_low": 20, "atr_high": 40,
            "stable_offset": -5, "chaos_offset": 10,
            "auto_stn_chaos": True, "auto_pbn_stable": False,
            "shield_time": 45, "shield_reach": 5,
            "atr_floor": 25.0, "trend_penalty": 0.02, "decisive_diff": 0.02
        }
        
        # Internal tracking for DURATION mode
        self._above_ts = {}     # {side: timestamp_first_seen_above}
        self.pbn_analysis = None  # Store detailed PBN analysis results

    def reset(self):
        super().reset()
        self._above_ts = {}
        self.last_skip_reason = None
        self.pre_buy_triggered = False
        self.pbn_analysis = None

    def get_signal(self, context: dict) -> str:
        self.last_skip_reason = None # Reset state for new tick
        if self.triggered_signal: return self.triggered_signal
        
        # Extract variables from context
        elapsed = context.get("elapsed", 0)
        up_bid = context.get("up_bid", 0.5)
        down_bid = context.get("down_bid", 0.5)
        up_ask = context.get("up_ask", 0.5)
        down_ask = context.get("down_ask", 0.5)
        atr_5m = context.get("atr_5m", 0)
        trend_1h = context.get("trend_1h", "NEUTRAL")
        trend_1h = context.get("trend_1h", "NEUTRAL")
        odds_score = context.get("odds_score", 0.0)
        rsi_1m = context.get("rsi_1m", 50)
        velocity = context.get("velocity", 0)
        window_analytics = context.get("window_analytics", {})
        
        atr_floor = self.adv_settings.get("atr_floor", 25.0)
        trend_penalty_val = self.adv_settings.get("trend_penalty", 0.02)
        decisive_diff_val = self.adv_settings.get("decisive_diff", 0.02)

        # -------------------------------------------------------------
        # STAGE 0: Pre-Buy Logic (Executed at T-15s instead of inside engine)
        # -------------------------------------------------------------
        window_seconds = context.get("window_seconds", 300)
        if elapsed >= (window_seconds - 15) and not self.pre_buy_triggered and self.buy_mode in ["PRE", "HYBRID", "ADV"]:
            # ADV Logic Override
            effective_mode = self.buy_mode
            if self.buy_mode == "ADV":
                if atr_5m >= self.adv_settings.get("atr_high", 40) and self.adv_settings.get("auto_stn_chaos", False):
                    effective_mode = "STD"
            
            # ALWAYS run analysis for PBN mode - execute regardless of ATR floor
            analysis_only = False
            if self.buy_mode == "ADV" and effective_mode == "STD":
                self.last_skip_reason = "ADV overrode to STD (high ATR chaos) - PBN blocked"
                analysis_only = True
                # self.pre_buy_triggered = True # DON'T LATCH YET, let analysis populate
            
            # For PRE and HYBRID modes, always execute based on analysis (no ATR floor blocking)
            
            # Pre-Buy Analysis with Multi-Factor Reasoning (ALWAYS RUN for PBN visibility)
            btc_price = context.get("btc_price", 0)
            btc_open = context.get("btc_open", 0)
            btc_diff = btc_price - btc_open
            btc_range = context.get("btc_dyn_rng", 0)
            up_bid = context.get("up_bid", up_ask)
            down_bid = context.get("down_bid", down_ask)
            odds_score = context.get("odds_score", 0)
            trend_1h = context.get("trend_1h", "NEUTRAL")
            rsi_1m = context.get("rsi_1m", 50)
                
                # Determine ATR tier
            atr_low = self.adv_settings.get("atr_low", 20)
            atr_high = self.adv_settings.get("atr_high", 40)
            tier = "CHAOS" if atr_5m >= atr_high else "STABLE" if atr_5m <= atr_low else "NEUTRAL"
            tier_color = "[red]" if tier == "CHAOS" else "[green]" if tier == "STABLE" else "[yellow]"
            offset = self.adv_settings.get("chaos_offset", 10) if tier == "CHAOS" else self.adv_settings.get("stable_offset", -5) if tier == "STABLE" else 0
            
            # Calculate price imbalance
            price_imbalance = (up_ask - down_ask) * 100
            
            factors = []
            up_score = 0
            down_score = 0
            
            # 1. Trend Analysis
            if trend_1h in ["S-UP", "M-UP", "W-UP"]:
                up_score += 2
                factors.append(f"Trend 1H: [green]BULLISH[/] ({trend_1h}) [+2]")
            elif trend_1h in ["S-DOWN", "M-DOWN", "W-DOWN"]:
                down_score += 2
                factors.append(f"Trend 1H: [red]BEARISH[/] ({trend_1h}) [+2]")
            else:
                factors.append(f"Trend 1H: [yellow]NEUTRAL[/] ({trend_1h}) [0]")
            
            # 2. BTC Movement Analysis
            if abs(btc_diff) > 50:
                if btc_diff > 0:
                    up_score += 1
                    factors.append(f"BTC Move: [green]+${btc_diff:.0f}[/] [+1]")
                else:
                    down_score += 1
                    factors.append(f"BTC Move: [red]${btc_diff:.0f}[/] [+1]")
            else:
                factors.append(f"BTC Move: [yellow]${btc_diff:.0f}[/] [0]")
            
            # 3. RSI Analysis
            if rsi_1m > 70:
                down_score += 1
                factors.append(f"RSI 1m: [red]{rsi_1m:.0f} (Overbought)[/] [+1]")
            elif rsi_1m < 30:
                up_score += 1
                factors.append(f"RSI 1m: [green]{rsi_1m:.0f} (Oversold)[/] [+1]")
            else:
                factors.append(f"RSI 1m: [yellow]{rsi_1m:.0f} (Neutral)[/] [0]")
            
            # 4. Polymarket Odds Analysis
            if abs(odds_score) > 5:
                if odds_score > 0:
                    up_score += 1
                    factors.append(f"Odds Score: [green]+{odds_score:.1f}¢[/] (UP favored) [+1]")
                else:
                    down_score += 1
                    factors.append(f"Odds Score: [red]{odds_score:.1f}¢[/] (DN favored) [+1]")
            else:
                factors.append(f"Odds Score: [yellow]{odds_score:.1f}¢[/] (Balanced) [0]")
            
            # 5. Price Imbalance Analysis
            if abs(price_imbalance) > 2:
                if price_imbalance > 0:
                    down_score += 1
                    factors.append(f"Ask Spread: [red]+{price_imbalance:.1f}¢[/] (UP premium) [+1 DN]")
                else:
                    up_score += 1
                    factors.append(f"Ask Spread: [green]+{price_imbalance:.1f}¢[/] (DN premium) [+1 UP]")
            else:
                factors.append(f"Ask Spread: [yellow]{price_imbalance:.1f}¢[/] (Balanced) [0]")
            
            # 6. ATR Tier Adjustment
            factors.append(f"ATR Tier: {tier_color}{tier}[/] (ATR={atr_5m:.1f}) [Offset: {offset:+}¢]")
            
            # 7. Volatility Analysis
            if btc_range > 100:
                factors.append(f"Volatility: [red]HIGH[/] (${btc_range:.0f} range) [Caution]")
            elif btc_range > 50:
                factors.append(f"Volatility: [yellow]MODERATE[/] (${btc_range:.0f} range)")
            else:
                factors.append(f"Volatility: [green]LOW[/] (${btc_range:.0f} range)")
            
            # Calculate final recommendation for LOGGING ONLY
            net_score = up_score - down_score
            if net_score > 0:
                log_side = "UP"
                confidence = "STRONG" if net_score >= 3 else "MODERATE" if net_score >= 2 else "WEAK"
            elif net_score < 0:
                log_side = "DOWN"
                confidence = "STRONG" if net_score <= -3 else "MODERATE" if net_score <= -2 else "WEAK"
            else:
                log_side = None
                confidence = "NONE"
                
            if log_side:
                reason = f"PBN Analysis: {confidence} {log_side} (Score: {net_score:+d})"
            else:
                reason = f"PBN Analysis: INDECISIVE (Score: {net_score:+d}) | Completely Tied"
            
            # Log detailed analysis (this will be captured and displayed)
            self.pbn_analysis = {
                "factors": factors,
                "up_score": up_score,
                "down_score": down_score,
                "net_score": net_score,
                "decision": log_side,
                "confidence": confidence,
                "reason": reason
            }

            if analysis_only:
                self.pre_buy_triggered = True # Latch now
                return "WAIT_PBN_ANALYSIS_ONLY"

            # -------------------------------------------------------------
            # EXPLICIT OVERRIDE: PBN EXECUTIONS MUST FAVOR HIGHER ASK PRICE
            # -------------------------------------------------------------
            if up_ask > down_ask:
                exec_side = "UP"
            elif down_ask > up_ask:
                exec_side = "DOWN"
            else: # Exactly tied
                exec_side = "UP" if "UP" in trend_1h else "DOWN"
                
            exec_reason = f"{exec_side} Ask ({locals().get(exec_side.lower() + '_ask', 0)*100:.1f}¢) > Opposing. {reason}"
            if up_ask == down_ask: 
                exec_reason = f"Tied Asks ({up_ask*100:.1f}¢) -> Forced 1H Trend ({trend_1h}). {reason}"

            self.pre_buy_triggered = True # Latch on successful decision
            self.triggered_signal = f"PRE_BUY_{exec_side}|{exec_reason}"
            return self.triggered_signal

        if elapsed > (window_seconds - 20): return "WAIT_EOW"

        # 1. Volatility Gate (Focus on Decisive Markets)
        if atr_5m is not None and atr_5m < atr_floor:
            self.last_skip_reason = f"Low Vol (<${atr_floor})"
            return "NONE"

        # 2. Trend Squeeze Logic (Protect against Bull Traps in Downtrends)
        # Requirement: To bet UP in a Strong DOWN trend, the UP side must lead by an extra bonus lead.
        up_penalty = trend_penalty_val if trend_1h == "S-DOWN" else 0.0

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

class Momentum2Scanner(BaseScanner):
    """
    MOM-2: Redesigned Momentum Scanner with Unified Scoring Intelligence.
    Consolidates TIME, PRICE, and PBN into a single weighted scoring engine.
    """
    def __init__(self, config: TradingConfig = None):
        super().__init__(config)
        self.mode = "VECTOR" # Default mode
        self.buy_mode = "STD"
        self.threshold = 0.60
        self.base_threshold = 0.60
        self.duration = 10     # Missing attribute fix
        self.last_skip_reason = None
        self.adv_settings = {
            "atr_low": 20, "atr_high": 40,
            "stable_offset": -5, "chaos_offset": 10,
            "auto_stn_chaos": True, "auto_pbn_stable": False,
            "shield_time": 45, "shield_reach": 5,
            "atr_floor": 25.0, "trend_penalty": 0.02, "decisive_diff": 0.02
        }
        self.pre_buy_triggered = False
        self.triggered_signal = None
        self.pbn_analysis = None
        self._above_ts = {}

    def reset(self):
        super().reset()
        self.pre_buy_triggered = False
        self.triggered_signal = None
        self.pbn_analysis = None
        self._above_ts = {}

    def get_signal(self, context: dict) -> str:
        self.last_skip_reason = None
        if self.triggered_signal: return self.triggered_signal

        # Extract context
        elapsed = context.get("elapsed", 0)
        up_bid = context.get("up_bid", 0.5)
        down_bid = context.get("down_bid", 0.5)
        up_ask = context.get("up_ask", 0.5)
        down_ask = context.get("down_ask", 0.5)
        atr_5m = context.get("atr_5m", 0)
        trend_1h = context.get("trend_1h", "NEUTRAL")
        rsi_1m = context.get("rsi_1m", 50)
        velocity = context.get("velocity", 0)
        odds_score = context.get("odds_score", 0)
        
        # ADV Settings
        atr_floor = self.adv_settings.get("atr_floor", 25.0)
        
        window_seconds = context.get("window_seconds", 300)
        if atr_5m is not None and atr_5m < atr_floor:
            self.last_skip_reason = f"Low Vol (<${atr_floor})"
            return "NONE"
            
        if elapsed > (window_seconds - 20) and self.buy_mode == "STD":
            return "WAIT_EOW"

        # 🔴 MODE SELECTION
        if self.mode == "PRICE":
            if up_bid >= self.threshold:
                self.triggered_signal = f"BET_UP_MM2|Price Threshold HIT: UP {up_bid*100:.1f}¢"
                return self.triggered_signal
            if down_bid >= self.threshold:
                self.triggered_signal = f"BET_DOWN_MM2|Price Threshold HIT: DOWN {down_bid*100:.1f}¢"
                return self.triggered_signal
            return f"WAIT_PRICE_MM2 ({self.threshold*100:.0f}¢)"

        elif self.mode == "DURATION":
            import time as _time
            now = _time.time()
            for side, bid in (("UP", up_bid), ("DOWN", down_bid)):
                if bid >= self.threshold:
                    if side not in self._above_ts:
                        self._above_ts[side] = now
                    elif now - self._above_ts[side] >= self.duration:
                        self.triggered_signal = f"BET_{side}_MM2|Duration {self.duration}s above {self.threshold*100:.0f}¢ HIT"
                        return self.triggered_signal
                else:
                    self._above_ts.pop(side, None)
            return f"WAIT_DUR_MM2 ({self.duration}s)"

        elif self.mode == "TIME":
            if elapsed < self.duration: return f"WAIT_TIME_MM2 ({elapsed}/{self.duration}s)"
            if up_bid > down_bid:
                self.triggered_signal = f"BET_UP_MM2|Leader @ {elapsed}s: UP {up_bid*100:.1f}¢"
                return self.triggered_signal
            elif down_bid > up_bid:
                self.triggered_signal = f"BET_DOWN_MM2|Leader @ {elapsed}s: DOWN {down_bid*100:.1f}¢"
                return self.triggered_signal
            return "WAIT_TIE_MM2"

        # 🟢 VECTOR SCORING ENGINE (Default)
        up_score = 0
        down_score = 0
        factors = []
        
        # 1. Price Lead Factor
        spread = (up_bid - down_bid) * 100
        decisive_min = self.adv_settings.get("decisive_diff", 0.02) * 100
        
        if abs(spread) >= decisive_min:
            if spread > 0:
                up_score += 2
                factors.append(f"Price Lead: UP +{spread:.1f}¢ [+2]")
            else:
                down_score += 2
                factors.append(f"Price Lead: DOWN +{abs(spread):.1f}¢ [+2]")
        else:
            factors.append(f"Price Lead: Neutral ({spread:.1f}¢)")

        # 2. BTC Velocity Factor
        # Weight increases as window ends
        vel_weight = 2 if elapsed > 240 else 1
        if abs(velocity) > 50:
            if velocity > 0:
                up_score += vel_weight
                factors.append(f"BTC Velocity: UP +${velocity:.0f} [+{vel_weight}]")
            else:
                down_score += vel_weight
                factors.append(f"BTC Velocity: DOWN -${abs(velocity):.0f} [+{vel_weight}]")

        # 3. Trend Alignment
        t_penalty = 2 # Heavy weight on 1H trend
        if "UP" in trend_1h and trend_1h != "NEUTRAL":
            up_score += t_penalty
            factors.append(f"Trend 1H: {trend_1h} [+2 UP]")
        elif "DOWN" in trend_1h and trend_1h != "NEUTRAL":
            down_score += t_penalty
            factors.append(f"Trend 1H: {trend_1h} [+2 DOWN]")

        # 4. Sentiment (Odds Score)
        if abs(odds_score) > 10:
            if odds_score > 0:
                up_score += 1
                factors.append(f"Sentiment: Bullish (+{odds_score:.1f}¢) [+1 UP]")
            else:
                down_score += 1
                factors.append(f"Sentiment: Bearish ({odds_score:.1f}¢) [+1 DOWN]")

        # 5. RSI Divergence
        if rsi_1m < 30:
            up_score += 1
            factors.append(f"RSI: Oversold ({rsi_1m:.0f}) [+1 UP]")
        elif rsi_1m > 70:
            down_score += 1
            factors.append(f"RSI: Overbought ({rsi_1m:.0f}) [+1 DOWN]")

        # 🔴 FINAL DECISION
        net_score = up_score - down_score
        
        # PBN Phase (T-15s)
        if elapsed >= (window_seconds - 15) and not self.pre_buy_triggered and self.buy_mode in ["PRE", "HYBRID", "ADV"]:
            # Capture Analysis for UI/Logs
            self.pbn_analysis = {
                "factors": factors,
                "up_score": up_score,
                "down_score": down_score,
                "net_score": net_score,
                "decision": "UP" if net_score > 0 else "DOWN" if net_score < 0 else "NONE"
            }
            
            self.pre_buy_triggered = True
            side = self.pbn_analysis["decision"]
            if side == "NONE":
                side = "UP" if up_ask > down_ask else "DOWN" # Fallback
                reason = "INDECISIVE TIE"
            else:
                reason = f"SCORE {net_score:+d}"
                
            self.triggered_signal = f"PRE_BUY_{side}|MOM-2 {reason}"
            return self.triggered_signal

        # Normal Phase Execution
        if self.buy_mode == "PRE":
            return "WAIT_PRE_MODE"
            
        # Requires conviction score >= 3 for non-PBN entries
        conviction_min = 3
        if abs(net_score) >= conviction_min:
            side = "UP" if net_score > 0 else "DOWN"
            self.triggered_signal = f"BET_{side}_MOM2|Conviction {net_score:+d} HIT"
            return self.triggered_signal

        return f"WAIT_conv_{net_score:+d}"

class RsiScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None, rsi_threshold=20, time_remaining_pct=0.25):
        super().__init__(config)
        self.rsi_threshold = rsi_threshold
        self.time_remaining_pct = time_remaining_pct

    def get_signal(self, context: dict):
        if self.triggered_signal: return self.triggered_signal
        
        rsi = context.get("rsi_1m", 50)
        price = context.get("current_price", 0.5)
        bb_lower = context.get("bb_lower", 0.0)
        window_seconds = context.get("window_seconds", 300)
        time_remaining = window_seconds - context.get("elapsed", 0)
        
        if rsi < self.rsi_threshold and price < bb_lower and time_remaining > (window_seconds * self.time_remaining_pct):
            self.triggered_signal = f"BET_UP_RSI_OVERSOLD|RSI {rsi:.1f} + Below BB"
            return self.triggered_signal
        return "WAIT"

class TrapCandleScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None, start_move_pct=0.002, retrace_ratio=0.35):
        super().__init__(config)
        self.start_move_pct = start_move_pct
        self.retrace_ratio = retrace_ratio

    def get_signal(self, context: dict):
        if self.triggered_signal: return self.triggered_signal
        
        price_history = context.get("history_objs", [])
        open_price = context.get("open_price", 0.5)
        phase1_duration = context.get("phase1_duration", 60)
        
        if not price_history: return "NO_DATA"
        try:
            p3_candle = next((x for x in price_history if x['elapsed'] >= phase1_duration), None)
            if p3_candle:
                start_move = abs(p3_candle['price'] - open_price)
                current_move = abs(price_history[-1]['price'] - open_price)
                if (start_move / open_price > self.start_move_pct) and (current_move < start_move * self.retrace_ratio):
                    self.triggered_signal = "BET_DOWN_FADE_BREAKOUT|Flash Crash Fade Retraced"
                    return self.triggered_signal
        except: pass
        return "WAIT"

class MidGameScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None, min_elapsed_pct=0.30, max_green_ticks=25):
        super().__init__(config)
        self.min_elapsed_pct = min_elapsed_pct
        self.max_green_ticks = max_green_ticks

    def get_signal(self, context: dict):
        if self.triggered_signal: return self.triggered_signal
        
        price_history = context.get("history_objs", [])
        open_price = context.get("open_price", 0.5)
        elapsed = context.get("elapsed", 0)
        trend_1h = context.get("trend_1h", "NEUTRAL")
        window_seconds = context.get("window_seconds", 300)
        min_elapsed = window_seconds * self.min_elapsed_pct
        
        if not price_history: return "WAIT"
        if trend_1h == "UP": return "WAIT_TREND_MISMATCH"
        if elapsed < min_elapsed: return "WAIT_TIME"
        crossed_up = any(x['price'] > open_price for x in price_history if min_elapsed <= x['elapsed'] <= (window_seconds * 0.66))
        green_ticks = sum(1 for x in price_history if x['price'] > open_price and min_elapsed <= x['elapsed'] <= (window_seconds * 0.66))
        if crossed_up and green_ticks < self.max_green_ticks and price_history[-1]['price'] < open_price and elapsed > (window_seconds * 0.66):
             self.triggered_signal = "BET_DOWN_FAILED_RESCUE|Bulls failed to hold green"
             return self.triggered_signal
        return "WAIT"

class LateReversalScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None, min_elapsed_pct=0.73, surge_pct=1.0003):
        super().__init__(config)
        self.min_elapsed_pct = min_elapsed_pct
        self.surge_pct = surge_pct

    def get_signal(self, context: dict):
        if self.triggered_signal: return self.triggered_signal
        
        price_history = context.get("history_objs", [])
        open_price = context.get("open_price", 0.5)
        elapsed = context.get("elapsed", 0)
        window_seconds = context.get("window_seconds", 300)
        min_elapsed = window_seconds * self.min_elapsed_pct
        
        if not price_history: return "WAIT"
        if elapsed < min_elapsed: return "WAIT_TIME"
        early_low = min([x['price'] for x in price_history if x['elapsed'] < (window_seconds * 0.46)], default=open_price)
        if early_low >= open_price * 0.999: return "WAIT_NO_DROP"
        crossed = any(x['price'] > open_price for x in price_history if (window_seconds * 0.46) <= x['elapsed'] <= (window_seconds * 0.66))
        if not crossed: return "WAIT_NO_CROSS"
        if price_history[-1]['price'] > open_price * self.surge_pct:
            self.triggered_signal = "BET_UP_LATE_REVERSAL|Late surge to green"
            return self.triggered_signal
        return "WAIT"

class StaircaseBreakoutScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None):
        super().__init__(config)
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
        
    def get_signal(self, context: dict):
        if self.triggered_signal: return self.triggered_signal
        
        close_prices = context.get("close_prices", [])
        atr_5m = context.get("atr_5m", None)
        
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
            base_tolerance = self.config.TOLERANCE_PCT if self.config else 0.002
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
    def __init__(self, config: TradingConfig = None, min_pump_pct=0.003, reversal_depth=0.9985):
        super().__init__(config)
        self.min_pump_pct = min_pump_pct
        self.reversal_depth = reversal_depth

    def get_signal(self, context: dict):
        if self.triggered_signal: return self.triggered_signal
        
        current_price = context.get("current_price", 0.5)
        current_open = context.get("open_price", 0.5)
        last_window = context.get("last_window", None)
        
        if not last_window: return "NO_DATA"
        last_move = last_window['close'] - last_window['open']
        if (last_move / last_window['open'] > self.min_pump_pct) and (current_price < current_open * self.reversal_depth):
            self.triggered_signal = "BET_DOWN_POST_PUMP|Reversing previous window pump"
            return self.triggered_signal
        
        # Original logic for post-dump rally, adapted to new context
        midpoint = last_window['open'] + (last_window['height'] * 0.5)
        if last_window['close'] < last_window['open'] and current_price > midpoint and current_price > current_open:
            self.triggered_signal = "BET_UP|Post-Dump Rally Above Midpoint"
            return self.triggered_signal
        return "WAIT"

class StepClimberScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None, tick_count=15, climb_pct=1.001):
        super().__init__(config)
        self.tick_count = tick_count
        self.climb_pct = climb_pct

    def get_signal(self, context: dict):
        if self.triggered_signal: return self.triggered_signal
        
        close_prices = context.get("close_prices", [])
        
        if len(close_prices) < self.tick_count: return "WAIT_DATA"
        recent = close_prices[-self.tick_count:]
        if all(recent[i] <= recent[i+1] for i in range(len(recent)-1)):
            if recent[-1] > recent[0] * self.climb_pct:
                self.triggered_signal = f"BET_UP_STEP_CLIMBER|Gradual {self.tick_count}-tick climb detected"
                return self.triggered_signal
        return "WAIT"

class SlingshotScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None, ma_period=15):
        super().__init__(config)
        self.ma_period = ma_period

    def get_signal(self, context: dict):
        if self.triggered_signal: return self.triggered_signal
        
        close_prices = context.get("close_prices", [])
        
        if len(close_prices) < self.ma_period: return "WAIT"
        ma = sum(close_prices[-self.ma_period:]) / self.ma_period
        if close_prices[-1] > ma and (close_prices[-2] < ma or close_prices[-3] < ma):
             self.triggered_signal = f"MAX_BET_UP_RECLAIM|Reclaimed MA{self.ma_period}"
             return self.triggered_signal
        if close_prices[-1] < ma and (close_prices[-2] > ma or close_prices[-3] > ma):
             self.triggered_signal = f"MAX_BET_DOWN_BREAKDOWN|Lost MA{self.ma_period} Support"
             return self.triggered_signal
        return "WAIT"

class MinOneScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None, wick_multiplier=1.5):
        super().__init__(config)
        self.wick_multiplier = wick_multiplier

    def get_signal(self, context: dict):
        if self.triggered_signal: return self.triggered_signal
        
        price_history = context.get("history_objs", [])
        window_seconds = context.get("window_seconds", 300)
        phase1_duration = context.get("phase1_duration", 60)
        
        if elapsed < phase1_duration or elapsed > (window_seconds * 0.43): return "WAIT"
        min1 = self.get_price_slice(price_history, 0, phase1_duration)
        if not min1: return "WAIT"
        h = max(min1); l = min(min1)
        c = min1[-1]; o = min1[0]; body = abs(c - o)
        if (h - max(o, c)) > body * self.wick_multiplier: self.triggered_signal = "BET_DOWN_WICK|Liar's Wick Detected"; return self.triggered_signal
        if (min(o, c) - l) > body * self.wick_multiplier: self.triggered_signal = "BET_UP_WICK|Liar's Wick Detected"; return self.triggered_signal
        return "WAIT"

class LiquidityVacuumScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None, break_structure_pct=1.0001):
        super().__init__(config)
        self.swept = False
        self.sweep_high = 0
        self.break_structure_pct = break_structure_pct
        
    def reset(self):
        super().reset()
        self.swept = False
        self.sweep_high = 0
        
    def get_signal(self, context: dict):
        if self.triggered_signal: return self.triggered_signal
        
        current_price = context.get("current_price", 0.5)
        swing_low = context.get("swing_low", 0.0)
        
        if swing_low == 0: return "WAIT"
        if current_price < swing_low:
            self.swept = True
            if current_price > self.sweep_high: self.sweep_high = current_price
            return "SWEEP_DETECTED"
        if self.swept and current_price > swing_low * self.break_structure_pct:
            self.triggered_signal = f"BET_UP_LIQ_SWEEP|Swept {swing_low:.2f} then broke structure"
            return self.triggered_signal
        return "WAIT"

class CobraScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None, ma_period=15, std_dev_mult=1.5):
        super().__init__(config)
        self.ma_period = ma_period
        self.std_dev_mult = std_dev_mult

    def get_signal(self, context: dict):
        if self.triggered_signal: return self.triggered_signal
        closes_60m = context.get("close_prices", [])
        current_price = context.get("current_price", 0.5)
        elapsed = context.get("elapsed", 0)
        window_seconds = context.get("window_seconds", 300)
        if elapsed > (window_seconds * 0.6) or len(closes_60m) < self.ma_period: return "WAIT"
        slice_ = closes_60m[-self.ma_period:]; sma = sum(slice_) / self.ma_period
        std = (sum((x - sma) ** 2 for x in slice_) / self.ma_period) ** 0.5
        if current_price > (sma + self.std_dev_mult*std): self.triggered_signal = "BET_UP_COBRA|Explosive breakout"; return self.triggered_signal
        if current_price < (sma - self.std_dev_mult*std): self.triggered_signal = "BET_DOWN_COBRA|Explosive breakdown"; return self.triggered_signal
        return "WAIT"

class CoiledCobraScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None):
        super().__init__(config)
        self.vol_history = []  # Track 20-period StdDev over the window
        
        # Adjustable parameters
        self.coil_threshold_pct = 0.25
        self.coil_lookback_history = 60
        self.coil_lookback_recent = 10
        
    def get_signal(self, context: dict):
        if self.triggered_signal: return self.triggered_signal
        
        closes_60m = context.get("close_prices", [])
        current_price = context.get("current_price", 0.5)
        
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
    def __init__(self, config: TradingConfig = None, pump_threshold=0.001, cross_count=2):
        super().__init__(config)
        self.state = "SEARCHING"
        self.mesa_floor = None
        self.pump_start_time = None
        self.pump_threshold = pump_threshold
        self.cross_count = cross_count
        
    def reset(self): super().reset(); self.state = "SEARCHING"; self.mesa_floor = None; self.pump_start_time = None
    
    def get_signal(self, context: dict):
        if self.triggered_signal: return self.triggered_signal
        
        price_history = context.get("history_objs", [])
        open_price = context.get("open_price", 0.5)
        elapsed = context.get("elapsed", 0)
        phase1_duration = context.get("phase1_duration", 60)
        
        if not price_history: return "WAIT"
        if elapsed < phase1_duration: return "WAIT_TIME"
        current_price = price_history[-1]['price']
        if self.state == "SEARCHING":
            if elapsed <= phase1_duration and (current_price - open_price) / open_price > self.pump_threshold:
                self.state = "WATCHING_TOP"; self.pump_start_time = elapsed; return "PUMP_DETECTED"
        elif self.state == "WATCHING_TOP":
            if elapsed < (self.pump_start_time + (phase1_duration * 0.66)): return "WAIT_DEVELOP"
            mesa_window = self.get_price_slice(price_history, elapsed - phase1_duration, elapsed)
            if len(mesa_window) < 10: return "WAIT_DATA"
            ma = sum(mesa_window) / len(mesa_window); crosses = sum(1 for i in range(1, len(mesa_window)) if (mesa_window[i-1] > ma) != (mesa_window[i] > ma))
            self.mesa_floor = min(mesa_window)
            if crosses >= self.cross_count: self.state = "HUNTING_BREAK"; return "MESA_ARMED"
            if current_price > ma * 1.001: self.reset(); return "ABORT_BULL_FLAG"
        elif self.state == "HUNTING_BREAK":
            last_5 = [p['price'] for p in price_history[-5:]]
            if last_5 and max(last_5) < self.mesa_floor:
                self.triggered_signal = "BET_DOWN_HEAVY|Mesa Collapse Confirmed"; self.state = "EXECUTED"; return self.triggered_signal
        return "WAIT"

class MeanReversionScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None, reversal_threshold=0.0005):
        super().__init__(config)
        self.reversal_threshold = reversal_threshold

    def get_signal(self, context: dict):
        if self.triggered_signal: return self.triggered_signal
        
        price_history = context.get("history_objs", [])
        fast_bb = context.get("fast_bb", None)
        trend_1h = context.get("trend_1h", "NEUTRAL")
        
        if trend_1h == "UP": return "WAIT_TREND_MISMATCH"
        if not fast_bb or len(price_history) < 20: return "WAIT"
        upper_band = fast_bb[0]; current_price = price_history[-1]['price']
        recent_prices = [p['price'] for p in price_history]
        if not recent_prices: return "WAIT"
        last_20 = recent_prices[-20:]
        if any(p > upper_band for p in last_20) and current_price < upper_band:
            peak_price = max(last_20)
            if (peak_price - current_price) / peak_price > self.reversal_threshold:
                self.triggered_signal = f"SHORT_THE_SNAP|Rejection from Top"; return self.triggered_signal
        return "WAIT"

class GrindSnapScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None, grind_duration=100, snap_duration=20, min_slope_pct=0.1, reversal_ratio=0.60):
        super().__init__(config)
        self.grind_duration = grind_duration
        self.snap_duration = snap_duration
        self.min_slope_pct = min_slope_pct
        self.reversal_ratio = reversal_ratio

    def get_signal(self, context: dict):
        if self.triggered_signal: return self.triggered_signal
        
        price_history = context.get("history_objs", [])
        elapsed = context.get("elapsed", 0)
        window_seconds = context.get("window_seconds", 300)
        
        # Scale durations based on window
        scaler = window_seconds / 300.0
        grind_dur = self.grind_duration * scaler
        snap_dur = self.snap_duration * scaler
        
        # Minimum time needed for both the grind and the snap
        total_required_time = grind_dur + snap_dur
        
        if not price_history: return "WAIT"
        if elapsed < (total_required_time + 10): return "WAIT_TIME"
        
        p_now = price_history[-1]['price']
        
        # We define T-0 as roughly "10 seconds ago" to give the snap time to form 
        # but to have ended just recently.
        p_snap_end = next((x['price'] for x in reversed(price_history) if x['elapsed'] <= (elapsed - 10)), None)
        p_snap_start = next((x['price'] for x in reversed(price_history) if x['elapsed'] <= (elapsed - 10 - snap_dur)), None)
        p_grind_start = next((x['price'] for x in reversed(price_history) if x['elapsed'] <= (elapsed - 10 - snap_dur - grind_dur)), None)
        
        if not p_snap_end or not p_snap_start or not p_grind_start: return "WAIT"
        
        grind_move = p_snap_start - p_grind_start
        
        # Check minimum grind slope (convert percentage to a decimal fraction)
        if abs(grind_move / p_grind_start) < (self.min_slope_pct / 100.0): return "WAIT_FLAT"
        
        snap_move = p_snap_end - p_snap_start
        
        # We need the snap move to be in the opposite direction
        if (grind_move > 0 and snap_move > 0) or (grind_move < 0 and snap_move < 0): return "WAIT_NOT_A_SNAP"
            
        recent_snap_period = self.get_price_slice(price_history, elapsed - 10 - snap_dur, elapsed)
        
        # Ensure it didn't completely reverse BACK into the grind direction during the snap window
        if grind_move > 0 and any(p > p_snap_start for p in recent_snap_period): return "WAIT_FAILED_HOLD"
        elif grind_move < 0 and any(p < p_snap_start for p in recent_snap_period): return "WAIT_FAILED_HOLD"
        
        # Check if snap reversal intensity matches/beats the user ratio
        if abs(snap_move / grind_move) > self.reversal_ratio:
             self.triggered_signal = f"BET_{'DOWN' if grind_move > 0 else 'UP'}_SNAP|Grind Snapped"; return self.triggered_signal
             
        return "WAIT"

class VolCheckScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None, avg_3m_multiplier=1.0):
        super().__init__(config)
        self.avg_3m_multiplier = avg_3m_multiplier

    def get_signal(self, context: dict):
        if self.triggered_signal: return self.triggered_signal
        
        closes_60m = context.get("close_prices", [])
        current_price = context.get("current_price", 0.5)
        open_price = context.get("open_price", 0.5)
        elapsed = context.get("elapsed", 0)
        window_seconds = context.get("window_seconds", 300)
        up_p = context.get("up_ask", 0.5) 
        down_p = context.get("down_ask", 0.5)
        
        if (window_seconds-elapsed) > (window_seconds * 0.33) or (window_seconds-elapsed) < 10: return "WAIT_TIME"
        target_side = "UP" if 0.85 <= up_p <= 0.90 else ("DOWN" if 0.85 <= down_p <= 0.90 else None)
        if not target_side: return "WAIT_PRICE"
        if len(closes_60m) < 45: return "WAIT_DATA"
        ranges = []
        for i in range(0, 42, 3): chunk = closes_60m[-45+i:-45+i+3]; ranges.append(max(chunk)-min(chunk))
        avg_3m = sum(ranges)/len(ranges)
        dist = abs(current_price - open_price)
        if dist > (avg_3m * self.avg_3m_multiplier) and ((target_side == "UP" and current_price > open_price) or (target_side == "DOWN" and current_price < open_price)):
             self.triggered_signal = f"VOL_SAFE_{target_side}|Gap > Avg3m Range"; return self.triggered_signal
        return "WAIT"

class MosheSpecializedScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None, t1=290, d1=2000.0, t2=80, d2=80.0, t3=15, d3=25.0, moshe_threshold=0.86):
        super().__init__(config)
        self.checkpoints = {}
        # 3-Point Time Remaining and Min Diff Curve
        self.bet_size = 2.0
        self.t1 = t1; self.d1 = d1
        self.t2 = t2; self.d2 = d2
        self.t3 = t3; self.d3 = d3
        self.moshe_threshold = moshe_threshold
        
    def reset(self): super().reset(); self.checkpoints = {}
    
    def get_signal(self, context: dict):
        if self.triggered_signal: return self.triggered_signal
        
        elapsed = context.get("elapsed", 0)
        price = context.get("current_price", 0.5)
        open_price = context.get("open_price", 0.5)
        trend_1h = context.get("trend_1h", "NEUTRAL")
        up_p = context.get("up_ask", 0.5)
        down_p = context.get("down_ask", 0.5)
        window_seconds = context.get("window_seconds", 300)
        
        time_rem = window_seconds - elapsed
        
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
        # Added Safety: The side we're betting on must ACTUALLY be the leading side
        if self.moshe_threshold <= up_p < 1.0 and up_p > down_p:
            if "DOWN" in trend_1h and "S-" in trend_1h:
                return "WAIT_TREND_SAFE"
            self.triggered_signal = f"BET_UP_MOSHE_90|High Probability Win (BTC Diff: ${actual_diff:.2f})"
            return self.triggered_signal
            
        if self.moshe_threshold <= down_p < 1.0 and down_p > up_p:
            if "UP" in trend_1h and "S-" in trend_1h:
                return "WAIT_TREND_SAFE"
            self.triggered_signal = f"BET_DOWN_MOSHE_90|High Probability Win (BTC Diff: ${actual_diff:.2f})"
            return self.triggered_signal

        return "WAIT"

class ZScoreBreakoutScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None, z_threshold=3.5, coil_threshold=0.001):
        super().__init__(config)
        self.z_threshold = z_threshold
        self.coil_threshold = coil_threshold

    def get_signal(self, context: dict):
        if self.triggered_signal: return self.triggered_signal
        
        price_history = context.get("history_objs", [])
        open_price = context.get("open_price", 0.5)
        elapsed = context.get("elapsed", 0)
        window_seconds = context.get("window_seconds", 300)
        
        if not price_history: return "WAIT"
        if elapsed < (window_seconds * 0.73): return "WAIT_TIME"
        early_data = self.get_price_slice(price_history, 0, (window_seconds * 0.73))
        if not early_data: return "WAIT"
        avg = sum(early_data)/len(early_data); std = (sum((p-avg)**2 for p in early_data)/len(early_data))**0.5 or 0.01
        if (max(early_data)-min(early_data))/open_price > self.coil_threshold: return "WAIT_NO_COIL"
        z = (price_history[-1]['price'] - avg) / std
        thresh = self.z_threshold if elapsed < (window_seconds * 0.86) else (self.z_threshold - 0.5)
        if abs(z) > thresh:
            if (z > 0 and price_history[-1]['price'] > max(early_data)) or (z < 0 and price_history[-1]['price'] < min(early_data)):
                self.triggered_signal = f"BET_{'UP' if z > 0 else 'DOWN'}_ZSCORE|Breakout Z={z:.1f}"; return self.triggered_signal
        return "WAIT"

class NitroScanner(BaseScanner):
    """
    NITRO (NIT) Scanner: Triggers a buy if btc_diff exceeds 5m ATR within the first X minutes.
    Designed to catch impulsive volatility gaps at window start.
    """
    def __init__(self, config: TradingConfig = None, time_cutoff_pct=0.40):
        super().__init__(config)
        self.time_cutoff_pct = time_cutoff_pct # First 40% default
        self.atr_multiplier = 1.0 # Multiplier of ATR needed for trigger
        self.last_skip_reason = None

    def get_signal(self, context: dict) -> str:
        self.last_skip_reason = None
        if self.triggered_signal: return self.triggered_signal

        elapsed = context.get("elapsed", 0)
        btc_price = context.get("btc_price", 0)
        btc_open = context.get("btc_open", 0)
        btc_diff = btc_price - btc_open
        atr_5m = context.get("atr_5m", 0)
        window_seconds = context.get("window_seconds", 300)

        # 1. Time Gate (Nitro only fires in the 'impulse' phase)
        if elapsed > (window_seconds * self.time_cutoff_pct):
            return "WAIT_NEXT_WINDOW"
        
        # 2. ATR Gap Logic
        if atr_5m <= 0: return "WAIT_DATA"
        
        gap_needed = atr_5m * self.atr_multiplier
        if abs(btc_diff) >= gap_needed:
            side = "UP" if btc_diff > 0 else "DOWN"
            self.triggered_signal = f"BET_{side}_NIT|BTC Gap ${abs(btc_diff):.2f} > ATR ${gap_needed:.2f}"
            return self.triggered_signal
        
        self.last_skip_reason = f"BTC Gap ${abs(btc_diff):.2f} < ATR Req ${gap_needed:.2f}"
        return "NO_SIGNAL"


class VolSnapScanner(BaseScanner):
    """
    VOLSNAP (VSN) Scanner: Accumulates BTC order book volume snapshots for the first X minutes
    of a window. Triggers if the difference between cumulative UP and DOWN volume
    exceeds a user-defined threshold.
    - Cum-UP lead > Threshold -> BET_UP
    - Cum-DN lead > Threshold -> BET_DOWN
    """
    def __init__(self, config: TradingConfig = None, time_cutoff_pct=0.20):
        super().__init__(config)
        self.time_cutoff_pct = time_cutoff_pct # Default: first 20%
        self.diff_threshold = 50.0 # Default: 50 BTC lead
        self.cum_up = 0.0
        self.cum_dn = 0.0
        self.last_skip_reason = None
        self._last_elapsed = -1

    def reset(self):
        super().reset()
        self.cum_up = 0.0
        self.cum_dn = 0.0
        self._last_elapsed = -1

    def get_signal(self, context: dict) -> str:
        self.last_skip_reason = None
        if self.triggered_signal: return self.triggered_signal

        elapsed = context.get("elapsed", 0)
        vol_up = context.get("vol_up", 0)
        vol_dn = context.get("vol_dn", 0)
        window_seconds = context.get("window_seconds", 300)

        # 1. Accumulation Phase
        time_cutoff = window_seconds * self.time_cutoff_pct
        if elapsed <= time_cutoff:
             if elapsed > self._last_elapsed:  # Only add once per second
                 self.cum_up += vol_up
                 self.cum_dn += vol_dn
                 self._last_elapsed = elapsed
             
             self.last_skip_reason = f"ACCUMULATING: U{self.cum_up:.0f} D{self.cum_dn:.0f} (T-{time_cutoff-elapsed:.0f}s)"
             return "WAIT"

        # 2. Trigger Phase (after time cutoff)
        diff = self.cum_up - self.cum_dn
        
        if abs(diff) >= self.diff_threshold:
            side = "UP" if diff > 0 else "DOWN"
            lead_symbol = "U!" if diff > 0 else "D!"
            self.triggered_signal = f"BET_{side}_VSN|Vol Lead {lead_symbol} {abs(diff):.1f}B > {self.diff_threshold:.0f}B"
            return self.triggered_signal

        self.last_skip_reason = f"DIFF {abs(diff):.1f}B < THRESHOLD {self.diff_threshold:.0f}B"
        return "WAIT"

class BriefingScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None):
        super().__init__(config)
        self.rsi_low = 30
        self.rsi_high = 70
        self.odds_thresh = 5.0
        self.imb_thresh = 2.0
        self.signal_thresh = 2
        self.weight_trend = 1
        self.weight_rsi = 1
        self.weight_odds = 1
        self.weight_imb = 1

    def get_signal(self, context: dict):
        elapsed = context.get("elapsed", 0)
        if elapsed > 15: 
            return "WAIT"
            
        # Per-window latch logic
        if self.triggered_signal:
            return "WAIT"

        u_p = 0
        d_p = 0
        
        t1 = context.get("trend_1h", "NEUTRAL").upper()
        rsi = context.get("rsi_1m", 50)
        odds = context.get("odds_score", 0)
        
        up_ask = context.get("up_ask", 0)
        dn_ask = context.get("down_ask", 0)
        imb = (up_ask - dn_ask) * 100

        # Scoring
        if "BULL" in t1: u_p += self.weight_trend
        if "BEAR" in t1: d_p += self.weight_trend

        if rsi < self.rsi_low: u_p += self.weight_rsi
        if rsi > self.rsi_high: d_p += self.weight_rsi

        if odds > self.odds_thresh: u_p += self.weight_odds
        elif odds < -self.odds_thresh: d_p += self.weight_odds

        if imb < -self.imb_thresh: d_p += self.weight_imb 
        elif imb > self.imb_thresh: u_p += self.weight_imb

        score = u_p - d_p
        if score >= self.signal_thresh:
            self.triggered_signal = f"BET_UP_BRIEF|Score {score} (U{u_p} D{d_p})"
            return self.triggered_signal
        elif score <= -self.signal_thresh:
            self.triggered_signal = f"BET_DOWN_BRIEF|Score {score} (U{u_p} D{d_p})"
            return self.triggered_signal

        self.last_skip_reason = f"SCORE {score} NEUTRAL (U{u_p} D{d_p})"
        return "WAIT"

class HdoScanner(BaseScanner):
    def __init__(self, config: TradingConfig = None):
        super().__init__(config)
        self.trigger_threshold = 0.59
    def get_signal(self, context: dict):
        return "WAIT" # Logic is actually internal to trade_engine.py _check_hdo

ALGO_INFO = {
    "NPA": {"name": "N-Pattern", "desc": "Detects impulse moves followed by a retracement support and subsequent breakout of the new high."},
    "FAK": {"name": "Fakeout", "desc": "Spots rejected 'rescue' attempts where price spikes above open but fails and sinks back below."},
    "MOM": {"name": "Momentum", "desc": "Dual Mode: TIME (Default 10s lead) or PRICE (Threshold trigger 51-70¢)."},
    "MM2": {"name": "Momentum-2", "desc": "Redesigned MOM with Unified Scoring Intelligence and Time-Aware weights."},
    "RSI": {"name": "RSI Oversold", "desc": "Standard RSI < 15 check combined with a Bollinger Band lower-touch for extreme reversals."},
    "TRA": {"name": "Trap Candle", "desc": "Fades aggressive breakouts that get >75% retraced within the same 5-minute window."},
    "MID": {"name": "Mid-Game", "desc": "Identifies bulls failing to hold green in the middle of the round, leading to a 'Failed Rescue' drop."},
    "LAT": {"name": "Late Reversal", "desc": "Spots late-window surges that cross from red to green after an early-window drop was established."},
    "STA": {"name": "Staircase", "desc": "Detects orderly, rising lows (steps) followed by an aggressive breakout of the local high."},
    "POS": {"name": "Post-Pump", "desc": "Mean reversion logic that trades the fade after a massive, single-bar pump or dump."},
    "STE": {"name": "Step Climber", "desc": "The 'Pulse Entry' - looks for a perfect touch of the 20-period Moving Average from above."},
    "SLI": {"name": "Slingshot", "desc": "Triggers on the reclaim (UP) or breakdown (DOWN) of the 20-period Moving Average line."},
    "MIN": {"name": "Min-One", "desc": "Checks the 1-minute candle for 'Long Wicks' (2x body size) to detect deceptive exhaustion."},
    "LIQ": {"name": "Liq Vacuum", "desc": "Sweeps a previous swing low to grab liquidity before reversing aggressively."},
    "COB": {"name": "Cobra Break", "desc": "Detects explosive, high-volatility breakouts outside the 2-Sigma Bollinger Bands."},
    "CCO": {"name": "Coiled Cobra", "desc": "Refined Vol-Crossover: MA20 reclaim following a low-volatility 'coiled' phase."},
    "MES": {"name": "Mesa Collapse", "desc": "Spots a flat/choppy distribution top ('Mesa') that unexpectedly collapses below its floor."},
    "MEA": {"name": "Mean Reversion", "desc": "Standard rejection from the upper/lower 20-period Bollinger Bands toward the 1H trend mean."},
    "GRI": {"name": "Grind-Snap", "desc": "Detects a tight, 2-minute 'grind' phase followed by a sharp impulse snap in either direction."},
    "VOL": {"name": "Vol-Check", "desc": "Calculates if the move distance is greater than the average 3-minute range to ensure volatility exists."},
    "MOS": {"name": "Moshe Pulse", "desc": "Surge detection based on 30-second price checkpoints and 1H macro trend alignment."},
    "NIT": {"name": "Nitro BTC", "desc": "Triggers if BTC price move exceeds 5m ATR within the first 2 minutes of the window."},
    "ZSC": {"name": "Z-Score", "desc": "Statistical breakout scanner triggering when price deviates >3.5 Standard Deviations from the window mean."},
    "VSN": {"name": "Vol Snap", "desc": "Triggers when BTC order book depth near the window open exceeds X BTC on one side, indicating strong directional conviction."},
    "HDO": {"name": "Hedge Direction Opposite", "desc": "Protects portfolio by entering an opposite position when the counter-side price crosses a threshold. Amount is scaled by Algo Weight."},
    "BRI": {"name": "Briefing", "desc": "Automated 'My Guess' logic: Uses 1H trend, RSI, bid spread, and ask imbalance at window start to determine conviction."}
}
