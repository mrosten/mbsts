
from mbsts_v4.risk import RiskManager
from types import SimpleNamespace

# Mock App Structure with STRICT Clamping Logic
class MockApp:
    def __init__(self):
        self.risk_manager = RiskManager()
        self.risk_initialized = True
        self.live_broker = SimpleNamespace(balance=100.0)
        self.sim_broker = SimpleNamespace(balance=100.0)
        self.query_one = lambda x: SimpleNamespace(value=True) # Always Live
        
    def _add_risk_revenue(self, amount):
        if not self.risk_initialized: return
        
        is_live = self.query_one("#cb_live").value
        main_bal = self.live_broker.balance if is_live else self.sim_broker.balance

        print(f"DEBUG: Start Risk: {self.risk_manager.risk_bankroll:.2f} | Target: {self.risk_manager.target_bankroll:.2f} | Wallet: {main_bal:.2f} | Adding: {amount:.2f}")

        # 1. Add revenue to current bankroll
        self.risk_manager.risk_bankroll += amount
        
        # 2. Hard Clamping: Never exceed the Wallet Balance
        if self.risk_manager.risk_bankroll > main_bal:
            print("DEBUG: Clamped to Wallet Balance")
            self.risk_manager.risk_bankroll = main_bal

        # 3. Refill Logic: If we are below target, check if general balance allows for replenishment
        if self.risk_manager.risk_bankroll < self.risk_manager.target_bankroll:
            if main_bal >= self.risk_manager.target_bankroll:
                 print("DEBUG: Refilling to Target from Wallet")
                 self.risk_manager.risk_bankroll = self.risk_manager.target_bankroll
            else:
                 print("DEBUG: Wallet too low to refill fully, syncing to wallet")
                 self.risk_manager.risk_bankroll = main_bal
        
        # 4. STRICT Clamping: Skim EVERYTHING above the target.
        if self.risk_manager.risk_bankroll > self.risk_manager.target_bankroll:
             skim_amt = self.risk_manager.risk_bankroll - self.risk_manager.target_bankroll
             print(f"DEBUG: STRICT Skimming excess above target. Risk: {self.risk_manager.risk_bankroll:.2f} -> {self.risk_manager.target_bankroll:.2f} (Skimmed: ${skim_amt:.2f})")
             self.risk_manager.risk_bankroll = self.risk_manager.target_bankroll
            
        print(f"DEBUG: End Risk: {self.risk_manager.risk_bankroll:.2f}")

    def update_balance_ui(self): pass

# Test Case
app = MockApp()
app.risk_manager.set_bankroll(50.0, is_live=True) # Target is 50/8 = 6.25
print(f"Init Bankroll: {app.risk_manager.risk_bankroll}")

# 1. Win a trade, revenue 10 (Net +5)
# Start 6.25 -> Bet 0? No, assume we started session.
# Let's say we bet 1.00. Risk drops to 5.25.
app.risk_manager.risk_bankroll = 5.25
app.live_broker.balance = 105.0 
# Revenue 2.00 (Win $1 profit)
app._add_risk_revenue(2.00)

# Expect: Risk 5.25 + 2.00 = 7.25. 
# Target is 6.25.
# STRICT Clamping: Risk > Target. Reset to 6.25. Skim 1.00.
