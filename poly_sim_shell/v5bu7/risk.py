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
        self.window_start_bankroll = 0.0 # Snapshot of bankroll at start of window
        self.allocated_this_window = 0.0
        self.window_bets = [] # List of {id, cost, potential_payout}
        self.window_bets = [] # List of {id, cost, potential_payout}
        self.bet_percentage = TradingConfig.DEFAULT_RISK_PCT  # Default 12% of risk bankroll per bet
    def set_bankroll(self, amount, is_live=False):
        self.is_live_mode = is_live
        if is_live:
            self.risk_bankroll = amount / TradingConfig.LIVE_RISK_DIVISOR
        else:
            self.risk_bankroll = amount
        self.target_bankroll = self.risk_bankroll # Set Cap to initial value
        self.window_start_bankroll = self.risk_bankroll
        self.reset_window() # Clear allocation state for new bankroll
            
    def calculate_bet_size(self, strategy_type, balance, consecutive_losses, trend_context):
        """
        Determine safe bet size based on bankroll, recent performance, and market context.
        """
        # 1. Base Sizing using the Window Start Bankroll anchor
        base = self.window_start_bankroll
        if base <= 0: return 0.0
        
        cost = base * self.bet_percentage
        
        # 2. Assign Confidence Tier
        # 2. Apply Confidence Multipliers
        trend_1h = trend_context.get('trend_1h', 'NEUTRAL')
        direction = trend_context.get('direction', 'UP')
        
        if trend_1h != 'NEUTRAL' and trend_1h != direction:
            # Note: Since risk.py doesn't have direct access to app instance here,
            # this will be overridden by trade_engine.py's penalty\_percentage anyway.
            # Defaulting to 10% penalty
            cost *= 0.90
            
        if consecutive_losses >= 2:
            cost *= 0.7
            
        if "FAKEOUT" in strategy_type.upper():
            cost = 1.00
            
        # 3. Apply Tier Pricing
        cost = max(TradingConfig.MIN_BET, min(cost, TradingConfig.MAX_BET_SESSION_CAP))
            
        # 4. Final Safety Clamping: Cannot bet more than what's left in the window
        cost = min(cost, self.risk_bankroll)
        
        if cost < TradingConfig.MIN_BET:
            return 0.0
            
        return round(cost, 2)

    def register_bet(self, cost):
        self.risk_bankroll -= cost
        self.allocated_this_window += cost
        if self.risk_bankroll < 0:
            self.risk_bankroll = 0.0  # Hard floor - never go negative
        
    def reset_window(self):
        self.allocated_this_window = 0.0
        self.window_bets = []
        self.window_start_bankroll = self.risk_bankroll

    def register_settlement(self, payout, realized_revenue, grow=False):
        """Adds profits back to the risk bankroll after a window closes."""
        total_back = payout + realized_revenue
        self.risk_bankroll += total_back
        
        if not grow:
            # Cap the bankroll at the target_bankroll if compounding is disabled
            if self.risk_bankroll > self.target_bankroll:
                self.risk_bankroll = self.target_bankroll
        else:
            # If compounding is enabled, update the target cap as well
            if self.risk_bankroll > self.target_bankroll:
                self.target_bankroll = self.risk_bankroll
        
        self.window_start_bankroll = self.risk_bankroll

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
        self.ledger = {} # Dictionary mapping ticket_id -> {side, entry, cost, shares, target_tp, target_sl, ...}

    def calculate_bet_size(self, context, strategy_type):
        if not self.is_active: return 0
        
        # Base capital relies on the persistent starting balance setting
        base_capital = context.get('target_bankroll', self.initial_balance)
        cost = base_capital * TradingConfig.DEFAULT_RISK_PCT
        
        trend_1h = context.get('trend_1h', 'NEUTRAL')
        direction = context.get('direction', 'UP')
        
        if trend_1h != 'NEUTRAL' and trend_1h != direction:
            cost *= 0.90
            
        if self.consecutive_losses >= 2:
            cost *= 0.7
            
        if "FAKEOUT" in strategy_type.upper():
            cost = 1.00
            
        cost = max(TradingConfig.MIN_BET, min(cost, TradingConfig.MAX_BET_SESSION_CAP))
            
        # Final Safety Clamping
        cost = min(cost, self.balance)
        
        if cost < TradingConfig.MIN_BET:
            return 0.0
            
        return round(cost, 2)

    def record_trade(self, ticket_id, side, entry_price, cost, shares, target_tp=None, target_sl=None, contract_price=0.50):
        self.balance -= cost
        self.ledger[ticket_id] = {
            "algo_name": self.algo_name,
            "side": side,
            "entry_price": entry_price,
            "cost": cost,
            "shares": shares,
            "target_tp": target_tp,
            "target_sl": target_sl,
            "contract_price": contract_price,
            "timestamp": time.time(),
            "status": "OPEN",
            "limit_order_id": None
        }

    def settle_window(self, win_side, close_price, open_price):
        total_payout = 0
        total_profit = 0
        
        if self.ledger:
            for ticket_id, trade in list(self.ledger.items()):
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
            self.ledger.clear() 
        
        if self.balance < TradingConfig.MIN_BET:
            self.is_active = False
            
        return total_payout, total_profit
