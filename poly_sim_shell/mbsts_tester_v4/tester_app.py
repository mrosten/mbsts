import asyncio
import time
from datetime import datetime
import os
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, RichLog, Label, Button, ProgressBar, ListItem, ListView
from textual.screen import ModalScreen
from textual import work, on

from mbsts_tester_v4.loader import LogLoader
from mbsts_v4.scanners import (
    NPatternScanner, FakeoutScanner, TailWagScanner, RsiScanner, TrapCandleScanner,
    MidGameScanner, LateReversalScanner, StaircaseBreakoutScanner, PostPumpScanner,
    StepClimberScanner, SlingshotScanner, MinOneScanner, LiquidityVacuumScanner,
    CobraScanner, MesaCollapseScanner, MeanReversionScanner, GrindSnapScanner,
    VolCheckScanner, MosheSpecializedScanner, ZScoreBreakoutScanner, ALGO_INFO
)
from mbsts_v4.market import calculate_rsi, calculate_bb

class FileSelectScreen(ModalScreen):
    """A modal screen to select a CSV log file."""
    def compose(self) -> ComposeResult:
        logs = []
        if os.path.exists("logs"):
            logs = [f for f in os.listdir("logs") if f.endswith(".csv")]
        
        with Vertical(id="modal_container"):
            yield Label("[bold cyan]Select a Log File to Replay[/]", id="modal_title")
            with ListView(id="file_list"):
                for log in logs:
                    item = ListItem(Label(log))
                    item.log_filename = log
                    yield item
            with Horizontal(id="modal_footer"):
                yield Button("CANCEL", id="close_btn", variant="error")

    def on_mount(self):
        self.styles.align = ("center", "middle")
        container = self.query_one("#modal_container")
        container.styles.background = "#1a1a1a"
        container.styles.border = ("thick", "cyan")
        container.styles.padding = (1, 2)
        container.styles.width = 60
        container.styles.height = 30
        
    @on(ListView.Selected)
    def on_file_selected(self, event: ListView.Selected):
        filename = getattr(event.item, "log_filename", None)
        if filename:
            self.dismiss(os.path.join("logs", filename))

    @on(Button.Pressed, "#close_btn")
    def on_cancel(self):
        self.dismiss(None)

class TesterApp(App):
    CSS = """
    Screen { align: center top; background: #0a0a0a; }
    #header { height: 3; background: #1a1a1a; color: #00ff00; border-bottom: solid #333333; content-align: center middle; }
    .stat_label { margin: 0 2; }
    .price_val { text-style: bold; color: #ffffff; }
    .bankroll_val { color: #00ff00; text-style: bold; }
    .pnl_pos { color: #00ff00; }
    .pnl_neg { color: #ff0000; }
    
    #main_body { height: 1fr; }
    #log_panel { width: 3fr; height: 100%; border: ascii #333333; }
    #side_panel { width: 1fr; height: 100%; border-left: solid #333333; background: #111111; padding: 1 1; }
    
    #side_title { margin-bottom: 1; border-bottom: solid #333333; width: 100%; text-align: center; }
    .scanner_row { height: 1; padding: 0 1; margin-bottom: 0; }
    .scanner_active { background: #00ff00; color: #000000; text-style: bold; }
    .scanner_inactive { color: #444444; }
    
    #controls { height: 3; dock: bottom; background: #1a1a1a; align: center middle; padding: 0 2; }
    ProgressBar { width: 1fr; margin: 0 2; }

    #modal_container { layout: vertical; }
    #modal_title { width: 100%; text-align: center; margin-bottom: 1; }
    #file_list { background: #000000; border: solid #333333; height: 1fr; }
    #modal_footer { height: 3; align: center middle; }
    """

    def __init__(self, initial_ticks=None):
        super().__init__()
        self.ticks = initial_ticks or []
        self.current_index = 0
        self.is_playing = False
        self.playback_speed = 0.01 # Fast!
        self.price_history = []
        
        # Simulation Logic
        self.initial_balance = 100.00
        self.balance = 100.00
        self.active_trades = []
        self.trade_history = []
        self.window_open_price = 0
        
        self.scanners = {
            "NPattern": NPatternScanner(), "Fakeout": FakeoutScanner(),
            "Slingshot": SlingshotScanner(), "Cobra": CobraScanner(),
            "MinOne": MinOneScanner(), "MidGame": MidGameScanner(),
            "LateReversal": LateReversalScanner(), "GrindSnap": GrindSnapScanner(),
            "TrapCandle": TrapCandleScanner(), "Staircase": StaircaseBreakoutScanner(),
            "RSI": RsiScanner(), "Mesa": MesaCollapseScanner(),
            "ZScore": ZScoreBreakoutScanner(), "Moshe": MosheSpecializedScanner(),
            "VolCheck": VolCheckScanner(), "LiqVacuum": LiquidityVacuumScanner()
        }
        
    def compose(self) -> ComposeResult:
        yield Horizontal(
            Label("ALGO TESTER V4", id="title"),
            Label("Tick: 0/0", id="lbl_progress", classes="stat_label"),
            Label("BTC: $0.00", id="lbl_price", classes="stat_label"),
            Label("Bankroll: $100.00", id="lbl_bankroll", classes="stat_label bankroll_val"),
            Label("PnL: $0.00", id="lbl_pnl", classes="stat_label pnl_pos"),
            id="header"
        )
        yield Horizontal(
            RichLog(id="log_window", highlight=True, markup=True, classes="log_panel"),
            Vertical(
                Label("ACTIVE SCANNERS", id="side_title"),
                *[Label(f"• {name}", id=f"status_{name}", classes="scanner_row scanner_inactive") for name in self.scanners],
                id="side_panel"
            ),
            id="main_body"
        )
        yield Horizontal(
            Button("LOAD LOG", id="btn_load", variant="primary"),
            Button("PLAY", id="btn_play", variant="success"),
            Button("PAUSE", id="btn_pause", variant="warning"),
            Button("STEP", id="btn_step", variant="primary"),
            ProgressBar(total=100, id="pbar"),
            id="controls"
        )
        yield Footer()

    async def on_mount(self):
        if not self.ticks:
            self.action_select_file()
        else:
            self.setup_replay()
            
    def setup_replay(self):
        self.log_msg("[bold cyan]Setting up Replay...[/]")
        self.current_index = 0
        self.balance = self.initial_balance
        self.active_trades = []
        self.price_history = []
        for s in self.scanners.values(): s.reset()
        if self.ticks:
            self.query_one("#pbar").total = len(self.ticks)
            self.update_ui()

    def action_select_file(self):
        def handle_file(path):
            if path:
                self.log_msg(f"[bold yellow]Loading {path}...[/]")
                loader = LogLoader(path)
                self.ticks = loader.load()
                self.setup_replay()
                self.log_msg(f"[bold green]Successfully loaded {len(self.ticks)} ticks.[/]")
        
        self.push_screen(FileSelectScreen(), handle_file)

    @on(Button.Pressed, "#btn_load")
    def on_btn_load(self):
        self.is_playing = False
        self.action_select_file()

    def log_msg(self, msg):
        self.query_one("#log_window").write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def update_ui(self):
        if self.current_index >= len(self.ticks) or not self.ticks: return
        tick = self.ticks[self.current_index]
        
        self.query_one("#lbl_progress").update(f"Tick: {self.current_index}/{len(self.ticks)}")
        self.query_one("#lbl_price").update(f"BTC: [bold white]${tick.get('BTC_Price', 0):,.2f}[/]")
        
        # Bankroll & PnL
        pnl = self.balance - self.initial_balance
        pnl_class = "pnl_pos" if pnl >= 0 else "pnl_neg"
        pnl_sign = "+" if pnl >= 0 else ""
        
        self.query_one("#lbl_bankroll").update(f"Bankroll: [bold]${self.balance:,.2f}[/]")
        pnl_label = self.query_one("#lbl_pnl")
        pnl_label.update(f"PnL: [bold]{pnl_sign}${pnl:,.2f}[/]")
        pnl_label.set_classes(f"stat_label {pnl_class}")
        
        self.query_one("#pbar").progress = self.current_index

    @on(Button.Pressed, "#btn_play")
    def start_replay(self):
        if self.ticks:
            self.is_playing = True
            self.run_playback()

    @on(Button.Pressed, "#btn_pause")
    def pause_replay(self):
        self.is_playing = False

    @on(Button.Pressed, "#btn_step")
    def step_replay(self):
        if self.ticks:
            self.process_next_tick()

    @work(exclusive=True)
    async def run_playback(self):
        while self.is_playing and self.current_index < len(self.ticks):
            self.process_next_tick()
            await asyncio.sleep(self.playback_speed)

    def process_next_tick(self):
        if self.current_index >= len(self.ticks):
            self.is_playing = False
            return
            
        tick = self.ticks[self.current_index]
        elapsed = self.parse_elapsed(tick['TimeRem'])
        
        is_new_window = False
        if self.current_index == 0:
            is_new_window = True
        elif tick['BTC_Open'] != self.ticks[self.current_index-1]['BTC_Open']:
            is_new_window = True

        if is_new_window:
            # Settle previous window trades
            if self.current_index > 0:
                prev_tick = self.ticks[self.current_index-1]
                self.settle_trades(prev_tick['BTC_Price'], self.window_open_price)
            
            self.window_open_price = tick['BTC_Open']
            self.log_msg(f"[bold yellow]New Window: Open ${self.window_open_price:,.2f}[/]")
            self.price_history = []
            for s in self.scanners.values(): s.reset()
            # Reset visual highlights
            for name in self.scanners:
                self.query_one(f"#status_{name}").set_classes("scanner_row scanner_inactive")

        self.price_history.append({'timestamp': tick['Timestamp'], 'elapsed': elapsed, 'price': tick['BTC_Price']})
        self.run_scanners(tick, elapsed)
        self.current_index += 1
        self.update_ui()

    def settle_trades(self, close_price, open_price):
        if not self.active_trades: return
        
        # Determine actual outcome
        outcome = "UP" if close_price > open_price else ("DOWN" if close_price < open_price else "DRAW")
        
        window_pnl = 0
        for t in self.active_trades:
            if t['direction'] == outcome:
                # Win: 1.00 payout on Polymarket (Profit = 1.0 - entry_price)
                # But here we simulate simple: you bet $5.5, if you win you get back some return.
                # Actually Polymarket is: Buy shares at $0.50, if win they go to $1.00.
                # So profit = (1.0 - BuyPrice) * Shares
                shares = t['amount'] / t['entry_poly']
                revenue = shares * 1.0
                profit = revenue - t['amount']
                self.balance += revenue
                window_pnl += profit
                self.log_msg(f"[bold green]WIN[/] {t['algo']} ({t['direction']}) | Entry: {t['entry_poly']} | [green]+${profit:.2f}[/]")
            elif outcome == "DRAW":
                self.balance += t['amount']
                self.log_msg(f"[bold yellow]DRAW[/] {t['algo']} | Entry: {t['entry_poly']} | [yellow]$0.00[/]")
            else:
                window_pnl -= t['amount']
                # Balance was already deducted at entry
                self.log_msg(f"[bold red]LOSS[/] {t['algo']} ({t['direction']}) | Entry: {t['entry_poly']} | [red]-${t['amount']:.2f}[/]")
        
        self.active_trades = []

    def parse_elapsed(self, time_rem_str):
        try:
            m, s = map(int, str(time_rem_str).split(':'))
            return 300 - (m * 60 + s)
        except: return 0

    def run_scanners(self, tick, elapsed):
        ph = self.price_history
        cur = tick['BTC_Price']
        opn = self.window_open_price
        closes_60 = [p['price'] for p in ph] 
        
        rsi = calculate_rsi(closes_60) if len(closes_60) >= 15 else 50
        bb_upper, bb_mid, bb_lower = calculate_bb(closes_60) if len(closes_60) >= 20 else (0,0,0)

        for name, sc in self.scanners.items():
            res = "WAIT"
            try:
                # Execution logic to match app.py
                if name == "NPattern": res = sc.analyze(ph, opn)
                elif name == "Fakeout": res = sc.analyze(ph, opn, "GREEN") # Defaulting
                elif name == "Slingshot": res = sc.analyze(closes_60)
                elif name == "Cobra": res = sc.analyze(closes_60, cur, elapsed)
                elif name == "MinOne": res = sc.analyze(ph, elapsed)
                elif name == "MidGame": res = sc.analyze(ph, opn, elapsed, "NEUTRAL")
                elif name == "LateReversal": res = sc.analyze(ph, opn, elapsed)
                elif name == "GrindSnap": res = sc.analyze(ph, elapsed)
                elif name == "TrapCandle": res = sc.analyze(ph, opn)
                elif name == "Staircase": res = sc.analyze(closes_60)
                elif name == "RSI": res = sc.analyze(rsi, cur, bb_lower, elapsed)
                elif name == "Mesa": res = sc.analyze(ph, opn, elapsed)
                elif name == "ZScore": res = sc.analyze(ph, opn, elapsed)
                elif name == "Moshe": res = sc.analyze(elapsed, cur, opn, "NEUTRAL", tick.get('UP_Bid', 0.5), tick.get('DN_Bid', 0.5))
                elif name == "VolCheck": res = sc.analyze(closes_60, cur, opn, elapsed, tick.get('UP_Bid', 0.5), tick.get('DN_Bid', 0.5))
                elif name == "LiqVacuum": res = sc.analyze(cur, 0, opn)
                
                status_lbl = self.query_one(f"#status_{name}")
                if res and "BET_" in str(res):
                    status_lbl.set_classes("scanner_row scanner_active")
                    if not hasattr(sc, '_logged_replay'):
                        dir_ = "UP" if "UP" in str(res) else "DOWN"
                        color = "green" if dir_ == "UP" else "red"
                        self.log_msg(f"[{color}]SIGNAL {name}[/]: {res} @ {cur}")
                        self.place_trade(name, dir_, tick)
                        sc._logged_replay = True
                else:
                    # Don't remove active class until window end, so user can see it triggered!
                    # status_lbl.remove_class("scanner_active")
                    pass
            except: pass

    def place_trade(self, algo_name, direction, tick):
        # Prevent multiple trades per algo per window (simple safety)
        if any(t['algo'] == algo_name for t in self.active_trades): return
        
        # Simulate fixed $5.50 bet
        bet_amount = 5.50
        if self.balance < bet_amount:
            self.log_msg(f"[red]Skip {algo_name}: Insufficient Balance (${self.balance:.2f})[/]")
            return
            
        poly_price = tick.get('UP_Bid' if direction == "UP" else 'DN_Bid', 0.5)
        if poly_price <= 0: poly_price = 0.5 # Default
        
        self.balance -= bet_amount
        self.active_trades.append({
            'algo': algo_name,
            'direction': direction,
            'amount': bet_amount,
            'entry_poly': poly_price,
            'entry_btc': tick['BTC_Price']
        })
        self.log_msg(f"[cyan]V-TRADE[/] {algo_name} | {direction} @ ${poly_price:.2f} | Spent $5.50")
