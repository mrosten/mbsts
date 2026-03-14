import os
import math
import time
from datetime import datetime
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, BalanceAllowanceParams

# Handle imports for both package and direct execution
try:
    from .config import PRIVATE_KEY, PROXY_ADDRESS, CHAIN_ID, HOST
except ImportError:
    # Running directly from vortex_pulse directory
    from config import PRIVATE_KEY, PROXY_ADDRESS, CHAIN_ID, HOST

class SimBroker:
    def __init__(self, balance, log_file):
        self.balance = balance
        self.shares = {"UP": 0.0, "DOWN": 0.0}
        self.pre_buy_shares = {"UP": 0.0, "DOWN": 0.0}
        self.invested_this_window = 0.0
        self.pre_buy_invested = 0.0
        self.revenue_this_window = 0.0
        self.log_file = log_file
        self.init_log()

    def init_log(self):
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w') as f:
                meta = (
                    f"# Polymarket Vortex Pulse V5 — Session Log\n"
                    f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"# Snapshot rows logged every ~15s. TRADE_EVENT rows on buy/sell/settle.\n"
                    f"#\n"
                    f"# SNAPSHOT FIELDS:\n"
                    f"#   Timestamp      — Wall-clock time of snapshot\n"
                    f"#   SimBal         — Simulated wallet balance (USD)\n"
                    f"#   LiveBal        — Live Polymarket wallet balance (USD)\n"
                    f"#   RiskBankroll   — Current risk-adjusted bankroll available for bets (USD)\n"
                    f"#   TimeRem        — Time remaining in current 5-min window (MM:SS)\n"
                    f"#   BTC_Price      — Live BTC/USD price from Kraken WS / Binance fallback\n"
                    f"#   BTC_Open       — BTC price at window open (Kraken REST)\n"
                    f"#   BTC_Diff       — BTC_Price minus BTC_Open (USD)\n"
                    f"#   BTC_Range      — Intra-window high-low price range (USD)\n"
                    f"#   Odds_Score     — Polymarket UP-DN bid skew in cents (+ve = UP favoured)\n"
                    f"#   Trend_4H       — 4-hour macro trend direction (S-UP/M-UP/W-UP/NEUTRAL/W-DOWN/M-DOWN/S-DOWN)\n"
                    f"#   Trend_1H       — 1-hour trend direction (same scale)\n"
                    f"#   RSI_1m         — 14-period RSI on 1-minute Binance candles\n"
                    f"#   ATR_5m         — 5-period Average True Range on 1-minute candles (USD)\n"
                    f"#   Sig_Slingshot  — Slingshot scanner signal this tick (WAIT/OFF/BET_UP/BET_DOWN)\n"
                    f"#   Sig_Cobra      — Cobra scanner signal this tick\n"
                    f"#   Sig_CoiledCobra— Coiled Cobra (CCO) scanner signal this tick\n"
                    f"#   Sig_Flag       — BullFlag scanner signal this tick\n"
                    f"#   Master_Score   — Net scanner consensus: (# UP signals) minus (# DOWN signals)\n"
                    f"#   Master_Status  — Aggregate direction: BUY_UP / BUY_DN / NEUTRAL\n"
                    f"#   Active_Scanners— Count of scanners firing a BET signal this tick\n"
                    f"#   UP_Price       — Polymarket UP option midpoint price\n"
                    f"#   DN_Price       — Polymarket DOWN option midpoint price\n"
                    f"#   UP_Bid         — Polymarket UP option best bid\n"
                    f"#   DN_Bid         — Polymarket DOWN option best bid\n"
                    f"#   Shares_UP      — Current UP shares held\n"
                    f"#   Shares_DN      — Current DOWN shares held\n"
                    f"#\n"
                    f"# TRADE_EVENT FIELDS (interleaved rows):\n"
                    f"#   TRADE_EVENT,Time,Type,Side,Amount,ExecPrice,SigPrice,Slippage,Shares,RSI,Trend,RiskBal,MainBal,Note\n"
                )
                header = (
                    "Timestamp,SimBal,LiveBal,RiskBankroll,"
                    "TimeRem,BTC_Price,BTC_Open,BTC_Diff,BTC_Range,"
                    "Odds_Score,Trend_4H,Trend_1H,RSI_1m,ATR_5m,"
                    "Sig_Slingshot,Sig_Cobra,Sig_CoiledCobra,Sig_Flag,"
                    "Master_Score,Master_Status,Active_Scanners,"
                    "UP_Price,DN_Price,UP_Bid,DN_Bid,"
                    "Shares_UP,Shares_DN"
                )
                f.write(meta + header + "\n")

    def write_to_log(self, text):
        # Access app for log settings if possible. 
        # PulseApp sets self.app = self on this broker during init.
        current_app = getattr(self, "app", None)
        if current_app and hasattr(current_app, "log_settings"):
            if not current_app.log_settings.get("main_csv", True):
                return

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
        diff = md['btc_price'] - md['btc_open']
        
        line = (
            f"{ts},{self.balance:.2f},{live_bal:.2f},{risk_bankroll:.2f},"
            f"{time_rem_str},{md['btc_price']:.2f},{md['btc_open']:.2f},{diff:.2f},{md.get('btc_dyn_rng',0):.2f},"
            f"{md.get('odds_score',0)},{md.get('trend_4h','NEUTRAL')},{md.get('trend_1h','NEUTRAL')},"
            f"{md.get('rsi_1m',50):.1f},{md.get('atr_5m',0):.2f},"
            f"{md.get('sling_signal','OFF')},{md.get('cobra_signal','OFF')},{md.get('coiled_cobra_signal','OFF')},{md.get('flag_signal','OFF')},"
            f"{md.get('master_score',0)},{md.get('master_status','NEUTRAL')},{md.get('active_scanners',0)},"
            f"{md['up_price']:.3f},{md['down_price']:.3f},{md['up_bid']:.3f},{md['down_bid']:.3f},"
            f"{self.shares['UP']:.2f},{self.shares['DOWN']:.2f}"
        )
        self.write_to_log(line)

    def buy(self, side, usd_amount, price, context=None, reason="Manual", is_pre_buy=False):
        if price <= 0 or price >= 1: return False, "Invalid price", 0.0, 0.0
        if usd_amount > self.balance: return False, "Insufficient Funds", 0.0, 0.0
        shares = usd_amount / price
        self.balance -= usd_amount
        
        if reason == "PreBuy_NextWindow":
            self.pre_buy_shares[side] += shares
            self.pre_buy_invested += usd_amount
        else:
            self.invested_this_window += usd_amount
            self.shares[side] += shares

        action = "BUY UP" if side == "UP" else "BUY DOWN"
        msg = f"BUY {side}: {shares:.2f} @ {price*100:.1f}c | ${usd_amount:.2f} [{reason}]"
        self.log_trade("BUY", side, usd_amount, price, shares, context=context, note=reason)
        return True, msg, shares, price

    def sell(self, side, price, reason="Manual", size=None):
        shares = self.shares[side] if size is None else size
        if shares <= 0: return False, "No shares", 0.0
        revenue = shares * price
        self.balance += revenue
        self.revenue_this_window += revenue
        
        if size is None:
            self.shares[side] = 0.0
        else:
            self.shares[side] -= size
            
        action = "SELL UP" if side == "UP" else "SELL DOWN"
        msg = f"SELL {side}: {shares:.2f} @ {price*100:.1f}c | ${revenue:.2f} [{reason}]"
        self.log_trade("SELL", side, revenue, price, shares, note=reason)
        return True, msg, revenue
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

    def promote_prebuy(self):
        """Transfers pre-buy shares/investments to the active window at the start of a new cycle."""
        for side in ["UP", "DOWN"]:
            self.shares[side] += self.pre_buy_shares[side]
        self.invested_this_window += self.pre_buy_invested
        
        # Reset buffers
        self.pre_buy_shares = {"UP": 0.0, "DOWN": 0.0}
        self.pre_buy_invested = 0.0

class LiveBroker:
    def __init__(self, sim_broker_ref):
        self.client = None
        self.sim_broker = sim_broker_ref 
        self.balance = 0.0
        # init_client() is now called by the App via a background worker to prevent startup hangs.

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

                action = "BUY UP" if side == "UP" else "BUY DOWN"
                msg = f"BUY {side}: {size:.2f} @ {actual_price*100:.1f}c | ${actual_cost_usd:.2f} [{reason}]"
                self.sim_broker.log_trade("LIVE_BUY", side, actual_cost_usd, actual_price, size, context=ctx, note=reason)
                return True, msg, size, actual_price
            else:
                err = r.get('errorMsg') or str(r)
                self.sim_broker.write_to_log(f"LIVE_BUY_FAIL: {err}")
                return False, f"Live Fail: {err}", 0.0, 0.0
        except Exception as e:
            return False, f"Err: {e}", 0.0, 0.0

    def place_limit_sell(self, side, token_id, size, limit_price):
        if not self.client or not token_id: return False, "Client Error"
        try:
            o_args = OrderArgs(price=limit_price, size=size, side="SELL", token_id=token_id)
            r = self.client.post_order(self.client.create_order(o_args))
            if r.get("success") or r.get("orderID"):
                return True, r.get("orderID")
            return False, r.get('errorMsg') or str(r)
        except Exception as e:
            return False, str(e)
            
    def cancel_limit_order(self, order_id):
        if not self.client or not order_id: return False, "No Client/Order ID"
        try:
            r = self.client.cancel_order(order_id)
            if r and (str(r).lower() == "canceled" or (isinstance(r, dict) and r.get("success"))):
                return True, "Canceled"
            # It might also return a list of canceled orders, etc.
            return True, "Cancel sent"
        except Exception as e:
            return False, str(e)

    def sell(self, side, token_id, limit_price=0.02, best_bid=None, reason="Manual", size=None):
        if not self.client or not token_id: return False, "Client/Token Error", 0.0
        try:
            if size is None:
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
                action = "SELL UP" if side == "UP" else "SELL DOWN"
                msg = f"SELL {side}: {size:.2f} @ {eff_price*100:.1f}c | ${proceeds:.2f} [{reason}]"
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
        if amount <= 0: return False, "Zero amount", 0.0, 0.0
        if is_live:
            if not token_id: return False, "No Token ID", 0.0, 0.0
            return self.live.buy(side, amount, price, token_id, context=context, reason=reason)
        else:
            return self.sim.buy(side, amount, price, context=context, reason=reason)

    def execute_sell(self, is_live, side, token_id, limit_price, best_bid, reason="", size=None):
        if is_live:
             return self.live.sell(side, token_id, limit_price=limit_price, best_bid=best_bid, reason=reason, size=size)
        else:
             return self.sim.sell(side, limit_price, reason=reason, size=size)
