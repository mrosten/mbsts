import asyncio
import time
from datetime import datetime
import os
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, RichLog, Label, Button, ProgressBar, ListItem, ListView, Static, Input
from textual.screen import ModalScreen
from textual import work, on, events

from mbsts_tester_v4.loader import LogLoader
from mbsts_v4.scanners import (
    NPatternScanner, FakeoutScanner, TailWagScanner, RsiScanner, TrapCandleScanner,
    MidGameScanner, LateReversalScanner, StaircaseBreakoutScanner, PostPumpScanner,
    StepClimberScanner, SlingshotScanner, MinOneScanner, LiquidityVacuumScanner,
    CobraScanner, MesaCollapseScanner, MeanReversionScanner, GrindSnapScanner,
    VolCheckScanner, MosheSpecializedScanner, ZScoreBreakoutScanner, ALGO_INFO
)
from mbsts_v4.market import calculate_rsi, calculate_bb
import pandas as pd

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
            with Horizontal(id="balance_row"):
                yield Label("Starting Balance ($):", id="lbl_bal_input")
                yield Input(value="100.00", placeholder="100.00", id="inp_start_bal")
            with Horizontal(id="modal_footer"):
                yield Button("CANCEL", id="close_btn", variant="error")

    def on_mount(self):
        self.styles.align = ("center", "middle")
        container = self.query_one("#modal_container")
        container.styles.background = "#1a1a1a"
        container.styles.border = ("thick", "cyan")
        container.styles.padding = (1, 2)
        container.styles.width = 70
        container.styles.height = 35
        
        # Style input row
        bal_row = self.query_one("#balance_row")
        bal_row.styles.height = 3
        bal_row.styles.margin = (1, 0)
        bal_row.styles.align = ("center", "middle")
        self.query_one("#lbl_bal_input").styles.margin = (0, 2)
        self.query_one("#inp_start_bal").styles.width = 20
        
    @on(ListView.Selected)
    def on_file_selected(self, event: ListView.Selected):
        filename = getattr(event.item, "log_filename", None)
        bal_str = self.query_one("#inp_start_bal").value
        try:
            balance = float(bal_str)
        except:
            balance = 100.00
            
        if filename:
            self.dismiss((os.path.join("logs", filename), balance))

    @on(Button.Pressed, "#close_btn")
    def on_cancel(self):
        self.dismiss(None)

class TesterApp(App):
    CSS = """
    Screen { align: center top; background: #0a0a0a; }
    #header { height: 3; background: #1a1a1a; color: #00ff00; border-bottom: solid #333333; content-align: center middle; }
    .stat_label { margin: 0 1; }
    .price_val { text-style: bold; color: #ffffff; }
    .bankroll_val { color: #00ff00; text-style: bold; }
    .pnl_pos { color: #00ff00; }
    .pnl_neg { color: #ff5555; }
    .log_pnl { color: #888888; }
    
    #main_body { height: 1fr; }
    #log_panel { width: 3fr; height: 100%; border: ascii #333333; }
    #side_panel { width: 1.2fr; height: 100%; border-left: solid #333333; background: #111111; padding: 1 1; }
    
    #side_title { margin-bottom: 0; border-bottom: solid #333333; width: 100%; text-align: center; }
    #side_shortcuts { height: 3; align: center middle; border-bottom: solid #333333; margin-bottom: 1; }
    .btn_side { min-width: 10; margin: 0 1; }
    
    .scanner_row { height: 1; padding: 0 1; margin-bottom: 0; }
    .scanner_active { background: #00ff00; color: #000000; text-style: bold; }
    .scanner_inactive { color: #444444; }
    .scanner_muted { color: #ff0000; text-style: strike; }
    .scanner_winner { color: #ffff00; text-style: bold; }
    
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
        self.playback_speed = 0.005 # Ultra-fast playback
        self.price_history = []
        
        # Simulation Logic
        self.initial_balance = 100.00
        self.balance = 100.00
        self.peak_balance = 100.00
        self.active_trades = []
        self.window_open_price = 0
        
        # Historical Comparison
        self.log_start_bal = 0
        self.log_current_bal = 0
        
        # UI State
        self.muted_scanners = set() 
        self.triggered_this_window = set()
        self.all_trades_history = [] # For CSV Export
        
        self.scanners = {
            "NPattern": NPatternScanner(), "Fakeout": FakeoutScanner(),
            "Slingshot": SlingshotScanner(), "Cobra": CobraScanner(),
            "MinOne": MinOneScanner(), "MidGame": MidGameScanner(),
            "LateReversal": LateReversalScanner(), "GrindSnap": GrindSnapScanner(),
            "TrapCandle": TrapCandleScanner(), "BullFlag": StaircaseBreakoutScanner(),
            "RSI": RsiScanner(), "Mesa": MesaCollapseScanner(),
            "ZScore": ZScoreBreakoutScanner(), "Moshe": MosheSpecializedScanner(),
            "VolCheck": VolCheckScanner(), "LiqVacuum": LiquidityVacuumScanner(),
            "StepClimber": StepClimberScanner(), "PostPump": PostPumpScanner(),
            "TailWag": TailWagScanner(), "MeanReversion": MeanReversionScanner()
        }
        self.scanner_stats = {name: {'wins': 0, 'losses': 0, 'pnl': 0.0} for name in self.scanners}
        
    def compose(self) -> ComposeResult:
        yield Horizontal(
            Label("ALGO TESTER V4", id="title"),
            Label("Tick: 0/0", id="lbl_progress", classes="stat_label"),
            Label("BTC: $0.00", id="lbl_price", classes="stat_label"),
            Label("Log: $0.00", id="lbl_log_bal", classes="stat_label log_pnl"),
            Label("Equity: $100.00", id="lbl_equity", classes="stat_label bankroll_val"),
            Label("Cash: $100.00", id="lbl_bankroll", classes="stat_label"),
            Label("Active: $0.00", id="lbl_exposure", classes="stat_label"),
            Label("Peak: $100.00", id="lbl_peak", classes="stat_label"),
            Label("PnL: $0.00", id="lbl_pnl", classes="stat_label pnl_pos"),
            id="header"
        )
        yield Horizontal(
            RichLog(id="log_window", highlight=True, markup=True, classes="log_panel"),
            Vertical(
                Label("[bold cyan]ACTIVE SCANNERS[/]", id="side_title"),
                Horizontal(
                    Button("MUTE ALL", id="btn_mute_all", classes="btn_side", variant="error"),
                    Button("UNMUTE", id="btn_unmute_all", classes="btn_side", variant="success"),
                    id="side_shortcuts"
                ),
                *[Static(f"• {name}", id=f"status_{name}", classes="scanner_row scanner_inactive") for name in self.scanners],
                id="side_panel"
            ),
            id="main_body"
        )
        yield Horizontal(
            Button("LOAD LOG", id="btn_load", variant="primary"),
            Button("PLAY", id="btn_play", variant="success"),
            Button("PAUSE", id="btn_pause", variant="warning"),
            Button("STEP", id="btn_step", variant="primary"),
            Button("REWIND", id="btn_rewind", variant="error"),
            Button("EXPORT STATS", id="btn_export", variant="default"),
            ProgressBar(total=100, id="pbar"),
            id="controls"
        )
        yield Footer()

    async def on_mount(self):
        if not self.ticks:
            self.action_select_file()
        else:
            self.setup_replay(self.initial_balance)
            
    def setup_replay(self, start_balance: float):
        self.log_msg(f"[bold cyan]Initializing Replay (${start_balance:.2f})...[/]")
        self.current_index = 0
        self.initial_balance = start_balance
        self.balance = start_balance
        self.peak_balance = start_balance
        self.active_trades = []
        self.price_history = []
        self.triggered_this_window = set()
        self.scanner_stats = {name: {'wins': 0, 'losses': 0, 'pnl': 0.0} for name in self.scanners}
        
        for s in self.scanners.values(): s.reset()
        if self.ticks:
            first_tick = self.ticks[0]
            self.log_start_bal = first_tick.get('SimBal', 0)
            self.log_current_bal = self.log_start_bal
            self.query_one("#pbar").total = len(self.ticks)
            self.update_ui()
            self.refresh_scanner_list()

    def action_select_file(self):
        def handle_file(result):
            if result:
                path, balance = result
                self.log_msg(f"[bold yellow]Loading {path}...[/]")
                loader = LogLoader(path)
                self.ticks = loader.load()
                self.setup_replay(balance)
                self.log_msg(f"[bold green]Successfully loaded {len(self.ticks)} ticks.[/]")
        
        self.push_screen(FileSelectScreen(), handle_file)

    @on(Button.Pressed, "#btn_load")
    def on_btn_load(self):
        self.is_playing = False
        self.action_select_file()

    @on(Button.Pressed, "#btn_export")
    def on_btn_export(self):
        if not self.all_trades_history:
            self.log_msg("[bold yellow]No trades to export yet.[/]")
            return
            
        filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df = pd.DataFrame(self.all_trades_history)
        df.to_csv(filename, index=False)
        self.log_msg(f"[bold green]Exported {len(df)} trades to {filename}[/]")

    @on(Button.Pressed, "#btn_mute_all")
    def on_mute_all(self):
        self.muted_scanners = set(self.scanners.keys())
        self.log_msg("[bold red]All scanners muted.[/]")
        self.refresh_scanner_list()

    @on(Button.Pressed, "#btn_unmute_all")
    def on_unmute_all(self):
        self.muted_scanners = set()
        self.log_msg("[bold green]All scanners enabled.[/]")
        self.refresh_scanner_list()

    @on(events.Click, ".scanner_row") # Click scanner to toggle mute
    def on_scanner_toggle(self, event: events.Click):
        target_id = event.widget.id
        if target_id and target_id.startswith("status_"):
            name = target_id.replace("status_", "")
            if name in self.muted_scanners:
                self.muted_scanners.remove(name)
                self.log_msg(f"[bold green]Enabled {name}[/]")
            else:
                self.muted_scanners.add(name)
                self.log_msg(f"[bold red]Muted {name}[/]")
            self.refresh_scanner_list()

    def refresh_scanner_list(self):
        for name in self.scanners:
            lbl = self.query_one(f"#status_{name}")
            cls = "scanner_row"
            if name in self.muted_scanners: cls += " scanner_muted"
            elif name in self.triggered_this_window: cls += " scanner_active"
            elif self.scanner_stats[name]['wins'] > self.scanner_stats[name]['losses'] and self.scanner_stats[name]['wins'] > 0:
                cls += " scanner_winner"
            else: cls += " scanner_inactive"
            
            stats = self.scanner_stats[name]
            total = stats['wins'] + stats['losses']
            pnl = stats['pnl']
            wr = (stats['wins']/total*100) if total > 0 else 0
            pnl_str = f"{'+' if pnl >= 0 else ''}${pnl:.2f}"
            lbl.update(f"• {name:12} [dim]{wr:3.0f}% ({total})[/] [bold]{pnl_str}[/]")
            lbl.set_classes(cls)

    def log_msg(self, msg):
        self.query_one("#log_window").write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def update_ui(self):
        if self.current_index >= len(self.ticks) or not self.ticks: return
        tick = self.ticks[self.current_index]
        
        self.query_one("#lbl_progress").update(f"Tick: {self.current_index}/{len(self.ticks)}")
        self.query_one("#lbl_price").update(f"BTC: [bold white]${tick.get('BTC_Price', 0):,.2f}[/]")
        
        # Log Reality Check
        self.log_current_bal = tick.get('SimBal', 0)
        log_pnl = self.log_current_bal - self.log_start_bal
        pnl_color = "pnl_pos" if log_pnl >= 0 else "pnl_neg"
        log_pnl_str = f"({log_pnl:+.2f})"
        self.query_one("#lbl_log_bal").update(f"Log: [dim]${self.log_current_bal:,.2f} {log_pnl_str}[/]")
        
        # Tester Stats (Equity based)
        realized_pnl = sum(s['pnl'] for s in self.scanner_stats.values())
        exposure = sum(t['amount'] for t in self.active_trades)
        equity = self.balance + exposure
        
        self.query_one("#lbl_equity").update(f"Equity: [bold]${equity:,.2f}[/]")
        self.query_one("#lbl_bankroll").update(f"Cash: [dim]${self.balance:,.2f}[/]")
        self.query_one("#lbl_exposure").update(f"Active: [yellow]${exposure:,.2f}[/]")
        
        # Update Peak (on Equity)
        if equity > self.peak_balance:
            self.peak_balance = equity
        self.query_one("#lbl_peak").update(f"Peak: [dim]${self.peak_balance:,.2f}[/]")

        pnl_label = self.query_one("#lbl_pnl")
        pnl_sign = "+" if realized_pnl >= 0 else ""
        pnl_class = "pnl_pos" if realized_pnl >= 0 else "pnl_neg"
        pnl_label.update(f"PnL: [bold]{pnl_sign}${realized_pnl:,.2f}[/]")
        pnl_label.set_classes(f"stat_label {pnl_class}")
        
        self.query_one("#pbar").progress = self.current_index
        self.refresh_scanner_list()

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

    @on(Button.Pressed, "#btn_rewind")
    def rewind_replay(self):
        self.is_playing = False
        if self.ticks:
            self.setup_replay(self.initial_balance)
            self.log_msg("[bold red]Replay Rewound to Start.[/]")

    @work(exclusive=True)
    async def run_playback(self):
        while self.is_playing and self.current_index < len(self.ticks):
            self.process_next_tick()
            await asyncio.sleep(self.playback_speed)

    def process_next_tick(self):
        if self.current_index >= len(self.ticks):
            self.is_playing = False
            # Settle any final trades at EOF
            if self.active_trades and self.ticks:
                last_tick = self.ticks[-1]
                self.settle_trades(last_tick.get('BTC_Price', 0), self.window_open_price)
            return
            
        tick = self.ticks[self.current_index]
        elapsed = self.parse_elapsed(tick.get('TimeRem', '5:00'))
        
        is_new_window = False
        if self.current_index == 0:
            is_new_window = True
        else:
            prev_tick = self.ticks[self.current_index-1]
            old_open = prev_tick.get('BTC_Open', 0)
            new_open = tick.get('BTC_Open', 0)
            
            # Handle NaNs and ensure we only trigger on valid, different Open prices
            if pd.notnull(old_open) and pd.notnull(new_open):
                if abs(new_open - old_open) > 0.01: 
                    is_new_window = True

        if is_new_window:
            if self.current_index > 0:
                prev_tick = self.ticks[self.current_index-1]
                self.settle_trades(prev_tick.get('BTC_Price', 0), self.window_open_price)
            
            self.window_open_price = tick.get('BTC_Open', 0)
            if pd.isnull(self.window_open_price):
                 self.window_open_price = tick.get('BTC_Price', 0) # Fallback
                 
            self.log_msg(f"[bold yellow]New Window: Open ${self.window_open_price:,.2f}[/]")
            self.triggered_this_window = set()
            for s in self.scanners.values(): 
                s.reset()
                # Clear all trigger states for the new window
                s.triggered_signal = None
                if hasattr(s, '_logged_replay'):
                    del s._logged_replay

        self.price_history.append({'timestamp': tick.get('Timestamp'), 'elapsed': elapsed, 'price': tick.get('BTC_Price', 0)})
        if len(self.price_history) > 100:
            self.price_history.pop(0)
            
        self.run_scanners(tick, elapsed)
        self.current_index += 1
        self.update_ui()

    def settle_trades(self, close_price, open_price):
        if not self.active_trades: return
        outcome = "UP" if close_price > open_price else ("DOWN" if close_price < open_price else "DRAW")
        
        for t in self.active_trades:
            if t['direction'] == outcome:
                shares = t['amount'] / t['entry_poly']
                revenue = shares * 1.0
                profit = revenue - t['amount']
                self.balance += revenue
                self.scanner_stats[t['algo']]['wins'] += 1
                self.scanner_stats[t['algo']]['pnl'] += profit
                self.log_msg(f"[bold green]WIN[/] {t['algo']} | Return: [green]+${profit:.2f}[/]")
                
                # Record in history
                t.update({'outcome': 'WIN', 'revenue': revenue, 'profit': profit, 'close_btc': close_price, 'settle_time': datetime.now().strftime('%H:%M:%S')})
                self.all_trades_history.append(t)
            elif outcome == "DRAW":
                self.balance += t['amount']
                self.log_msg(f"[bold yellow]DRAW[/] {t['algo']} | Entry returned")
                t.update({'outcome': 'DRAW', 'revenue': t['amount'], 'profit': 0, 'close_btc': close_price, 'settle_time': datetime.now().strftime('%H:%M:%S')})
                self.all_trades_history.append(t)
            else:
                self.scanner_stats[t['algo']]['losses'] += 1
                self.scanner_stats[t['algo']]['pnl'] -= t['amount']
                self.log_msg(f"[bold red]LOSS[/] {t['algo']} | Cost: [red]-${t['amount']:.2f}[/]")
                t.update({'outcome': 'LOSS', 'revenue': 0, 'profit': -t['amount'], 'close_btc': close_price, 'settle_time': datetime.now().strftime('%H:%M:%S')})
                self.all_trades_history.append(t)
        
        self.active_trades = []

    def parse_elapsed(self, time_rem_str):
        try:
            m, s = map(int, str(time_rem_str).split(':'))
            return 300 - (m * 60 + s)
        except: return 0

    def run_scanners(self, tick, elapsed):
        ph = self.price_history
        cur = tick.get('BTC_Price', 0)
        opn = self.window_open_price
        closes_60 = [p['price'] for p in ph] 
        
        rsi = calculate_rsi(closes_60) if len(closes_60) >= 15 else 50
        bb_upper, bb_mid, bb_lower = calculate_bb(closes_60) if len(closes_60) >= 20 else (0,0,0)
        ma = bb_mid # For MeanReversion, using BB_mid as MA

        for name, sc in self.scanners.items():
            if name in self.muted_scanners: continue
            
            res = "WAIT"
            try:
                # Execution logic (Experimental Gates for Tester only)
                if name == "Slingshot":
                    if elapsed <= 240 and len(closes_60) >= 20:
                        window_range = max(closes_60) - min(closes_60)
                        if window_range >= (closes_60[-1] * 0.0005): # Volatility Gate
                            res = sc.analyze(closes_60)
                elif name == "BullFlag":
                    if elapsed <= 240: res = sc.analyze(closes_60)
                elif name == "StepClimber":
                    if elapsed <= 200: res = sc.analyze(closes_60)
                elif name == "NPattern": res = sc.analyze(ph, opn)
                elif name == "Fakeout": res = sc.analyze(ph, opn, "GREEN") 
                elif name == "Cobra": res = sc.analyze(closes_60, cur, elapsed)
                elif name == "MinOne": res = sc.analyze(ph, elapsed)
                elif name == "MidGame": res = sc.analyze(ph, opn, elapsed, "NEUTRAL")
                elif name == "LateReversal": res = sc.analyze(ph, opn, elapsed)
                elif name == "GrindSnap": res = sc.analyze(ph, elapsed)
                elif name == "TrapCandle": res = sc.analyze(ph, opn)
                elif name == "RSI": res = sc.analyze(rsi, cur, bb_lower, elapsed)
                elif name == "Mesa": res = sc.analyze(ph, opn, elapsed)
                elif name == "ZScore": res = sc.analyze(ph, opn, elapsed)
                elif name == "Moshe": res = sc.analyze(elapsed, cur, opn, "NEUTRAL", tick.get('UP_Bid', 0.5), tick.get('DN_Bid', 0.5))
                elif name == "TailWag":
                    res = sc.analyze(300 - elapsed, tick.get('Poly_Vol', 0), tick.get('Spot_Depth', 0), "UP" if cur > opn else "DOWN", cur, ph)
                elif name == "PostPump":
                    res = sc.analyze(cur, opn, {}) # Mock last_window
                elif name == "MeanReversion":
                    res = sc.analyze(ph, (bb_upper, ma, bb_lower), "DOWN") # Mock fast_bb and trend
                elif name == "VolCheck": res = sc.analyze(closes_60, cur, opn, elapsed, tick.get('UP_Bid', 0.5), tick.get('DN_Bid', 0.5))
                elif name == "LiqVacuum": res = sc.analyze(cur, 0, opn)
                
                if res and "BET_" in str(res):
                    self.triggered_this_window.add(name)
                    if not hasattr(sc, '_logged_replay'):
                        dir_ = "UP" if "UP" in str(res) else "DOWN"
                        self.log_msg(f"[bold cyan]SIGNAL {name}[/]: {res} @ {cur}")
                        self.place_trade(name, dir_, tick)
                        sc._logged_replay = True
            except: pass

    def place_trade(self, algo_name, direction, tick):
        if any(t['algo'] == algo_name for t in self.active_trades): return
        
        # Dynamic Sizing: 20% of available bankroll
        bet_amount = self.balance * 0.20
        if bet_amount < 1.0: # Minimum bet safety
            if self.balance >= 1.0: bet_amount = 1.0
            else: return
            
        poly_price = tick.get('UP_Bid' if direction == "UP" else 'DN_Bid', 0.5)
        if poly_price <= 0: poly_price = 0.5 
        
        # Risk Mitigation: Don't buy if odds are too poor (e.g. > $0.85)
        # High poly_price = low payout. Buying at 0.85 requires 85%+ win rate to break even.
        MAX_POLY_PRICE = 0.85
        if poly_price > MAX_POLY_PRICE:
            self.log_msg(f"[dim]SKIPPED {algo_name}[/] | Price too high: ${poly_price:.2f}")
            return
            
        self.balance -= bet_amount
        self.active_trades.append({
            'algo': algo_name, 'direction': direction, 'amount': bet_amount,
            'entry_poly': poly_price, 'entry_btc': tick.get('BTC_Price', 0)
        })
        self.log_msg(f"[magenta]V-TRADE[/] {algo_name} ({direction}) | Size: ${bet_amount:.2f} | Price: ${poly_price:.2f}")
