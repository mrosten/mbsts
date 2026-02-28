import os
import math
import time
from datetime import datetime
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, BalanceAllowanceParams
from .config import PRIVATE_KEY, PROXY_ADDRESS, CHAIN_ID, HOST

class SimBroker:
    def __init__(self, balance, log_file):
        self.balance = balance
        self.shares = {"UP": 0.0, "DOWN": 0.0}
        self.invested_this_window = 0.0
        self.revenue_this_window = 0.0
        self.log_file = log_file
        self.init_log()

    def init_log(self):
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w') as f:
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

    def log_trade(self, type_, side, amount, price, shares, context=None, note=""):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Context extraction
        ctx = context or {}
        sig_price = ctx.get('signal_price', price)
        slippage = price - sig_price
        rsi = ctx.get('rsi', 0)
        trend = ctx.get('trend', 'N/A')
        risk_bal = ctx.get('risk_bal', 0)
        main_bal = self.balance # Sim Main Balance
        
        # CSV: Event,Time,Type,Side,Amount,ExecPrice,SigPrice,Slippage,Shares,RSI,Trend,RiskBal,MainBal,Note
        line = (f"TRADE_EVENT,{ts},{type_},{side},{amount:.2f},{price:.5f},{sig_price:.5f},"
                f"{slippage:.5f},{shares:.2f},{rsi:.2f},{trend},{risk_bal:.2f},{main_bal:.2f},{note}")
        self.write_to_log(line)

    def log_snapshot(self, md, time_rem_str, is_live_active, live_bal, risk_bankroll):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mode = "LIVE" if is_live_active else "SIM"
        diff = md['btc_price'] - md['btc_open']
        
        line = (
            f"{ts},{mode},{self.balance:.2f},{live_bal:.2f},{risk_bankroll:.2f},"
            f"{time_rem_str},{md['btc_price']:.2f},{md['btc_open']:.2f},{diff:.2f},{md.get('btc_dyn_rng',0):.2f},"
            f"{md.get('btc_odds',0)},{md.get('trend_prob',0.5):.4f},{md.get('trend_score',3)},"
            f"{md.get('sling_signal','WAIT')},{md.get('poly_signal','N/A')},{md.get('cobra_signal','WAIT')},{md.get('flag_signal','WAIT')},{md.get('to_signal','N/A')},"
            f"{md.get('master_score',0)},{md.get('master_status','NEUTRAL')},"
            f"{md['up_price']:.3f},{md['down_price']:.3f},{md['up_bid']:.3f},{md['down_bid']:.3f},"
            f"{self.shares['UP']:.2f},{self.shares['DOWN']:.2f},-"
        )
        self.write_to_log(line)

    def buy(self, side, usd_amount, price, context=None, reason="Manual"):
        if usd_amount > self.balance: return False, "Insufficient Funds"
        shares = usd_amount / price
        self.balance -= usd_amount
        self.invested_this_window += usd_amount
        self.shares[side] += shares
        self.log_trade("BUY", side, usd_amount, price, shares, context=context, note=reason)
        return True, f"Bought {shares:.2f} {side} @ {price*100:.1f}¢ | Cost: ${usd_amount:.2f} ({reason})"

    def sell(self, side, price, reason="Manual"):
        shares = self.shares[side]
        if shares <= 0: return False, "No shares", 0.0
        revenue = shares * price
        self.balance += revenue
        self.revenue_this_window += revenue
        self.shares[side] = 0.0
        self.log_trade("SELL", side, revenue, price, shares, note=reason)
        return True, f"Sold {shares:.2f} {side} for ${revenue:.2f} ({reason})", revenue

    def settle_window(self, winning_side):
        winning_shares = self.shares[winning_side]
        payout = winning_shares * 1.00
        total_revenue = payout + self.revenue_this_window
        net_pnl = total_revenue - self.invested_this_window
        self.balance += payout
        self.log_trade("SETTLE", winning_side, payout, 1.00, winning_shares, note=f"Win: {winning_side} | PnL: {net_pnl:.2f}")
        self.shares = {"UP": 0.0, "DOWN": 0.0}
        self.invested_this_window = 0.0
        self.revenue_this_window = 0.0
        return payout, net_pnl

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

    def buy(self, side, usd_amount, price, token_id, context=None, reason="Manual"):
        if not self.client or not token_id: return False, "Client/Token Error"
        try:
            # MARKET ORDER (GUI Manual or standard Algo)
            # We use limit_price 0.99 to sweep the book instantly. This is identical to mbsts_sniper.py 
            # and ensures Polymarket processes it as a Taker/Market order, entirely bypassing the
            # "5 share minimum" limit rule that causes small manual buys to be rejected.
            limit_price = 0.99
            size = round(usd_amount / price, 2)
            
            
            o_args = OrderArgs(price=limit_price, size=size, side="BUY", token_id=token_id)
            r = self.client.post_order(self.client.create_order(o_args))
            if r.get("success") or r.get("orderID"):
                # Use usd_amount as the authoritative cost — we control what we sent.
                # Polymarket rarely returns a meaningful takingAmount immediately;
                # it can return dust-level values that would make the log show $0.00.
                actual_cost_usd = usd_amount
                actual_price = price  # The price we targeted

                # Only refine with takingAmount if Polymarket returns a plausible value
                # (must be >= 10% of what we sent, to guard against dust/zero responses)
                taking_val = r.get("takingAmount", 0)
                try: taking_val = float(taking_val)
                except: taking_val = 0.0
                if taking_val > 0:
                    refined_cost = taking_val / 10**6
                    if refined_cost >= usd_amount * 0.10:  # Sanity check: plausible fill
                        actual_cost_usd = refined_cost
                        actual_price = round(actual_cost_usd / size, 4) if size > 0 else price

                main_bal = self.update_balance()
                ctx = context or {}
                ctx['main_bal'] = main_bal

                self.sim_broker.log_trade("LIVE_BUY", side, actual_cost_usd, actual_price, size, context=ctx, note=reason)
                return True, f"✅ LIVE BUY {side} | Fill: {actual_price*100:.1f}¢ | Cost: ${actual_cost_usd:.2f} | Size: {size:.2f}"
            else:
                err = r.get('errorMsg') or str(r)
                self.sim_broker.write_to_log(f"LIVE_BUY_FAIL: {err}")
                return False, f"Live Fail: {err}"
        except Exception as e:
            return False, f"Err: {e}"

    def sell(self, side, token_id, limit_price=0.02, best_bid=None, reason="Manual"):
        if not self.client or not token_id: return False, "Client/Token Error", 0.0
        try:
            b = self.client.get_balance_allowance(BalanceAllowanceParams(asset_type="CONDITIONAL", token_id=token_id))
            shares = float(b.get("balance", 0)) / 10**6
            if shares <= 0.001: return False, "No Live Pos", 0.0
            
            size = math.floor(shares * 100) / 100
            if size <= 0: return False, "Size too small", 0.0

            val_log = f"Selling {size} @ Limit ${limit_price}"
            if best_bid: val_log += f" (Bid: ${best_bid})"
            self.sim_broker.write_to_log(f"DEBUG_SELL: {val_log}")

            o_args = OrderArgs(price=limit_price, size=size, side="SELL", token_id=token_id)
            r = self.client.post_order(self.client.create_order(o_args))
            if r.get("success") or r.get("orderID"):
                eff_price = limit_price
                if best_bid and best_bid > limit_price: eff_price = best_bid
                
                proceeds = size * eff_price
                msg = f"✅ LIVE SOLD {side}: {size:.2f} Shares @ ${eff_price:.2f} (Total: ${proceeds:.2f})"
                self.sim_broker.write_to_log(f"TRADE_EVENT,{datetime.now()},LIVE_SELL,{side},Shares:{size},Price:{eff_price},Total:{proceeds},{reason}")
                self.update_balance()
                return True, msg, proceeds
            else:
                err = r.get('errorMsg') or str(r)
                self.sim_broker.write_to_log(f"LIVE_SELL_FAIL: {err}")
                return False, f"Live Sell Fail: {err}", 0.0
        except Exception as e:
            return False, f"Sell Err: {e}", 0.0

class TradeExecutor:
    def __init__(self, sim_broker, live_broker, risk_manager):
        self.sim = sim_broker
        self.live = live_broker
        self.risk = risk_manager
        
    def execute_buy(self, is_live, side, amount, price, token_id=None, context=None, reason=""):
        if amount <= 0: return False, "Zero amount"
        if is_live:
            if not token_id: return False, "No Token ID"
            success, msg = self.live.buy(side, amount, price, token_id, context=context, reason=reason)
            return success, msg
        else:
            success, msg = self.sim.buy(side, amount, price, context=context, reason=reason)
            return success, msg

    def execute_sell(self, is_live, side, token_id, limit_price, best_bid, reason=""):
        if is_live:
             return self.live.sell(side, token_id, limit_price=limit_price, best_bid=best_bid, reason=reason)
        else:
             return self.sim.sell(side, limit_price, reason=reason)
