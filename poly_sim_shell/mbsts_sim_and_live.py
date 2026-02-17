import os
import asyncio
import time
import json
import math
import csv
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

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

# --- BETTING CONFIG ---
AUTO_BET_PCT = 0.10  # Bet 10% of the dynamic bankroll per signal

# --- SCANNERS ---
class SlingshotScanner:
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, close_prices):
        if len(close_prices) < 20: return "WAIT"
        ma = sum(close_prices[-20:]) / 20
        curr = close_prices[-1]
        if self.triggered_signal == "UP (Reclaim)" and curr < ma: self.triggered_signal = None
        elif self.triggered_signal == "DOWN (Break)" and curr > ma: self.triggered_signal = None
        if self.triggered_signal: return self.triggered_signal
        p1, p2 = close_prices[-2], close_prices[-3]
        if curr > ma and (p1 < ma or p2 < ma): self.triggered_signal = "UP (Reclaim)"; return self.triggered_signal
        if curr < ma and (p1 > ma or p2 > ma): self.triggered_signal = "DOWN (Break)"; return self.triggered_signal
        return "WAIT"

class PolyOddsTrendScanner:
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, current_price, open_price, poly_up, poly_down, trend_prob):
        if self.triggered_signal == 'UP (Poly+Trend)' and current_price < open_price: self.triggered_signal = None
        elif self.triggered_signal == 'DOWN (Poly+Trend)' and current_price > open_price: self.triggered_signal = None
        if self.triggered_signal: return self.triggered_signal
        if poly_up >= 0.55 and poly_down <= 0.45 and trend_prob >= 0.5 and current_price > open_price:
            self.triggered_signal = 'UP (Poly+Trend)'; return self.triggered_signal
        if poly_down >= 0.55 and poly_up <= 0.45 and trend_prob < 0.5 and current_price < open_price:
            self.triggered_signal = 'DOWN (Poly+Trend)'; return self.triggered_signal
        return 'WAIT'

class CobraScanner:
    def __init__(self): self.triggered = None
    def reset(self): self.triggered = None
    def analyze(self, closes_60m, current_price, elapsed):
        if len(closes_60m) < 20: return "WAIT (Data)"
        slice_ = closes_60m[-20:]; sma = sum(slice_) / 20
        std = (sum((x - sma) ** 2 for x in slice_) / 20) ** 0.5
        if self.triggered == "UP (Explosive)" and current_price < sma: self.triggered = None
        elif self.triggered == "DOWN (Explosive)" and current_price > sma: self.triggered = None
        if self.triggered: return self.triggered
        if elapsed > 300: return "WAIT (Time)"
        if current_price > sma + (2 * std): self.triggered = "UP (Explosive)"; return self.triggered
        if current_price < sma - (2 * std): self.triggered = "DOWN (Explosive)"; return self.triggered
        return "WAIT"

class BullFlagScanner:
    def __init__(self): self.triggered = None
    def reset(self): self.triggered = None
    def analyze(self, closes_60m):
        if self.triggered: return self.triggered
        if len(closes_60m) < 20: return "WAIT"
        window = closes_60m[-15:]
        lows = [window[i] for i in range(1, len(window) - 1) if window[i] <= window[i-1] and window[i] <= window[i+1]]
        if len(lows) >= 3 and all(lows[i] < lows[i+1] for i in range(len(lows)-1)):
            if window[-1] >= (max(window) * 0.9995): self.triggered = "UP (Staircase)"; return self.triggered
        return "WAIT"

class TrendOddsScanner:
    def __init__(self): self.triggered = None
    def reset(self): self.triggered = None
    def analyze(self, trend_prob, odds, curr, open_):
        is_up = curr >= open_
        if self.triggered == "UP (Trend+Odds)" and not is_up: self.triggered = None
        elif self.triggered == "DOWN (Trend+Odds)" and is_up: self.triggered = None
        if self.triggered: return self.triggered
        trend_supports_up = trend_prob > 0.55
        trend_supports_down = trend_prob < 0.45
        high_odds = odds >= 3
        if is_up:
            if high_odds or (trend_supports_up and odds >= 2):
                self.triggered = "UP (Trend+Odds)"; return self.triggered
        else:
            if high_odds or (trend_supports_down and odds >= 2):
                self.triggered = "DOWN (Trend+Odds)"; return self.triggered
        return "WAIT"

def calculate_master_signal(sling, poly, cobra, flag, to_sig, up_price):
    score = 0
    ignore_up = up_price < 0.20; ignore_down = up_price > 0.80 
    if "UP" in cobra and not ignore_up: score += 2
    elif "DOWN" in cobra and not ignore_down: score -= 2
    for sig in [sling, flag, poly, to_sig]:
        if "UP" in sig and not ignore_up: score += 1
        elif "DOWN" in sig and not ignore_down: score -= 1
    status = "NEUTRAL"
    if score >= 3: status = "STRONG BUY UP"
    elif score <= -3: status = "STRONG BUY DOWN"
    elif score > 0: status = "LEAN UP"
    elif score < 0: status = "LEAN DOWN"
    return score, status

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
        return True, f"Bought {shares:.2f} {side} ({reason})"

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
                return True, f"✅ LIVE BUY {side} | {price*100:.1f}¢ | Pot. Win: ${size:.2f}"
            else:
                return False, f"Live Fail: {r.get('errorMsg')}"
        except Exception as e:
            return False, f"Err: {e}"

    def sell(self, side, token_id, limit_price=0.02, reason="Manual"):
        if not self.client or not token_id: return False, "Client/Token Error"
        try:
            b = self.client.get_balance_allowance(BalanceAllowanceParams(asset_type="CONDITIONAL", token_id=token_id))
            shares = float(b.get("balance", 0)) / 10**6
            if shares <= 0.001: return False, "No Live Pos"
            
            # FIX: Round DOWN
            size = math.floor(shares * 100) / 100
            if size <= 0: return False, "Size too small"

            self.sim_broker.write_to_log(f"DEBUG_SELL: Found {shares} shares. Selling {size} @ ${limit_price}")

            o_args = OrderArgs(price=limit_price, size=size, side="SELL", token_id=token_id)
            r = self.client.post_order(self.client.create_order(o_args))
            if r.get("success") or r.get("orderID"):
                self.sim_broker.write_to_log(f"TRADE_EVENT,{datetime.now()},LIVE_SELL,{side},Shares:{shares},{reason}")
                self.update_balance()
                return True, f"✅ LIVE SOLD {side}: {size:.2f} Shares"
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
class PolySimApp(App):
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
    
    /* INPUTS ON TOP ROW */
    #input_row { height: 3; align: center middle; layout: horizontal; padding: 0; margin-bottom: 1; border-bottom: solid $primary; }
    #inp_amount { width: 20; height: 1; margin: 0 2; background: $surface; border: none; color: #ffffff; text-align: center; }
    #inp_risk_alloc { width: 20; height: 1; margin: 0 2; background: $surface; border: none; color: #ff9900; text-align: center; }
    
    /* BUTTONS ON SECOND ROW */
    #button_row { height: 3; align: center middle; layout: horizontal; padding: 0; margin-bottom: 1; }
    Button { height: 1; min-width: 12; margin: 0 1; border: none; }
    .btn_buy_up { background: #006600; color: #ffffff; }
    .btn_buy_down { background: #660000; color: #ffffff; }
    .btn_sell_up { background: #b38600; color: #ffffff; }
    .btn_sell_down { background: #b34b00; color: #ffffff; }

    #checkbox_container { height: auto; border-bottom: double $primary; margin-bottom: 1; }
    .algo_row { align: center middle; height: 3; layout: horizontal; padding: 0 1; }
    .settings_row { align: center middle; height: 3; layout: horizontal; padding: 0 1; background: #222222; }
    .live_row { align: center middle; height: 3; background: #220000; padding: 0 1; border-top: solid #440000; }
    Checkbox { margin-right: 2; }
    #cb_live { color: #ff0000; text-style: bold; width: auto; }
    RichLog { height: 1fr; min-height: 5; background: #111111; color: #eeeeee; }
    """

    def __init__(self, sim_broker, live_broker):
        super().__init__()
        self.sim_broker = sim_broker
        self.live_broker = live_broker
        self.market_data = {
            "up_id": None, "down_id": None, 
            "up_price": 0.5, "down_price": 0.5, "up_bid": 0.5, "down_bid": 0.5,
            "btc_price": 0.0, "btc_open": 0.0, "btc_dyn_rng": 0.0, 
            "btc_odds": 0, "trend_score": 3, "trend_prob": 0.5,
            "sling_signal": "WAIT", "poly_signal": "WAIT", "cobra_signal": "WAIT", 
            "flag_signal": "WAIT", "to_signal": "WAIT",
            "master_score": 0, "master_status": "NEUTRAL",
            "start_ts": 0
        }
        self.slingshot = SlingshotScanner()
        self.poly_scanner = PolyOddsTrendScanner()
        self.cobra = CobraScanner()
        self.bullflag = BullFlagScanner()
        self.trend_odds = TrendOddsScanner()
        self.window_bets = set() 
        self.app_start_time = time.time()
        self.time_rem_str = "05:00"
        
        # Risk Management State
        self.dynamic_risk_cap = 0.0
        self.risk_cap_initialized = False
        self.live_spent_this_window = 0.0

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Label(f"SIM | Bal: ${self.sim_broker.balance:.2f}", id="header_stats"),
            Label(f" | RUN: 00:00:00", id="lbl_runtime", classes="run_time"),
            Label(" | 5M WIN: ", classes="timer_text"),
            Label("00:00", id="lbl_timer_big", classes="timer_text"),
            id="top_bar"
        )
        yield Horizontal(
            Container(
                Label("$0.00", id="p_btc", classes="price_val"),
                Label("Sling: WAIT", id="p_sling", classes="price_sub"),
                Label("NEUTRAL", id="p_master", classes="master_neu"),
                Label("Op: $0", id="p_btc_open", classes="price_sub"),
                Label("Poly: WAIT", id="p_poly", classes="price_sub"),
                Label("Odds: -/5", id="p_btc_odds", classes="price_sub"),
                Label("Diff: $0", id="p_btc_diff", classes="price_sub"),
                Label("Cobra: WAIT", id="p_cobra", classes="price_sub"),
                Label("Trend: -", id="p_btc_trend", classes="price_sub"),
                Label("Rng: $0", id="p_btc_rng", classes="price_sub"),
                Label("Flag: WAIT", id="p_flag", classes="price_sub"),
                Label("TO: WAIT", id="p_to", classes="price_sub"), 
                id="card_btc", classes="price_card"
            ),
            Vertical(
                Vertical(Label("UP", classes="price_sub", id="lbl_up_static"), Label("0.0¢", id="p_up", classes="price_val"), id="card_up", classes="mini_card"),
                Vertical(Label("DN", classes="price_sub", id="lbl_down_static"), Label("0.0¢", id="p_down", classes="price_val"), id="card_down", classes="mini_card"),
                classes="right_col"
            ),
            classes="row_main"
        )
        
        # --- INPUTS ROW ---
        yield Container(
            Input(placeholder="Manual Bet $", id="inp_amount"),
            Input(placeholder="Starting Risk Bankroll", id="inp_risk_alloc"),
            id="input_row"
        )

        # --- BUTTONS ROW ---
        yield Container(
            Button("BUY UP", id="btn_buy_up", classes="btn_buy_up"), 
            Button("BUY DN", id="btn_buy_down", classes="btn_buy_down"),
            Button("SELL UP", id="btn_sell_up", classes="btn_sell_up"), 
            Button("SELL DN", id="btn_sell_down", classes="btn_sell_down"),
            id="button_row"
        )
        
        yield Vertical(
            Horizontal(
                Checkbox("Sling", value=True, id="cb_sling"),
                Checkbox("Poly", value=True, id="cb_poly"),
                Checkbox("Cobra", value=True, id="cb_cobra"),
                Checkbox("Flag", value=True, id="cb_flag"),
                Checkbox("TO", value=True, id="cb_to"),
                classes="algo_row"
            ),
            # --- SETTINGS ROW ---
            Horizontal(
                Checkbox("Strong Only", value=False, id="cb_strong"),
                Checkbox("1 Trade Max", value=True, id="cb_one_trade"),
                classes="settings_row"
            ),
            Horizontal(
                Checkbox("ENABLE LIVE TRADING", value=False, id="cb_live"),
                classes="live_row"
            ),
            id="checkbox_container"
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

    @on(Checkbox.Changed, "#cb_live")
    def on_live_toggle(self, event: Checkbox.Changed):
        if event.value: 
            self.log_msg("[bold red]LIVE MODE ENABLED! All Algos deselected for safety.[/]")
            for cid in ["#cb_sling", "#cb_poly", "#cb_cobra", "#cb_flag", "#cb_to"]:
                self.query_one(cid).value = False
            self.log_msg("[yellow]Please check the algos you want to run live.[/]")
            
            # Update Risk Bankroll for Live
            lb = self.live_broker.balance
            if lb > 0:
                self.query_one("#inp_risk_alloc").value = f"{lb/8:.2f}"
                self.risk_cap_initialized = False # Force re-init
                self.log_msg(f"[cyan]Risk Bankroll updated to Live 1/8th: ${lb/8:.2f}[/]")
        else:
            # Revert to Sim Risk (Full Balance)
            sb = self.sim_broker.balance
            self.query_one("#inp_risk_alloc").value = f"{sb:.2f}"
            self.risk_cap_initialized = False
            self.log_msg(f"[cyan]Risk Bankroll reverted to Sim Balance: ${sb:.2f}[/]")

    @on(Checkbox.Changed)
    def on_any_checkbox(self, event: Checkbox.Changed):
        # Build list of active algos
        algos = []
        if self.query_one("#cb_sling").value: algos.append("Sling")
        if self.query_one("#cb_poly").value: algos.append("Poly")
        if self.query_one("#cb_cobra").value: algos.append("Cobra")
        if self.query_one("#cb_flag").value: algos.append("Flag")
        if self.query_one("#cb_to").value: algos.append("TO")
        
        settings = []
        if self.query_one("#cb_strong").value: settings.append("StrongOnly")
        if self.query_one("#cb_one_trade").value: settings.append("1TradeMax")
        if self.query_one("#cb_live").value: settings.append("LIVE")

        algo_str = ", ".join(algos) if algos else "None"
        sett_str = ", ".join(settings) if settings else "Standard"
        
        self.log_msg(f"[cyan]Strategy Update: Algos=[{algo_str}] | Settings=[{sett_str}][/]")

    def log_msg(self, msg):
        self.query_one(RichLog).write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def dump_state_log(self):
        is_live = self.query_one("#cb_live").value
        self.sim_broker.log_snapshot(self.market_data, self.time_rem_str, is_live, self.live_broker.balance, self.dynamic_risk_cap)

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
        if self.risk_cap_initialized:
            cap_display = f" (Bankroll: ${self.dynamic_risk_cap:.2f})"
            self.query_one("#inp_risk_alloc").value = f"{self.dynamic_risk_cap:.2f}"

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
            now = datetime.now(timezone.utc); floor = (now.minute // 5) * 5
            ts_start = int(now.replace(minute=floor, second=0, microsecond=0).timestamp())
            
            # --- INITIALIZE RISK CAP (BANKROLL) ---
            if not self.risk_cap_initialized:
                inp_val = self.query_one("#inp_risk_alloc").value
                try:
                    self.dynamic_risk_cap = float(inp_val)
                    self.risk_cap_initialized = True
                    self.log_msg(f"[cyan]Risk Bankroll Initialized: ${self.dynamic_risk_cap:.2f}[/]")
                except: pass

            # --- SETTLEMENT LOGIC ---
            if self.market_data["start_ts"] != 0 and ts_start != self.market_data["start_ts"]:
                last_price = self.market_data["btc_price"]
                last_open = self.market_data["btc_open"]
                winner = "UP" if last_price >= last_open else "DOWN"
                
                sim_payout, sim_pnl = self.sim_broker.settle_window(winner)
                
                is_live = self.query_one("#cb_live").value
                if self.risk_cap_initialized:
                    if not is_live:
                        self.dynamic_risk_cap += sim_pnl

                self.log_msg(f"[bold yellow]SETTLED:[/]{winner}")
                self.live_spent_this_window = 0.0
                
                self.update_balance_ui()
                self.slingshot.reset(); self.poly_scanner.reset()
                self.cobra.reset(); self.bullflag.reset(); self.trend_odds.reset()
                self.window_bets.clear()
            
            self.market_data["start_ts"] = ts_start
            elapsed = int(now.timestamp()) - ts_start
            rem_min = max(1, min(5, (300 - elapsed + 59) // 60))
            slug = f"btc-updown-5m-{ts_start}"
            
            # Fetch Shares
            curr_shares_up = self.sim_broker.shares["UP"]
            curr_shares_down = self.sim_broker.shares["DOWN"]

            def get_data(app_ref, s_up, s_down):
                s = requests.Session()
                d = {"curr":0,"open":0,"rng":0,"odds":1,"t_score":3,"t_prob":0.5,
                     "sling":"WAIT","poly":"WAIT","cobra":"WAIT","flag":"WAIT", "to_sig":"WAIT"}
                
                try: d["curr"] = float(app_ref.chainlink_contract.functions.latestAnswer().call()) / 10**8
                except: 
                    try: d["curr"] = float(s.get("https://api.binance.com/api/v3/ticker/price", params={"symbol":"BTCUSDC"}).json()["price"])
                    except: pass
                try:
                    k = s.get("https://api.binance.com/api/v3/klines", params={"symbol":"BTCUSDC","interval":"1m","limit":90}).json()
                    start_ms = ts_start * 1000
                    for x in k: 
                        if int(x[0]) == start_ms: d["open"] = float(x[1]); break
                    if d["open"] == 0 and k: d["open"] = float(k[-1][1])
                    hist = k[:-1]; closes = [float(x[4]) for x in k]
                    if len(hist) > rem_min:
                        rec = hist[-60:]; rngs = [max(float(x[2]) for x in rec[i:i+rem_min]) - min(float(x[3]) for x in rec[i:i+rem_min]) for i in range(len(rec)-rem_min+1)]
                        if rngs: d["rng"] = sum(rngs)/len(rngs)
                    d["sling"] = app_ref.slingshot.analyze(closes)
                    d["cobra"] = app_ref.cobra.analyze(closes, d["curr"], elapsed)
                    d["flag"] = app_ref.bullflag.analyze(closes)
                except: pass
                try:
                    tk = s.get("https://api.binance.com/api/v3/klines", params={"symbol":"BTCUSDC","interval":"5m","limit":35}).json()
                    c = [float(x[4]) for x in tk]
                    if len(c) >= 5:
                        lr = [math.log(c[i]/c[i-1]) for i in range(1, len(c))]
                        mu = lr[0]; var = 0; lam = 0.94
                        for r in lr[1:]: old=mu; mu=lam*old+(1-lam)*r; var=lam*var+(1-lam)*(r-old)**2
                        z = mu/math.sqrt(var) if var>0 else 0
                        d["t_prob"] = 0.5*(1+math.erf(z/1.414))
                        p=d["t_prob"]; d["t_score"] = 5 if p>=0.9 else (4 if p>=0.7 else (2 if p<=0.1 else (1 if p<=0.3 else 3)))
                except: pass
                try:
                    diff = abs(d["curr"] - d["open"])
                    if d["rng"] > 0:
                        ratio = diff / d["rng"]
                        if ratio >= 2.0: d["odds"] = 5
                        elif ratio >= 1.5: d["odds"] = 4
                        elif ratio >= 1.0: d["odds"] = 3
                        elif ratio >= 0.5: d["odds"] = 2
                        else: d["odds"] = 1
                    else: d["odds"] = 1
                except: d["odds"] = 1
                try:
                    m = s.get(f"https://gamma-api.polymarket.com/markets/slug/{slug}").json()
                    ids = json.loads(m["clobTokenIds"]); outs = json.loads(m["outcomes"])
                    uid = ids[0] if "Up" in outs[0] else ids[1]; did = ids[1] if uid==ids[0] else ids[0]
                    up_ask = float(s.get("https://clob.polymarket.com/price", params={"token_id":uid,"side":"buy"}).json().get("price",0))
                    down_ask = float(s.get("https://clob.polymarket.com/price", params={"token_id":did,"side":"buy"}).json().get("price",0))
                    up_bid = float(s.get("https://clob.polymarket.com/price", params={"token_id":uid,"side":"sell"}).json().get("price",0))
                    down_bid = float(s.get("https://clob.polymarket.com/price", params={"token_id":did,"side":"sell"}).json().get("price",0))
                    
                    d["poly"] = app_ref.poly_scanner.analyze(d["curr"], d["open"], up_ask, down_ask, d["t_prob"])
                    d["to_sig"] = app_ref.trend_odds.analyze(d["t_prob"], d["odds"], d["curr"], d["open"])
                    return uid, did, up_ask, down_ask, up_bid, down_bid, d
                except: return None, None, 0, 0, 0, 0, d

            res = await asyncio.to_thread(get_data, self, curr_shares_up, curr_shares_down)
            d = res[6]
            score, status = calculate_master_signal(d["sling"], d["poly"], d["cobra"], d["flag"], d["to_sig"], res[2])

            self.market_data.update({
                "up_id":res[0], "down_id":res[1],
                "up_price":res[2], "down_price":res[3], "up_bid":res[4], "down_bid":res[5],
                "btc_price":d["curr"], "btc_open":d["open"], "btc_dyn_rng":d["rng"], "btc_odds": d["odds"],
                "trend_score":d["t_score"], "trend_prob":d["t_prob"],
                "sling_signal":d["sling"], "poly_signal":d["poly"], "cobra_signal":d["cobra"], 
                "flag_signal":d["flag"], "to_signal":d["to_sig"],
                "master_score": score, "master_status": status
            })

            # --- AUTO TRADING ---
            active_scanners = {
                "Sling": d["sling"], "Poly": d["poly"], "Cobra": d["cobra"],
                "Flag": d["flag"], "TrendOdds": d["to_sig"]
            }
            cb_map = {
                "Sling": "#cb_sling", "Poly": "#cb_poly", "Cobra": "#cb_cobra",
                "Flag": "#cb_flag", "TrendOdds": "#cb_to"
            }

            time_since_start = time.time() - self.app_start_time
            if time_since_start > 5:
                # --- CHECK: 1 TRADE PER WINDOW ---
                if self.query_one("#cb_one_trade").value:
                    if len(self.window_bets) >= 1:
                        pass # Skipping loop entry for trading
                    else:
                        self._process_scanners(active_scanners, cb_map)
                else:
                    self._process_scanners(active_scanners, cb_map)
            
            self.update_balance_ui()
            self.update_sell_buttons()

            # --- EXIT AT LAST POSSIBLE MOMENT ---
            if elapsed > 285:
                self._run_last_second_exit()

            md = self.market_data
            self.query_one("#p_up").update(f"{md['up_price']*100:.1f}¢")
            self.query_one("#p_down").update(f"{md['down_price']*100:.1f}¢")
            self.query_one("#p_btc").update(f"${md['btc_price']:,.0f}")
            self.query_one("#p_btc_open").update(f"Op: ${md['btc_open']:,.0f}")
            self.query_one("#p_btc_rng").update(f"Rng: ${md['btc_dyn_rng']:.0f}")
            diff = md['btc_price'] - md['btc_open']
            dl = self.query_one("#p_btc_diff"); dl.update(f"{'+' if diff>=0 else '-'}${abs(diff):.1f}"); dl.classes = "diff_green price_sub" if diff>=0 else "diff_red price_sub"
            tl = self.query_one("#p_btc_trend"); tl.update(f"Trend: {md['trend_score']} ({md['trend_prob']:.0%})")
            ol = self.query_one("#p_btc_odds"); ol.update(f"Odds: {md['btc_odds']}/5")
            def set_sig(lid, sig):
                val = sig if sig else "WAIT"
                lbl = self.query_one(lid); lbl.update(f"{lid.split('_')[1].capitalize().replace('Btc_','').replace('Poly_','Poly').replace('To','TO')}: {val}")
                lbl.classes = "sig_up price_sub" if "UP" in val else "sig_down price_sub" if "DOWN" in val else "sig_wait price_sub"
            set_sig("#p_sling", md['sling_signal']); set_sig("#p_poly", md['poly_signal'])
            set_sig("#p_cobra", md['cobra_signal']); set_sig("#p_flag", md['flag_signal'])
            set_sig("#p_to", md['to_signal'])
            ms_lbl = self.query_one("#p_master"); ms_lbl.update(f"{md['master_score']} ({md['master_status']})")
            card = self.query_one("#card_btc")
            card.classes = "price_card border_green" if score >= 3 else "price_card border_red" if score <= -3 else "price_card"
            ms_lbl.classes = "master_up" if score >= 3 else "master_down" if score <= -3 else "master_neu"
            self.update_sell_buttons()
        except Exception: pass

    def _process_scanners(self, active_scanners, cb_map):
        for name, sig in active_scanners.items():
            cb_id = cb_map.get(name)
            if cb_id:
                is_enabled = self.query_one(cb_id).value
                if not is_enabled: continue 
            
            # --- CHECK: 1 TRADE PER WINDOW (IN-LOOP) ---
            if self.query_one("#cb_one_trade").value and len(self.window_bets) >= 1:
                return

            if not sig or sig == "WAIT": continue
            
            # --- CHECK: STRONG ONLY ---
            if self.query_one("#cb_strong").value:
                is_strong_master = "STRONG" in self.market_data["master_status"]
                is_high_odds = self.market_data["btc_odds"] >= 3
                if not (is_strong_master or is_high_odds):
                    continue

            bet_side = "UP" if "UP" in sig else "DOWN" if "DOWN" in sig else None
            if not bet_side: continue
            if any(b.startswith(f"{name}_") for b in self.window_bets): continue
            
            price = self.market_data["up_price"] if bet_side == "UP" else self.market_data["down_price"]
            if price < 0.20 or price > 0.95: continue
            
            # --- STRICT PRICE FILTER: $25 DIFF REQUIRED ---
            # Must be at least $25 diff in direction of bet
            diff = self.market_data["btc_price"] - self.market_data["btc_open"]
            if bet_side == "UP" and diff < 25: continue
            if bet_side == "DOWN" and diff > -25: continue

            is_live = self.query_one("#cb_live").value
            
            base_bal = 0.0
            if self.risk_cap_initialized:
                base_bal = self.dynamic_risk_cap
            else:
                base_bal = self.live_broker.balance if is_live else self.sim_broker.balance
            
            # --- STRICT RISK GUARD CLAUSE ---
            if self.risk_cap_initialized:
                if self.dynamic_risk_cap < 1.0:
                    continue 

            dynamic_amount = base_bal * AUTO_BET_PCT
            if dynamic_amount < 1.0: dynamic_amount = 1.0
            
            if self.risk_cap_initialized and dynamic_amount > self.dynamic_risk_cap:
                continue

            trade_success = False
            if is_live:
                    token_id = self.market_data["up_id"] if bet_side == "UP" else self.market_data["down_id"]
                    if dynamic_amount <= self.live_broker.balance and token_id:
                        algo_note = f"Algo: {name} | Sig: {sig}"
                        success, msg = self.live_broker.buy(bet_side, dynamic_amount, price, token_id, reason=algo_note)
                        if success:
                            self.log_msg(f"[bold red]LIVE BET {name.upper()}: {msg}[/]")
                            bet_id = f"{name}_{bet_side}"; self.window_bets.add(bet_id)
                            if self.risk_cap_initialized: self.dynamic_risk_cap -= dynamic_amount
                            self.live_spent_this_window += dynamic_amount
                            trade_success = True
            else:
                can_trade_sim = False
                if self.risk_cap_initialized:
                     if dynamic_amount <= self.dynamic_risk_cap: can_trade_sim = True
                elif dynamic_amount <= self.sim_broker.balance:
                     can_trade_sim = True

                if can_trade_sim:
                    algo_note = f"Algo: {name} | Sig: {sig}"
                    success, msg = self.sim_broker.buy(bet_side, dynamic_amount, price, reason=algo_note)
                    if success:
                        self.log_msg(f"[bold magenta]SIM {name.upper()}: {msg}[/]")
                        bet_id = f"{name}_{bet_side}"; self.window_bets.add(bet_id)
                        if self.risk_cap_initialized: self.dynamic_risk_cap -= dynamic_amount
                        trade_success = True
            
            # FAST BREAK IF ONE TRADE ENFORCED AND SUCCESSFUL
            if trade_success and self.query_one("#cb_one_trade").value:
                return

    def _run_last_second_exit(self):
        is_live = self.query_one("#cb_live").value
        has_pos_up = False
        has_pos_down = False
        
        if not is_live:
            if self.sim_broker.shares["UP"] > 0: has_pos_up = True
            if self.sim_broker.shares["DOWN"] > 0: has_pos_down = True
        else:
            has_pos_up = True 
            has_pos_down = True

        if has_pos_up:
            side = "UP"
            if is_live:
                token_id = self.market_data["up_id"]
                if token_id:
                    success, msg = self.live_broker.sell(side, token_id, reason="Last Second Exit")
                    if success: 
                        self.log_msg(f"[bold red]⏱ LIVE FINAL EXIT: {msg}[/]")
                        try:
                            rev = float(msg.split("Shares")[0].split(":")[-1].strip()) * 0.99 
                            if self.risk_cap_initialized: self.dynamic_risk_cap += rev
                        except: pass
            else:
                if self.sim_broker.shares["UP"] > 0:
                    success, msg = self.sim_broker.sell(side, 0.99, reason="Last Second Exit")
                    if success:
                        self.log_msg(f"[bold green]⏱ SIM FINAL EXIT: {msg}[/]")
                        if self.risk_cap_initialized: 
                            rev = float(msg.split("$")[1])
                            self.dynamic_risk_cap += rev

        if has_pos_down:
            side = "DOWN"
            if is_live:
                token_id = self.market_data["down_id"]
                if token_id:
                    success, msg = self.live_broker.sell(side, token_id, reason="Last Second Exit")
                    if success: 
                        self.log_msg(f"[bold red]⏱ LIVE FINAL EXIT: {msg}[/]")
                        try:
                            rev = float(msg.split("Shares")[0].split(":")[-1].strip()) * 0.99
                            if self.risk_cap_initialized: self.dynamic_risk_cap += rev
                        except: pass
            else:
                if self.sim_broker.shares["DOWN"] > 0:
                    success, msg = self.sim_broker.sell(side, 0.99, reason="Last Second Exit")
                    if success:
                        self.log_msg(f"[bold green]⏱ SIM FINAL EXIT: {msg}[/]")
                        if self.risk_cap_initialized:
                            rev = float(msg.split("$")[1])
                            self.dynamic_risk_cap += rev

    def update_timer(self):
        if self.market_data["start_ts"]: 
            rem = max(0, 300 - int(time.time() - self.market_data["start_ts"]))
            m, s = divmod(rem, 60)
            self.time_rem_str = f"{m:02d}:{s:02d}"
            self.query_one("#lbl_timer_big").update(self.time_rem_str)
        
        run_sec = int(time.time() - self.app_start_time)
        rh, rem = divmod(run_sec, 3600)
        rm, rs = divmod(rem, 60)
        self.query_one("#lbl_runtime").update(f" | RUN: {rh:02d}:{rm:02d}:{rs:02d}")

    @on(Input.Submitted, "#inp_risk_alloc")
    def on_risk_update(self, event: Input.Submitted):
        try:
            new_val = float(event.value)
            self.dynamic_risk_cap = new_val
            self.risk_cap_initialized = True
            self.log_msg(f"[bold cyan]Risk Bankroll Manually Updated: ${new_val:.2f}[/]")
        except ValueError:
            self.log_msg("[red]Invalid Risk Amount entered.[/]")

    async def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if "buy" in bid: await self.trigger_buy("UP" if "up" in bid else "DOWN")
        else: await self.trigger_sell_all("UP" if "up" in bid else "DOWN")

    async def trigger_buy(self, side):
        val_str = self.query_one("#inp_amount").value
        try: val = float(val_str)
        except: return
        is_live = self.query_one("#cb_live").value
        price = self.market_data["up_price"] if side == "UP" else self.market_data["down_price"]
        
        if is_live:
             token_id = self.market_data["up_id"] if side == "UP" else self.market_data["down_id"]
             if token_id:
                success, msg = self.live_broker.buy(side, val, price, token_id, reason="Manual Live")
                if success: 
                    self.log_msg(f"[bold red]{msg}[/]")
                    if self.risk_cap_initialized: self.dynamic_risk_cap -= val
                else: self.log_msg(f"[red]LIVE FAIL: {msg}[/]")
        else:
            success, msg = self.sim_broker.buy(side, val, price, reason="Manual Sim")
            if success: 
                self.log_msg(f"[green]{msg}[/]")
                if self.risk_cap_initialized: self.dynamic_risk_cap -= val
            else: self.log_msg(f"[red]{msg}[/]")
            
        self.update_balance_ui(); self.update_sell_buttons()

    async def trigger_sell_all(self, side):
        is_live = self.query_one("#cb_live").value
        if is_live:
             token_id = self.market_data["up_id"] if side == "UP" else self.market_data["down_id"]
             if token_id:
                success, msg = self.live_broker.sell(side, token_id, reason="Manual Live Sell")
                if success: 
                    self.log_msg(f"[bold red]{msg}[/]")
                    try:
                        rev = float(msg.split("Shares")[0].split(":")[-1].strip()) * 0.99 
                        if self.risk_cap_initialized: self.dynamic_risk_cap += rev
                    except: pass
                else: self.log_msg(f"[red]LIVE SELL FAIL: {msg}[/]")
        else:
            price = self.market_data["up_bid"] if side == "UP" else self.market_data["down_bid"]
            success, msg = self.sim_broker.sell(side, price)
            if success: 
                self.log_msg(f"[green]{msg}[/]")
                try:
                    rev = float(msg.split("$")[1])
                    if self.risk_cap_initialized: self.dynamic_risk_cap += rev
                except: pass
            else: self.log_msg(f"[red]{msg}[/]")
        self.update_balance_ui(); self.update_sell_buttons()

if __name__ == "__main__":
    import sys
    print("\n=== POLYMARKET SIMULATOR & LIVE BOT SETUP ===")
    print(f"Running with Python: {sys.executable}")
    try: start_bal = float(input("Enter Initial SIM Balance ($): ").strip() or "100.00")
    except: start_bal = 100.00
    default_log = f"sim_log_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    log_file = input(f"Enter Log Filename (default: {default_log}): ").strip()
    if not log_file: log_file = default_log
    if not log_file.endswith(".csv"): log_file += ".csv"
        
    print(f"Starting... Logging to: {log_file}")
    time.sleep(1)
    
    sim_broker = SimBroker(start_bal, log_file)
    live_broker = LiveBroker(sim_broker) # Pass sim broker to share log file
    
    app = PolySimApp(sim_broker, live_broker)
    app.run()
