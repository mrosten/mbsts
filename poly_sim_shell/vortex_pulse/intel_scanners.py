import time
import math
import collections
from datetime import datetime

# Handle imports for both package and direct execution
try:
    from .config import TradingConfig
    from .scanners import BaseScanner
except ImportError:
    from config import TradingConfig
    from scanners import BaseScanner

class WindowCandleProfiler(BaseScanner):
    """
    WCP: Analyzes the OHLC of the previous window to detect reversal/continuation patterns.
    """
    def __init__(self, config: TradingConfig = None):
        super().__init__(config)
        self.body_ratio_thresh = 0.30  # Body must be < 30% for a Dojo/Hammer
        self.shadow_ratio_thresh = 2.0  # One shadow must be 2x the body

    def get_signal(self, context: dict) -> str:
        if self.triggered_signal: return self.triggered_signal
        
        last_window = context.get("last_window_ohlc")
        if not last_window: return "WAIT_DATA"
        
        open_p = last_window.get("open")
        high_p = last_window.get("high")
        low_p = last_window.get("low")
        close_p = last_window.get("close")
        
        if not all([open_p, high_p, low_p, close_p]): return "WAIT_DATA"
        
        body = abs(close_p - open_p)
        total_range = high_p - low_p
        if total_range == 0: return "WAIT"
        
        upper_shadow = high_p - max(open_p, close_p)
        lower_shadow = min(open_p, close_p) - low_p
        
        # Shooting Star (Bearish Reversal)
        if upper_shadow > (body * self.shadow_ratio_thresh) and lower_shadow < (body * 0.5):
            self.triggered_signal = "BET_DOWN_WCP|Shooting Star detected in prev window"
            return self.triggered_signal
            
        # Hammer (Bullish Reversal)
        if lower_shadow > (body * self.shadow_ratio_thresh) and upper_shadow < (body * 0.5):
            self.triggered_signal = "BET_UP_WCP|Hammer detected in prev window"
            return self.triggered_signal

        return "WAIT"

class VPOCAnalyzer(BaseScanner):
    """
    VPOC: Tracks Volume Point of Control to identify 'thin' price moves.
    """
    def __init__(self, config: TradingConfig = None):
        super().__init__(config)
        self.dev_threshold = 0.0005 # 0.05% deviation from POC

    def get_signal(self, context: dict) -> str:
        if self.triggered_signal: return self.triggered_signal
        
        poc = context.get("last_window_poc")
        curr_p = context.get("current_price")
        if not poc or not curr_p: return "WAIT_DATA"
        
        dev = (curr_p - poc) / poc
        
        # If price is far above POC, it might be an overextended 'thin' move
        if dev > self.dev_threshold:
            self.triggered_signal = f"BET_DOWN_VPOC|Overextended above POC ({dev*100:.2f}%)"
            return self.triggered_signal
        elif dev < -self.dev_threshold:
            self.triggered_signal = f"BET_UP_VPOC|Overextended below POC ({abs(dev)*100:.2f}%)"
            return self.triggered_signal

        return "WAIT"

class SettlementDriftPredictor(BaseScanner):
    """
    SDP: Analyzes the Basis Gap between Polymarket and Kraken at settlement.
    """
    def __init__(self, config: TradingConfig = None):
        super().__init__(config)
        self.drift_threshold = 0.05 # 5 cent drift

    def get_signal(self, context: dict) -> str:
        if self.triggered_signal: return self.triggered_signal
        
        drift = context.get("last_settlement_drift")
        if drift is None: return "WAIT_DATA"
        
        if drift > self.drift_threshold:
            # Poly was over-priced vs Kraken; expect a downward snap
            self.triggered_signal = f"BET_DOWN_SDP|Basis Gap Collapse (Drift: {drift*100:.1f}c)"
            return self.triggered_signal
        elif drift < -self.drift_threshold:
            # Poly was under-priced vs Kraken; expect an upward snap
            self.triggered_signal = f"BET_UP_SDP|Basis Gap Rebound (Drift: {drift*100:.1f}c)"
            return self.triggered_signal

        return "WAIT"

class SentimentDivergenceScanner(BaseScanner):
    """
    DIV: Compares Odds Score delta vs BTC Price delta to detect human over-anticipation.
    """
    def __init__(self, config: TradingConfig = None):
        super().__init__(config)
        self.div_threshold = 5.0 # Odds points per 0.1% BTC move

    def get_signal(self, context: dict) -> str:
        if self.triggered_signal: return self.triggered_signal
        
        odds_delta = context.get("odds_delta")
        btc_pct_delta = context.get("btc_pct_delta")
        
        if odds_delta is None or btc_pct_delta is None or btc_pct_delta == 0: return "WAIT"
        
        intensity = odds_delta / (btc_pct_delta * 1000) # Points per 0.1%
        
        if intensity > self.div_threshold:
            # Humans are moving odds way faster than BTC is moving (BULLISH BUBBLE)
            self.triggered_signal = f"BET_DOWN_DIV|Sentiment Bubble (Int: {intensity:.1f})"
            return self.triggered_signal
        elif intensity < -self.div_threshold:
            # Humans are panic selling odds faster than BTC drop (BEARISH BUBBLE)
            self.triggered_signal = f"BET_UP_DIV|Sentiment Panic (Int: {intensity:.1f})"
            return self.triggered_signal

        return "WAIT"

class StrategyInversionScanner(BaseScanner):
    """
    SSI: Monitors session win streaks and inverts signals if accuracy is critically low.
    """
    def __init__(self, config: TradingConfig = None):
        super().__init__(config)
        self.loss_streak_threshold = 3
        self.active_inversion = False

    def get_signal(self, context: dict) -> str:
        streak = context.get("current_loss_streak", 0)
        
        if streak >= self.loss_streak_threshold:
            if not self.active_inversion:
                self.active_inversion = True
            return "READY_INVERT" # SSI doesn't bet directly, it signals others to invert
        else:
            self.active_inversion = False
            return "WAIT"
