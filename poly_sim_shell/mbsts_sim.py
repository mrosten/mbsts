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
from textual.widgets import Header, Footer, Input, Button, RichLog, Label
from textual.screen import ModalScreen
from textual import work

load_dotenv()

# --- CONFIG ---
POLYGON_RPC = os.getenv("POLYGON_RPC", "https://polygon-rpc.com") 
CHAINLINK_BTC_FEED = "0xc907E116054710363050Cce340695D7946aaBf47"
CHAINLINK_ABI = '[{"inputs":[],"name":"latestAnswer","outputs":[{"internalType":"int256","name":"","type":"int256"}],"stateMutability":"view","type":"function"}]'

# --- SCANNERS ---
class SlingshotScanner:
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, close_prices):
        if self.triggered_signal: return self.triggered_signal
        if len(close_prices) < 20: return "WAIT"
        ma = sum(close_prices[-20:]) / 20
        curr, p1, p2 = close_prices[-1], close_prices[-2], close_prices[-3]
        if curr > ma and (p1 < ma or p2 < ma): self.triggered_signal = "UP (Reclaim)"; return self.triggered_signal
        if curr < ma and (p1 > ma or p2 > ma): self.triggered_signal = "DOWN (Break)"; return self.triggered_signal
        return "WAIT"

class PolyOddsTrendScanner:
    def __init__(self): self.triggered_signal = None
    def reset(self): self.triggered_signal = None
    def analyze(self, current_price, open_price, poly_up, poly_down, trend_prob):
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
        if self.triggered: return self.triggered
        if elapsed > 300: return "WAIT (Time)"
        if len(closes_60m) < 20: return "WAIT (Data)"
        slice_ = closes_60m[-20:]
        sma = sum(slice_) / 20
        std = (sum((x - sma) ** 2 for x in slice_) / 20) ** 0.5
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

def calculate_master_signal(sling, poly, cobra, flag):
    score = 0
    if "UP" in cobra: score += 2
    elif "DOWN" in cobra: score -= 2
    for sig in [sling, flag, poly]:
        if "UP" in sig: score += 1
        elif "DOWN" in sig: score -= 1
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
            with open(self.log_file, 'w', newline='') as f:
                csv.writer(f).writerow(["Timestamp", "Type", "Side", "Amount($)", "Price(c)", "Shares", "Balance", "Note"])

    def log_trade(self, type_, side, amount, price, shares, note=""):
        with open(self.log_file, 'a', newline='') as f:
            csv.writer(f).writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                type_, side, f"{amount:.2f}", f"{price:.3f}", f"{shares:.2f}", f"{self.balance:.2f}", note
            ])

    def buy(self, side, usd_amount, price):
        if usd_amount > self.balance: return False, "Insufficient Funds"
        if price <= 0: return False, "Invalid Price"
        
        shares = usd_amount / price
        self.balance -= usd_amount
        self.invested_this_window += usd_amount
        self.shares[side] += shares
        self.log_trade("BUY", side, usd_amount, price, shares)
        return True, f"Bought {shares:.2f} {side}"

    def sell(self, side, price, reason="Manual"):
        shares = self.shares[side]
        if shares <= 0: return False, "No Position"
        if price <= 0: return False, "Invalid Price"
        
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

# --- MODAL ---
class SettlementScreen(ModalScreen):
    CSS = """
    SettlementScreen { align: center middle; background: rgba(0,0,0,0.8); }
    #box { width: 60; height: auto; border: heavy $accent; background: $surface; padding: 2; align: center middle; }
    .win { color: #00ff00; text-style: bold; text-align: center; }
    .loss { color: #ff0000; text-style: bold; text-align: center; }
    .title { text-style: bold; border-bottom: solid $primary; width: 100%; text-align: center; }
    """
    def __init__(self, winner, payout, pnl, balance):
        super().__init__()
        self.winner = winner; self.payout = payout; self.pnl = pnl; self.balance = balance
    def compose(self) -> ComposeResult:
        c = "win" if self.pnl >= 0 else "loss"
        with Vertical(id="box"):
            yield Label(f"WINDOW CLOSED: {self.winner} WON", classes="title")
            yield Label(f"\nPayout: ${self.payout:.2f}", classes=c)
            yield Label(f"Net PnL: ${self.pnl:+.2f}", classes=c)
            yield Label(f"\nNew Balance: ${self.balance:.2f}")
            yield Button("CONTINUE (Auto in 5s)", id="btn_cont", variant="primary")
    def on_mount(self): self.set_timer(5, self.safe_dismiss)
    @work
    async def safe_dismiss(self): self.dismiss()
    @work
    async def on_button_pressed(self, event): self.dismiss()

# --- APP ---
class PolySimApp(App):
    CSS = """
    Screen { align: center top; }
    #header_stats { dock: top; height: 1; background: $panel; color: $text; content-align: center middle; }
    #timer_display { height: 3; background: $boost; border: solid $accent; content-align: center middle; text-align: center; margin-bottom: 1; }
    .timer_text { text-style: bold; color: $warning; }
    .price_card { width: 1fr; height: auto; min-height: 15; border: ascii $secondary; margin: 0 1; align: center middle; text-align: center; padding-bottom: 1; }
    #card_up { border: ascii #00ff00; }
    #card_down { border: ascii #ff0000; }
    #card_btc { border: ascii #f7931a; }
    .border_green { border: heavy #00ff00; }
    .border_red { border: heavy #ff0000; }
    .price_val { text-style: bold; color: auto; }
    .price_sub { color: $text-muted; text-style: dim; }
    .diff_green { color: #00ff00; text-style: bold; }
    .diff_red { color: #ff0000; text-style: bold; }
    .odds_high { color: #00ff00; text-style: bold; }
    .odds_med { color: #ffff00; text-style: bold; }
    .odds_low { color: #ff0000; text-style: bold; }
    .sig_up { color: #00ff00; text-style: bold; }
    .sig_down { color: #ff0000; text-style: bold; }
    .sig_wait { color: #555555; }
    .master_up { color: #00ff00; text-style: bold; background: #003300; }
    .master_down { color: #ff0000; text-style: bold; background: #330000; }
    .master_neu { color: #888888; }
    #input_area { height: auto; margin: 1 0; align: center middle; }
    .btn_row { align: center middle; height: 3; width: 100%; margin-top: 1; }
    Button { width: 1fr; height: 100%; margin: 0 1; }
    .btn_buy_up { background: #006600; }
    .btn_buy_down { background: #660000; }
    .btn_sell_up { background: #b38600; color: white; }
    .btn_sell_down { background: #b34b00; color: white; }
    RichLog { height: 5; min-height: 3; border-top: solid $primary; background: $surface; }
    """

    def __init__(self, broker):
        super().__init__()
        self.broker = broker
        self.market_data = {
            "up_price": 0.5, "down_price": 0.5, "up_bid": 0.5, "down_bid": 0.5,
            "btc_price": 0.0, "btc_open": 0.0, "btc_dyn_rng": 0.0, 
            "btc_odds": 0, "trend_score": 3, "trend_prob": 0.5,
            "sling_signal": "WAIT", "poly_signal": "WAIT", "cobra_signal": "WAIT", "flag_signal": "WAIT",
            "master_score": 0, "master_status": "NEUTRAL",
            "start_ts": 0
        }
        self.slingshot = SlingshotScanner()
        self.poly_scanner = PolyOddsTrendScanner()
        self.cobra = CobraScanner()
        self.bullflag = BullFlagScanner()

    def compose(self) -> ComposeResult:
        yield Label(f"SIM MODE | Bal: ${self.broker.balance:.2f}", id="header_stats")
        yield Horizontal(Label("5M WINDOW: ", classes="timer_text"), Label("00:00", id="lbl_timer_big", classes="timer_text"), id="timer_display")

        yield Horizontal(
            Vertical(
                Label("$0.00", id="p_btc", classes="price_val"),
                Label("Open: $0", id="p_btc_open", classes="price_sub"),
                Label("Diff: $0", id="p_btc_diff", classes="price_sub"),
                Label("Rng: $0", id="p_btc_rng", classes="price_sub"),
                Label("Odds: -/5", id="p_btc_odds", classes="price_sub"), # RESTORED ODDS LABEL
                Label("Trend: -", id="p_btc_trend", classes="price_sub"),
                Label("Sling: WAIT", id="p_sling", classes="price_sub"),
                Label("PolyT: WAIT", id="p_poly", classes="price_sub"),
                Label("Cobra: WAIT", id="p_cobra", classes="price_sub"),
                Label("Flag: WAIT", id="p_flag", classes="price_sub"),
                Label("---", classes="price_sub"),
                Label("SIGNAL: NEUTRAL", id="p_master", classes="price_sub"),
                id="card_btc", classes="price_card"
            ),
            Vertical(Label("UP", classes="price_label"), Label("0.0¢", id="p_up", classes="price_val"), id="card_up", classes="price_card"),
            Vertical(Label("DOWN", classes="price_label"), Label("0.0¢", id="p_down", classes="price_val"), id="card_down", classes="price_card")
        )

        yield Container(
            Input(placeholder="Amount ($)", id="inp_amount"),
            Horizontal(Button("BUY UP", id="btn_buy_up", classes="btn_buy_up"), Button("BUY DN", id="btn_buy_down", classes="btn_buy_down"), classes="btn_row"),
            Horizontal(Button("SELL UP", id="btn_sell_up", classes="btn_sell_up"), Button("SELL DN", id="btn_sell_down", classes="btn_sell_down"), classes="btn_row"),
            id="input_area"
        )
        yield RichLog(id="log_window", highlight=True, markup=True)

    async def on_mount(self):
        self.log_msg(f"Simulation Started. Bal: ${self.broker.balance}")
        self.log_msg(f"Logging to: {self.broker.log_file}")
        self.init_web3()
        self.set_interval(2, self.fetch_market_loop)
        self.set_interval(1, self.update_timer)

    def log_msg(self, msg):
        self.query_one(RichLog).write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    @work(exclusive=True, thread=True)
    def init_web3(self):
        try:
            from web3 import Web3
            self.w3_provider = Web3(Web3.HTTPProvider(POLYGON_RPC))
            self.chainlink_contract = self.w3_provider.eth.contract(address=Web3.to_checksum_address(CHAINLINK_BTC_FEED), abi=CHAINLINK_ABI)
            self.call_from_thread(self.log_msg, "[green]Web3 Linked (Read-Only)[/]")
        except: self.call_from_thread(self.log_msg, "[yellow]Web3 Failed. Using Binance backup.[/]")

    def update_balance_ui(self):
        self.query_one("#header_stats").update(f"SIM MODE | Bal: ${self.broker.balance:.2f}")

    def update_sell_buttons(self):
        md = self.market_data
        btn_su = self.query_one("#btn_sell_up"); btn_sd = self.query_one("#btn_sell_down")
        su = self.broker.shares["UP"]; sd = self.broker.shares["DOWN"]
        if su > 0:
            btn_su.label = f"SELL UP\n(${su * md['up_bid']:.2f})"
            btn_su.styles.background = "#b38600"
        else:
            btn_su.label = "SELL UP"; btn_su.styles.background = "#554400"
        if sd > 0:
            btn_sd.label = f"SELL DN\n(${sd * md['down_bid']:.2f})"
            btn_sd.styles.background = "#b34b00"
        else:
            btn_sd.label = "SELL DN"; btn_sd.styles.background = "#552200"

    async def fetch_market_loop(self):
        try:
            now = datetime.now(timezone.utc); floor = (now.minute // 5) * 5
            ts_start = int(now.replace(minute=floor, second=0, microsecond=0).timestamp())
            
            if self.market_data["start_ts"] != 0 and ts_start != self.market_data["start_ts"]:
                last_price = self.market_data["btc_price"]
                last_open = self.market_data["btc_open"]
                winner = "UP" if last_price >= last_open else "DOWN"
                payout, pnl = self.broker.settle_window(winner)
                
                self.push_screen(SettlementScreen(winner, payout, pnl, self.broker.balance))
                self.log_msg(f"[bold yellow]SETTLED:[/]{winner} | PnL: {pnl:+.2f}")
                self.update_balance_ui()
                self.slingshot.reset(); self.poly_scanner.reset()
                self.cobra.reset(); self.bullflag.reset()
            
            self.market_data["start_ts"] = ts_start
            elapsed = int(now.timestamp()) - ts_start
            rem_min = max(1, min(5, (300 - elapsed + 59) // 60))
            slug = f"btc-updown-5m-{ts_start}"

            curr_shares_up = self.broker.shares["UP"]
            curr_shares_down = self.broker.shares["DOWN"]

            def get_data(app_ref, s_up, s_down):
                s = requests.Session()
                d = {"curr":0,"open":0,"rng":0,"odds":1,"t_score":3,"t_prob":0.5,
                     "sling":"WAIT","poly":"WAIT","cobra":"WAIT","flag":"WAIT", "tp_trigger": None}
                
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

                # CALC ODDS SCORE
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
                    if s_up > 0 and up_bid >= 0.99: d["tp_trigger"] = "UP"
                    if s_down > 0 and down_bid >= 0.99: d["tp_trigger"] = "DOWN"
                    d["poly"] = app_ref.poly_scanner.analyze(d["curr"], d["open"], up_ask, down_ask, d["t_prob"])
                    return uid, did, up_ask, down_ask, up_bid, down_bid, d
                except: return None, None, 0, 0, 0, 0, d

            res = await asyncio.to_thread(get_data, self, curr_shares_up, curr_shares_down)
            d = res[6]
            score, status = calculate_master_signal(d["sling"], d["poly"], d["cobra"], d["flag"])

            self.market_data.update({
                "up_price":res[2], "down_price":res[3], "up_bid":res[4], "down_bid":res[5],
                "btc_price":d["curr"], "btc_open":d["open"], "btc_dyn_rng":d["rng"], "btc_odds": d["odds"],
                "trend_score":d["t_score"], "trend_prob":d["t_prob"],
                "sling_signal":d["sling"], "poly_signal":d["poly"], "cobra_signal":d["cobra"], "flag_signal":d["flag"],
                "master_score": score, "master_status": status
            })
            
            if d["tp_trigger"]:
                side = d["tp_trigger"]
                price = self.market_data["up_bid"] if side == "UP" else self.market_data["down_bid"]
                success, msg = self.broker.sell(side, price, reason="Auto-TP")
                if success:
                    self.log_msg(f"[bold green]💎 AUTO-TP: {msg}[/]")
                    self.update_balance_ui()

            md = self.market_data
            self.query_one("#p_up").update(f"{md['up_price']*100:.1f}¢")
            self.query_one("#p_down").update(f"{md['down_price']*100:.1f}¢")
            self.query_one("#p_btc").update(f"${md['btc_price']:,.0f}")
            self.query_one("#p_btc_open").update(f"Op: ${md['btc_open']:,.0f}")
            self.query_one("#p_btc_rng").update(f"{rem_min}m Rng: ${md['btc_dyn_rng']:.0f}")
            
            diff = md['btc_price'] - md['btc_open']
            dl = self.query_one("#p_btc_diff"); dl.update(f"{'+' if diff>=0 else '-'}${abs(diff):.1f}"); dl.classes = "diff_green" if diff>=0 else "diff_red"
            tl = self.query_one("#p_btc_trend"); tl.update(f"Trend: {md['trend_score']} ({md['trend_prob']:.0%})")
            tl.classes = "trend_up" if md['trend_score']>=4 else "trend_down" if md['trend_score']<=2 else "trend_noise"

            # RESTORED ODDS UPDATE
            ol = self.query_one("#p_btc_odds")
            ol.update(f"Odds: {md['btc_odds']}/5")
            if md['btc_odds'] >= 4: ol.classes = "odds_high"
            elif md['btc_odds'] == 3: ol.classes = "odds_med"
            else: ol.classes = "odds_low"

            def set_sig(lid, sig):
                lbl = self.query_one(lid); lbl.update(f"{lid.split('_')[1].capitalize().replace('Btc_','').replace('Poly_','Poly')}: {sig}")
                lbl.classes = "sig_up" if "UP" in sig else "sig_down" if "DOWN" in sig else "sig_wait"
            set_sig("#p_sling", md['sling_signal']); set_sig("#p_poly", md['poly_signal'])
            set_sig("#p_cobra", md['cobra_signal']); set_sig("#p_flag", md['flag_signal'])

            ms_lbl = self.query_one("#p_master"); ms_lbl.update(f"SCORE: {md['master_score']} ({md['master_status']})")
            card = self.query_one("#card_btc")
            card.classes = "price_card border_green" if score >= 3 else "price_card border_red" if score <= -3 else "price_card"
            ms_lbl.classes = "master_up" if score >= 3 else "master_down" if score <= -3 else "master_neu"
            
            self.update_sell_buttons()

        except Exception: pass

    def update_timer(self):
        if not self.market_data["start_ts"]: return
        rem = max(0, 300 - int(time.time() - self.market_data["start_ts"]))
        self.query_one("#lbl_timer_big").update(f"{rem//60:02d}:{rem%60:02d}")

    async def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if "buy" in bid: await self.trigger_buy("UP" if "up" in bid else "DOWN")
        else: await self.trigger_sell_all("UP" if "up" in bid else "DOWN")

    async def trigger_buy(self, side):
        val_str = self.query_one("#inp_amount").value
        try: val = float(val_str)
        except: return
        price = self.market_data["up_price"] if side == "UP" else self.market_data["down_price"]
        success, msg = self.broker.buy(side, val, price)
        if success:
            self.log_msg(f"[green]{msg}[/]")
            self.update_balance_ui(); self.update_sell_buttons()
        else: self.log_msg(f"[red]{msg}[/]")

    async def trigger_sell_all(self, side):
        price = self.market_data["up_bid"] if side == "UP" else self.market_data["down_bid"]
        success, msg = self.broker.sell(side, price)
        if success:
            self.log_msg(f"[green]{msg}[/]")
            self.update_balance_ui(); self.update_sell_buttons()
        else: self.log_msg(f"[red]{msg}[/]")

if __name__ == "__main__":
    print("\n=== POLYMARKET SIMULATOR SETUP ===")
    try: start_bal = float(input("Enter Initial Balance ($): ").strip() or "100.00")
    except: start_bal = 100.00
    default_log = f"sim_log_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    log_file = input(f"Enter Log Filename (default: {default_log}): ").strip()
    if not log_file: log_file = default_log
    if not log_file.endswith(".csv"): log_file += ".csv"
    print(f"Starting Sim with ${start_bal} logging to {log_file}...")
    time.sleep(1)
    
    broker = SimBroker(start_bal, log_file)
    app = PolySimApp(broker)
    app.run()
