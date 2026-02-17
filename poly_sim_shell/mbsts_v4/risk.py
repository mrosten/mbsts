import time
from .config import TradingConfig

class RiskManager:
    """
    Centralized Risk Management System.
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
        self.reset_window() # Clear allocation state for new bankroll
            
    def calculate_bet_size(self, strategy_type, balance, consecutive_losses, trend_context):
        """
        Determine safe bet size based on bankroll, recent performance, and market context.
        """
        # 1. Base Sizing
        budget_pct = TradingConfig.DEFAULT_RISK_PCT
        strong_patterns = ["UPTREND", "STRONG_TREND", "COBRA", "LIQ_SWEEP", "LATE_REVERSAL"]
        if any(p in strategy_type for p in strong_patterns):
            budget_pct = TradingConfig.STRONG_RISK_PCT
            
        # Use Initial Window Bankroll (before current window's bets) as the base
        base = self.risk_bankroll + self.allocated_this_window
        if base <= 0: return 0.0
        
        cost = base * budget_pct
        
        # 2. Adjustments
        if "FAKEOUT" in strategy_type.upper():
             cost *= 0.5
        
        trend_4h = trend_context.get('trend_4h', 'NEUTRAL')
        direction = trend_context.get('direction', 'UP')
        if trend_4h != 'NEUTRAL' and trend_4h != direction:
            cost *= 0.5
            
        if consecutive_losses >= 2:
            cost *= 0.7
            
        # 3. Clamping
        cost = max(0, min(cost, TradingConfig.MAX_BET_SESSION_CAP))
        
        if cost < TradingConfig.MIN_BET:
            if base >= TradingConfig.MIN_BET: return TradingConfig.MIN_BET
            return 0.0
            
        return round(cost, 2)

    def register_bet(self, cost):
        self.risk_bankroll -= cost
        self.allocated_this_window += cost
        
    def reset_window(self):
        self.allocated_this_window = 0.0
        self.window_bets = []

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
        self.active_trades = [] # List of {side, entry, cost, shares, timestamp}

    def calculate_bet_size(self, context, strategy_type):
        if not self.is_active: return 0
        budget_pct = TradingConfig.DEFAULT_RISK_PCT
        strong_patterns = ["UPTREND", "STRONG_TREND", "COBRA", "LIQ_SWEEP", "LATE_REVERSAL"]
        if any(p in strategy_type for p in strong_patterns):
            budget_pct = TradingConfig.STRONG_RISK_PCT
            
        base_capital = context.get('risk_cap', self.balance)
        cost = base_capital * budget_pct
        
        trend_4h = context.get('trend_4h', 'NEUTRAL')
        direction = context.get('direction', 'UP')
        if trend_4h != 'NEUTRAL' and trend_4h != direction:
            cost *= 0.5
            
        if self.consecutive_losses >= 2:
            cost *= 0.7
            
        if cost < TradingConfig.MIN_BET:
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
                    payout = trade['shares']
                    self.total_wins += 1
                    self.consecutive_losses = 0
                elif win_side == "DRAW":
                    payout = trade['cost']
                    self.total_draws += 1
                else:
                    payout = 0
                    self.total_losses += 1
                    self.consecutive_losses += 1
                
                total_payout += payout
                total_profit += (payout - trade['cost'])
                
            self.balance += total_payout
            self.active_trades = [] 
        
        if self.balance < TradingConfig.MIN_BET:
            self.is_active = False
            
        return total_payout, total_profit
