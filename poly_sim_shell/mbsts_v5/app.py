import time
import asyncio
import json
import os
import csv
from datetime import datetime, timezone
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Button, RichLog, Label, Checkbox
from textual import work, on, events

from .config import TradingConfig, POLYGON_RPC_LIST, CHAINLINK_BTC_FEED, CHAINLINK_ABI
from .market import MarketDataManager, calculate_rsi, calculate_bb, calculate_atr
from .risk import RiskManager, AlgorithmPortfolio
from .broker import TradeExecutor
from .scanners import (
    NPatternScanner, FakeoutScanner, MomentumScanner, RsiScanner, TrapCandleScanner,
    MidGameScanner, LateReversalScanner, StaircaseBreakoutScanner, PostPumpScanner,
    StepClimberScanner, SlingshotScanner, MinOneScanner, LiquidityVacuumScanner,
    CobraScanner, MesaCollapseScanner, MeanReversionScanner, GrindSnapScanner,
    VolCheckScanner, MosheSpecializedScanner, ZScoreBreakoutScanner
)

class SniperApp(App):
    CSS = """
    Screen { align: center top; layers: base; }
    #top_bar { dock: top; height: 1; background: $panel; color: $text; content-align: center middle; }
    #btn_settings { dock: right; border: none; background: transparent; color: #aaaaaa; min-width: 14; height: 1; padding: 0 1; }
    #btn_settings:hover { color: #ffffff; text-style: bold; }
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
    
    .input_group { height: 1; align: center middle; layout: horizontal; padding: 0; margin-bottom: 0; }
    .lbl_sm { content-align: center middle; margin-right: 1; color: #aaaaaa; }
    Input { width: 12; height: 1; margin: 0 1; background: $surface; border: none; color: #ffffff; text-align: center; }
    #inp_tp { color: #00ff00; }
    #inp_sl { color: #ff0000; }
    #inp_min_diff { color: #00ffff; }

    #button_row { height: 1; align: center middle; layout: horizontal; padding: 0; margin-top: 1; margin-bottom: 1; }
    Button { height: 1; min-width: 12; margin: 0 1; border: none; }
    .btn_buy_up { background: #006600; color: #ffffff; }
    .btn_buy_down { background: #660000; color: #ffffff; }
    .btn_sell_up { background: #b38600; color: #ffffff; }
    .btn_sell_down { background: #b34b00; color: #ffffff; }

    #checkbox_container { height: auto; border-bottom: double $primary; margin-bottom: 1; }
    .algo_row { align: center middle; height: 1; layout: horizontal; padding: 0; margin: 0; }
    .algo_row Button { height: 1; min-width: 8; margin: 0 1; }
    .algo_item { width: 1fr; height: 1; layout: horizontal; align: left middle; padding-left: 2; }
    .algo_item Checkbox { width: auto; margin: 0; padding: 0; border: none; }
    .algo_item Label { width: auto; margin: 0 0 0 1; color: #666666; }
    .algo_item Label:hover { color: cyan; text-style: underline; }
    
    .live_row { align: center middle; height: 3; background: #220000; padding: 0 1; border-top: solid #440000; }
    .live_row Checkbox { height: 1; min-height: 1; width: auto; margin: 0 1; background: #220000; color: #aaaaaa; border: none; }
    
    /* Checkbox Styling: Hide X when unchecked, Show when checked */
    Checkbox > .toggle--button { color: $surface; background: #333333; } /* Matches bg color to hide check */
    Checkbox.-on > .toggle--button { color: #000000; background: #00ff00; } /* Black check on Green BG */
    
    /* Live Mode Checkbox Special */
    #cb_live > .toggle--button { color: $surface; background: #550000; }
    #cb_live.-on > .toggle--button { color: #ffffff; background: #ff0000; }
    
    #live_row { align: left middle; }
    #inp_cmd { width: 1fr; margin: 0 4; background: #111111; border: none; color: #00ffff; text-align: left; min-width: 20; padding: 0 1; }
    
    /* Blinking Animation for Pending Trades */
    .blinking { text-style: bold; color: yellow; }
    
    /* Deprecated styling */
    .deprecated_lbl { color: #555555; }
    
    #cb_live { color: #ff0000; text-style: bold; }
    RichLog { height: 1fr; min-height: 5; background: #111111; color: #eeeeee; }
    """

    @on(Checkbox.Changed)
    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        cb = event.checkbox
        cb_id = cb.id
        
        if cb_id and cb_id.startswith("cb_"):
            code = cb_id[3:]
            try:
                lbl = self.query_one(f"#lbl_{code}")
                if event.value:
                    lbl.styles.color = "#00ff00"
                    lbl.styles.text_style = "bold"
                    self.log_msg(f"ENABLED {code.upper()}", level="ADMIN")
                else:
                    lbl.styles.color = "#666666"
                    lbl.styles.text_style = "none"
                    self.log_msg(f"DISABLED {code.upper()}", level="ADMIN")
            except Exception:
                # Catch NoMatches or KeyErrors from modal checkboxes that bubble up
                pass

    @on(events.Click, "Label")
    def on_label_click(self, event: events.Click) -> None:
        lbl_id = event.control.id
        if lbl_id and lbl_id.startswith("lbl_"):
            code = lbl_id[4:].upper()
            
            # Open BullFlag settings modal when STA is clicked
            if code == "STA":
                self.push_screen(BullFlagSettingsModal(self))
                return
            
            # Original logic for other algo codes
            if code in self.scanner_descriptions:
                desc = self.scanner_descriptions[code]["desc"]
                self.push_screen(AlgoInfoModal(code, self.scanner_descriptions[code]["name"], desc, self))
            event.stop()

    @on(Button.Pressed, "#btn_algo_all")
    def on_all_algos(self):
        for code in ALGO_INFO:
            try: self.query_one(f"#cb_{code.lower()}").value = True
            except: pass

    @on(Button.Pressed, "#btn_algo_none")
    def on_none_algos(self):
        for code in ALGO_INFO:
            try: self.query_one(f"#cb_{code.lower()}").value = False
            except: pass

    def __init__(self, sim_broker, live_broker, start_live_mode=False):
        super().__init__()
        self.sim_broker = sim_broker
        self.live_broker = live_broker
        self.start_live_mode = start_live_mode
        self.market_data_manager = MarketDataManager(logger_func=lambda m: self.call_from_thread(self.log_msg, m))
        self.risk_manager = RiskManager()
        self.trade_executor = TradeExecutor(sim_broker, live_broker, self.risk_manager)
        self.market_data = self.market_data_manager.market_data 
        self.risk_initialized = False 
        self.last_second_exit_triggered = False
        self.next_window_preview_triggered = False
        self.pre_buy_pending = None        # { side, entry, cost } — held outside window_bets across settlement
        self.pre_buy_triggered = False     # latch: only one pre-buy per window
        self.mom_buy_mode = "STD"          # "STD" = standard signal | "PRE" = pre-buy next window
        self.window_realized_revenue = 0.0 # cumulative revenue added this window (TP/SL/manual sells)
        self.halted = False                # True = bankroll exhausted, all scanning stopped
        self.sl_plus_mode = True
        self.committed_tp = 0.95  # Default TP 95% — only updated on Enter
        self.committed_sl = 0.40  # Default SL 40% — only updated on Enter
        
        self.console_log_file = self.sim_broker.log_file.replace(".csv", "_console.txt")
        with open(self.console_log_file, "w", encoding="utf-8") as f:
            f.write("=== POLYMARKET SNIPER V5 CONSOLE LOG ===\n")
        
        self.scanners = {
            "NPattern": NPatternScanner(),
            "Fakeout": FakeoutScanner(),
            "Momentum": MomentumScanner(),
            "RSI": RsiScanner(),
            "TrapCandle": TrapCandleScanner(),
            "MidGame": MidGameScanner(),
            "LateReversal": LateReversalScanner(),
            "BullFlag": StaircaseBreakoutScanner(),
            "PostPump": PostPumpScanner(),
            "StepClimber": StepClimberScanner(),
            "Slingshot": SlingshotScanner(),
            "MinOne": MinOneScanner(),
            "Liquidity": LiquidityVacuumScanner(),
            "Cobra": CobraScanner(),
            "Mesa": MesaCollapseScanner(),
            "MeanReversion": MeanReversionScanner(),
            "GrindSnap": GrindSnapScanner(),
            "VolCheck": VolCheckScanner(),
            "Moshe": MosheSpecializedScanner(),
            "ZScore": ZScoreBreakoutScanner()
        }
        
        self.portfolios = {name: AlgorithmPortfolio(name, 100.0) for name in self.scanners}
        self.window_bets = {} 
        self.pending_bets = {}
        self.last_second_exit_triggered = False 
        self.window_settled = False
        self.mid_window_lockout = False
        self.saved_sim_bankroll = None
        self.app_start_time = time.time()
        self.session_win_count = 0 
        self.session_total_trades = 0
        self.session_windows_settled = 0
        self.time_rem_str = "00:00"
        self.blink_state = False
        self.skipped_logs = set()
        self.session_date_logged = False
        
        # Adjustable global settings
        self.csv_log_freq = 15
        self.last_log_dump = 0
        
        # Persistent algorithm weights
        # Momentum Advanced Settings (v5.9)
        self.mom_adv_settings = {
            "atr_low": 20, "atr_high": 40,
            "stable_offset": -5, "chaos_offset": 10,
            "auto_stn_chaos": True, "auto_pbn_stable": False,
            "shield_time": 45, "shield_reach": 5
        }
        self.settings_file = "v5_settings.json"
        
        # Base 1.0 weight with 1.67x (20% / 12%) modifier for historically "Strong" scanners
        self.scanner_weights = {k: 1.0 for k in ALGO_INFO.keys()}
        self.scanner_weights["COB"] = 1.67
        self.scanner_weights["LIQ"] = 1.67
        self.scanner_weights["LAT"] = 1.67
        
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r") as f:
                    saved = json.load(f)
                    for k, v in saved.items():
                        if k in self.scanner_weights:
                            self.scanner_weights[k] = float(v)
        except Exception: pass

        self.mom_analytics = self._reset_mom_analytics()
        # Create a time-signatured log file for this session in lg/ subdirectory
        session_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.mom_adv_log_file = f"lg/momentum_adv_{session_time}.csv"
        self._init_mom_adv_log()

    def _reset_mom_analytics(self):
        return {
            "pre_15s_gap": None, "btc_pre_15s": None,
            "btc_pre_60s": None,
            "gap_5s": None,      "btc_5s": None,
            "gap_10s": None,     "btc_10s": None,
            "gap_15s": None,     "btc_15s": None,
            "up_bid_15s": None,  "down_bid_15s": None, "spread_15s": None,
            "first_55c_side": None, "first_55c_time": None,
            "first_60c_side": None, "first_60c_time": None,
            "first_65c_side": None, "first_65c_time": None,
            "window_low": None,  "window_high": None,
        }

    def _init_mom_adv_log(self):
        if not os.path.exists(self.mom_adv_log_file):
            with open(self.mom_adv_log_file, 'w') as f:
                header = (
                    "Window_ID,Pre_15s_Gap,BTC_Pre_15s,BTC_Pre_60s,BTC_Velocity_60s,"
                    "Gap_5s,BTC_5s,Gap_10s,BTC_10s,Gap_15s,BTC_15s,Poly_Spread_15s,"
                    "UP_Bid_15s,DN_Bid_15s,"
                    "First_55c_Side,First_55c_Time,First_60c_Side,First_60c_Time,"
                    "First_65c_Side,First_65c_Time,RSI_1m,V_1m,"
                    "Drawdown_UP,Drawdown_DN,ATR_5m,BTC_Open,BTC_Close,Winner"
                )
                f.write(header + "\n")

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Label(f"5-SIM | Bal: ${self.sim_broker.balance:.2f}", id="header_stats"),
            Label(f" | RUN: 00:00:00", id="lbl_runtime", classes="run_time"),
            Label(" | WIN: ", classes="timer_text"),
            Label("00:00", id="lbl_timer_big", classes="timer_text"),
            id="top_bar"
        )
        yield Horizontal(
            Container(
                Label("$0.00", id="p_btc", classes="price_val"),
                Label("Open: $0", id="p_btc_open", classes="price_sub"),
                Label("Diff: $0", id="p_btc_diff", classes="price_sub"),
                Label("Trend 1H: NEUTRAL", id="p_trend", classes="price_sub"),
                Label("ATR 5m: $0.00", id="p_atr", classes="price_sub"),
                id="card_btc", classes="price_card"
            ),
            Vertical(
                Vertical(Label("UP", classes="price_sub"), Label("0.0¢", id="p_up", classes="price_val"), id="card_up", classes="mini_card"),
                Vertical(Label("DN", classes="price_sub"), Label("0.0¢", id="p_down", classes="price_val"), id="card_down", classes="mini_card"),
                classes="right_col"
            ),
            classes="row_main"
        )
        yield Container(
            Label("Bet:", classes="lbl_sm"),
            Input(placeholder="Bet $", value="1.00", id="inp_amount"),
            Label("Bankroll:", classes="lbl_sm"),
            Input(placeholder="Risk Bankroll", id="inp_risk_alloc"),
            Label("TP %:", classes="lbl_sm"),
            Input(placeholder="TP %", value="95", id="inp_tp"),
            Label("SL %:", classes="lbl_sm"),
            Input(placeholder="SL %", value="40", id="inp_sl"),
            classes="input_group"
        )
        yield Container(
            Label("Sim Bal:", classes="lbl_sm"),
            Input(placeholder="Sim Bal", value=f"{self.sim_broker.balance:.2f}", id="inp_sim_bal"),
            Label("Min Diff:", classes="lbl_sm"),
            Input(placeholder="Min Diff $", value="0", id="inp_min_diff"),
            Label("Min Price:", classes="lbl_sm"),
            Input(placeholder="Min Price", value="0.55", id="inp_min_price"),
            Label("Max Price:", classes="lbl_sm"),
            Input(placeholder="Max Price", value="0.80", id="inp_max_price"),
            classes="input_group"
        )
        yield Container(
            Button("BUY UP", id="btn_buy_up", classes="btn_buy_up"), 
            Button("BUY DN", id="btn_buy_down", classes="btn_buy_down"),
            Button("SELL UP", id="btn_sell_up", classes="btn_sell_up"), 
            Button("SELL DN", id="btn_sell_down", classes="btn_sell_down"),
            id="button_row"
        )
        yield Horizontal(
            Label("Scanners:", classes="lbl_sm"),
            Button("ALL", id="btn_algo_all"),
            Button("NONE", id="btn_algo_none"),
            classes="algo_row"
        )
        yield Horizontal(
            Horizontal(Checkbox(value=False, id="cb_cob"), Label("COB", id="lbl_cob"), classes="algo_item"),
            Horizontal(Checkbox(value=False, id="cb_fak"), Label("FAK", id="lbl_fak"), classes="algo_item"),
            Horizontal(Checkbox(value=False, id="cb_gri"), Label("GRI ~", id="lbl_gri", classes="deprecated_lbl"), classes="algo_item"),
            Horizontal(Checkbox(value=False, id="cb_lat"), Label("LAT", id="lbl_lat"), classes="algo_item"),
            Horizontal(Checkbox(value=False, id="cb_liq"), Label("LIQ", id="lbl_liq"), classes="algo_item"),
            classes="algo_row"
        )
        yield Horizontal(
            Horizontal(Checkbox(value=False, id="cb_mea"), Label("MEA", id="lbl_mea"), classes="algo_item"),
            Horizontal(Checkbox(value=False, id="cb_mes"), Label("MES", id="lbl_mes"), classes="algo_item"),
            Horizontal(Checkbox(value=False, id="cb_mid"), Label("MID ~", id="lbl_mid", classes="deprecated_lbl"), classes="algo_item"),
            Horizontal(Checkbox(value=False, id="cb_min"), Label("MIN ~", id="lbl_min", classes="deprecated_lbl"), classes="algo_item"),
            Horizontal(Checkbox(value=False, id="cb_mos"), Label("MOS", id="lbl_mos"), classes="algo_item"),
            classes="algo_row"
        )
        yield Horizontal(
            Horizontal(Checkbox(value=False, id="cb_npa"), Label("NPA", id="lbl_npa"), classes="algo_item"),
            Horizontal(Checkbox(value=False, id="cb_pos"), Label("POS", id="lbl_pos"), classes="algo_item"),
            Horizontal(Checkbox(value=False, id="cb_rsi"), Label("RSI", id="lbl_rsi"), classes="algo_item"),
            Horizontal(Checkbox(value=False, id="cb_sli"), Label("SLI", id="lbl_sli"), classes="algo_item"),
            Horizontal(Checkbox(value=False, id="cb_sta"), Label("STA", id="lbl_sta"), classes="algo_item"),
            classes="algo_row"
        )
        yield Horizontal(
            Horizontal(Checkbox(value=False, id="cb_ste"), Label("STE", id="lbl_ste"), classes="algo_item"),
            Horizontal(Checkbox(value=True, id="cb_mom"), Label("MOM", id="lbl_mom"), classes="algo_item"),
            Horizontal(Checkbox(value=False, id="cb_tra"), Label("TRA", id="lbl_tra"), classes="algo_item"),
            Horizontal(Checkbox(value=False, id="cb_vol"), Label("VOL", id="lbl_vol"), classes="algo_item"),
            Horizontal(Checkbox(value=False, id="cb_zsc"), Label("ZSC", id="lbl_zsc"), classes="algo_item"),
            classes="algo_row"
        )
        yield Horizontal(
            Checkbox("TP/SL", value=True, id="cb_tp_active"),
            Checkbox("Strong Only", value=False, id="cb_strong"),
            Checkbox("1 Trade Max", value=False, id="cb_one_trade"), 
            Checkbox("Whale Protect", value=False, id="cb_whale"),
            id="settings_row",
            classes="live_row"
        )
        yield Horizontal(
            Checkbox("LIVE MODE", value=False, id="cb_live"),
            Input(placeholder="Command: e.g., lo=false", id="inp_cmd"),
            Button("⚙ Settings", id="btn_settings"),
            id="live_row",
            classes="live_row"
        )
        yield RichLog(id="log_window", highlight=True, markup=True)

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted):
        # Handle command input first
        if event.input.id == "inp_cmd":
            cmd = event.input.value.strip().lower()
            if cmd == "lo=false":
                if self.mid_window_lockout:
                    self.mid_window_lockout = False
                    self.log_msg("[bold green]Admin Command:[/] Mid-window lockout CANCELLED. Trading Enabled.")
                else:
                    self.log_msg("[dim]Admin Command:[/] Lockout was not active.")
            elif cmd == "sl+":
                self.sl_plus_mode = True
                self.log_msg("[bold green]Admin Command:[/] SL+ Recovery Mode ENABLED.")
                self.save_settings()
            elif cmd == "sl-":
                self.sl_plus_mode = False
                self.log_msg("[bold red]Admin Command:[/] SL+ Recovery Mode DISABLED.")
                self.save_settings()
            elif cmd:
                self.log_msg(f"[yellow]Unknown Command:[/] {cmd}")
            event.input.value = ""
            return
            
        # Ignore changes from the Sim Bal display field
        if event.input.id == "inp_sim_bal": return
        
        # Determine human-readable names for the logs
        labels = {
            "inp_amount": "Bet Size",
            "inp_risk_alloc": "Risk Bankroll",
            "inp_tp": "Take Profit %",
            "inp_sl": "Stop Loss %",
            "inp_min_diff": "Min BTC Diff",
            "inp_min_price": "Min Option Price",
            "inp_max_price": "Max Option Price"
        }
        
        name = labels.get(event.input.id, event.input.id)
        val = event.input.value
        
        # Only log if there's actually a value typed
        if val:
            # If the user changed the Bankroll input box, explicitly set the trading core to use this value
            if event.input.id == "inp_risk_alloc":
                try:
                    new_br = float(val)
                    is_live = self.query_one("#cb_live").value
                    max_allowed = self.live_broker.balance if is_live else self.sim_broker.balance
                    
                    if new_br > max_allowed:
                        self.log_msg(f"[bold red]Admin Error:[/] Cannot set Bankroll to ${new_br:.2f} (Max balance is ${max_allowed:.2f})")
                        # Visually revert the input field to the max allowed so they know what happened
                        event.input.value = f"{max_allowed:.2f}"
                        self.risk_manager.risk_bankroll = max_allowed
                        self.risk_manager.target_bankroll = max_allowed
                    else:
                        self.log_msg(f"[dim]Admin:[/] Set {name} to [bold cyan]${new_br:.2f}[/]")
                        self.risk_manager.risk_bankroll = new_br
                        self.risk_manager.target_bankroll = new_br
                except ValueError:
                    pass
            else:
                if event.input.id == "inp_tp":
                    try:
                        self.committed_tp = float(val) / 100
                        self.log_msg(f"[dim]Admin:[/] Set {name} to [bold cyan]{val}%[/] (committed)")
                    except ValueError: pass
                elif event.input.id == "inp_sl":
                    try:
                        self.committed_sl = float(val) / 100
                        self.log_msg(f"[dim]Admin:[/] Set {name} to [bold cyan]{val}%[/] (committed)")
                    except ValueError: pass
                else:
                    self.log_msg(f"[dim]Admin:[/] Set {name} to [bold cyan]{val}[/]")

        # Auto-persist any setting that was just changed
        if event.input.id in {"inp_amount", "inp_tp", "inp_sl", "inp_min_diff", "inp_min_price", "inp_max_price"}:
            self.save_settings()

    async def on_mount(self):
        self.log_msg(f"Simulation Started. Bal: ${self.sim_broker.balance}")
        def_risk = self.sim_broker.balance
        self.query_one("#inp_risk_alloc").value = f"{def_risk:.2f}"
        
        # Initialize label colors
        for code in ALGO_INFO:
            try:
                cb = self.query_one(f"#cb_{code.lower()}")
                lbl = self.query_one(f"#lbl_{code.lower()}")
                if cb.value:
                    lbl.styles.color = "#00ff00"
                    lbl.styles.text_style = "bold"
            except: pass

        self.init_web3()
        self.set_interval(1, self.fetch_market_loop)
        self.set_interval(1, self.update_timer)
        self.set_interval(1, self.check_dump_log)
        self.set_interval(0.5, self.toggle_blinks)

        # --- RESTORE PERSISTED SETTINGS ---
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r") as f:
                    s = json.load(f)
                # UI inputs
                for fid in ["inp_amount", "inp_tp", "inp_sl", "inp_min_diff", "inp_min_price", "inp_max_price"]:
                    if fid in s:
                        try: self.query_one(f"#{fid}").value = str(s[fid])
                        except: pass
                # Restore committed TP/SL from saved values
                try: self.committed_tp = float(s.get("inp_tp", 95)) / 100
                except: pass
                try: self.committed_sl = float(s.get("inp_sl", 40)) / 100
                except: pass
                # Checkboxes
                try: self.query_one("#cb_tp_active").value = bool(s.get("cb_tp_active", False))
                except: pass
                try: self.query_one("#cb_one_trade").value = bool(s.get("cb_one_trade", False))
                except: pass
                # Flags
                self.sl_plus_mode = bool(s.get("sl_plus_mode", True))
                self.mom_buy_mode = s.get("mom_buy_mode", "STD")  # "STD" or "PRE"
                self.log_msg("[dim]Settings restored from disk.[/]")
        except Exception as e:
            self.log_msg(f"[yellow]Could not restore settings: {e}[/]")
        # -----------------------------------

        if self.start_live_mode:
            self.query_one("#cb_live").value = True 

    @on(Checkbox.Changed, "#cb_live")
    def on_live_toggle(self, event: Checkbox.Changed):
        if event.value: 
            self.saved_sim_bankroll = self.risk_manager.risk_bankroll
            self.log_msg("[bold red]LIVE MODE ENABLED! All Algos deselected for safety.[/]")
            all_cbs = ["#cb_cob", "#cb_fak", "#cb_gri", "#cb_lat", "#cb_liq", "#cb_mea", "#cb_mes", "#cb_mid", "#cb_min", "#cb_mos", "#cb_npa", "#cb_pos", "#cb_rsi", "#cb_sli", "#cb_sta", "#cb_ste", "#cb_tra", "#cb_vol", "#cb_zsc"]
            for cid in all_cbs: self.query_one(cid).value = False
            lb = self.live_broker.balance
            if lb >= 0:
                self.query_one("#inp_risk_alloc").value = f"{lb/TradingConfig.LIVE_RISK_DIVISOR:.2f}"
                self.risk_manager.set_bankroll(lb, is_live=True)
                self.risk_initialized = True
        else:
            if self.saved_sim_bankroll is not None:
                self.query_one("#inp_risk_alloc").value = f"{self.saved_sim_bankroll:.2f}"
                self.risk_manager.risk_bankroll = self.saved_sim_bankroll
                self.risk_manager.target_bankroll = self.saved_sim_bankroll
            else:
                sb = self.sim_broker.balance
                self.query_one("#inp_risk_alloc").value = f"{sb:.2f}"
                self.risk_manager.set_bankroll(sb, is_live=False)
            self.risk_initialized = True

    @on(Checkbox.Changed, "#cb_tp_active")
    @on(Checkbox.Changed, "#cb_strong")
    @on(Checkbox.Changed, "#cb_one_trade")
    @on(Checkbox.Changed, "#cb_whale")
    def on_settings_checkbox_changed(self, event: Checkbox.Changed):
        """Auto-persist setting checkboxes and log them."""
        self.save_settings()
        cid = event.checkbox.id
        name = ""
        if cid == "cb_tp_active": name = "TP/SL Monitoring"
        elif cid == "cb_strong": name = "Strong Only Mode"
        elif cid == "cb_one_trade": name = "1 Trade Max Guard"
        elif cid == "cb_whale": name = "Whale Protect"
        
        if name:
            state = "ENABLED" if event.value else "DISABLED"
            self.log_msg(f"{state} {name}", level="ADMIN")

    def log_msg(self, msg, level="INFO"):
        """
        Enhanced logging with TTG (Time-To-Go) prefixes and categorization.
        Levels: ADMIN (Blue), SCAN (Gray), TRADE (Green/Red), MONEY (Gold), ERROR (Banner)
        """
        now_ts = time.time()
        timestamp = datetime.fromtimestamp(now_ts).strftime('%H:%M:%S')
        
        # Calculate TTG Prefix [T-MM:SS]
        ttg_str = ""
        if self.market_data.get("start_ts", 0) > 0:
            rem = max(0, TradingConfig.WINDOW_SECONDS - int(now_ts - self.market_data["start_ts"]))
            ttg_str = f"[T-{rem//60:02d}:{rem%60:02d}] "

        # Color/Category Mapping
        lv = level.upper()
        tag = f"[{lv:<8}]"
        prefix = f"{ttg_str}{tag}"
        
        # Outcome-based coloring (overrides category color)
        msg_lower = msg.lower()
        is_profit = any(x in msg_lower for x in ["profit", "win", "pnl: +", "rev: +", "refill: +"])
        is_loss = any(x in msg_lower for x in ["loss", "lose", "failed", "pnl: -", "err"])
        
        if not getattr(self, "session_date_logged", False):
            self.session_date_logged = True
            date_str = datetime.fromtimestamp(now_ts).strftime('%Y-%m-%d')
            self.query_one(RichLog).write(f"[bold white]=== SESSION START: {date_str} ===[/]")

        if is_profit:         display_msg = f"[bold green]{prefix}{msg}[/]"
        elif is_loss:         display_msg = f"[bold red]{prefix}{msg}[/]"
        elif lv == "ADMIN":   display_msg = f"[bold sky_blue3]{prefix}{msg}[/]"
        elif lv == "SCAN":    display_msg = f"[dim white]{prefix}{msg}[/]"
        elif lv == "TRADE":   display_msg = f"[bold green]{prefix}{msg}[/]"
        elif lv == "MONEY":   display_msg = f"[bold gold3]{prefix}{msg}[/]"
        elif lv == "ERROR":   display_msg = f"[bold white on red] !!! {lv:<8}: {msg} !!! [/]"
        else:                display_msg = f"{ttg_str}{msg}" # Default INFO style

        self.query_one(RichLog).write(display_msg)
        
        # Mirror to console log file for persistence (pure ASCII scrubbing)
        import re
        # 1. Strip Rich tags
        clean_msg = re.sub(r'\[/?[a-z #0-9,.]+\]', '', display_msg if lv != "INFO" else msg)
        # 2. Strip non-ASCII characters (emojis/symbols)
        clean_msg = clean_msg.encode('ascii', 'ignore').decode('ascii').strip()
        
        try:
            with open(self.console_log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {clean_msg}\n")
        except: pass

    def dump_state_log(self):
        is_live = self.query_one("#cb_live").value
        self.sim_broker.log_snapshot(self.market_data, self.time_rem_str, is_live, self.live_broker.balance, self.risk_manager.risk_bankroll)

    def check_dump_log(self):
        now = time.time()
        if now - self.last_log_dump >= self.csv_log_freq:
            self.last_log_dump = now
            self.dump_state_log()

    def toggle_blinks(self):
        self.blink_state = not self.blink_state
        for name in list(self.pending_bets.keys()):
            try:
                lbl = self.query_one(f"#lbl_{name[:3].lower()}")
                if self.blink_state:
                    lbl.styles.color = "yellow"
                else:
                    lbl.styles.color = "#666666"
            except: pass

    def save_settings(self):
        try:
            # Gather current UI field values (widgets must be mounted)
            def _v(wid, default=""):
                try: return self.query_one(wid).value
                except: return default
            def _cb(wid, default=False):
                try: return self.query_one(wid).value
                except: return default

            data = {
                "scanner_weights": self.scanner_weights,
                "inp_amount":    _v("#inp_amount",    "1.00"),
                "inp_tp":        _v("#inp_tp",        "95"),
                "inp_sl":        _v("#inp_sl",        "40"),
                "inp_min_diff":  _v("#inp_min_diff",  "0"),
                "inp_min_price": _v("#inp_min_price", "0.55"),
                "inp_max_price": _v("#inp_max_price", "0.80"),
                "cb_tp_active":  _cb("#cb_tp_active", False),
                "cb_one_trade":  _cb("#cb_one_trade", False),
                "sl_plus_mode":  self.sl_plus_mode,
                "mom_buy_mode":  self.mom_buy_mode,
            }
            with open(self.settings_file, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            self.log_msg(f"[red]Error saving settings: {e}[/]")

    @work(exclusive=True, thread=True)
    def init_web3(self):
        from web3 import Web3
        for rpc in POLYGON_RPC_LIST:
            try:
                self.w3_provider = Web3(Web3.HTTPProvider(rpc))
                if not self.w3_provider.is_connected(): continue
                self.chainlink_contract = self.w3_provider.eth.contract(address=Web3.to_checksum_address(CHAINLINK_BTC_FEED), abi=CHAINLINK_ABI)
                self.chainlink_contract.functions.latestAnswer().call()
                self.market_data_manager.chainlink_contract = self.chainlink_contract
                self.call_from_thread(self.log_msg, f"[green]Web3 Connected via {rpc} (Chainlink Active)[/]")
                return
            except: continue
        self.call_from_thread(self.log_msg, "[red]All Web3 RPCs Failed. Using Binance backup.[/]")

    def update_balance_ui(self):
        is_live = self.query_one("#cb_live").value
        lbl = self.query_one("#header_stats")
        cap_display = f" (B.R.: ${self.risk_manager.risk_bankroll:.2f})" if self.risk_initialized else ""
        if is_live:
            lbl.update(f"[bold red]5-LIVE[/] | Bal: ${self.live_broker.balance:.2f}{cap_display}")
            lbl.classes = "live_mode"
        else:
            lbl.update(f"5-SIM | Bal: ${self.sim_broker.balance:.2f}{cap_display}")
            lbl.classes = ""

    def update_sell_buttons(self):
        md = self.market_data
        is_live = self.query_one("#cb_live").value
        btn_su = self.query_one("#btn_sell_up"); btn_sd = self.query_one("#btn_sell_down")
        if is_live:
            btn_su.label = "SELL UP (LIVE)"; btn_sd.label = "SELL DN (LIVE)"
        else:
            su = self.sim_broker.shares["UP"]; sd = self.sim_broker.shares["DOWN"]
            btn_su.label = f"SELL UP\n(${su * md['up_bid']:.2f})" if su > 0 else "SELL UP"
            btn_sd.label = f"SELL DN\n(${sd * md['down_bid']:.2f})" if sd > 0 else "SELL DN"

    async def fetch_market_loop(self):
        if self.halted: return  # Bot frozen — bankroll exhausted
        try:
            now = datetime.now(timezone.utc); floor = (now.minute // 5) * 5
            ts_start = int(now.replace(minute=floor, second=0, microsecond=0).timestamp())
            
            # Map scanner names to their UI checkbox IDs
            scanner_map = {name: f"#cb_{name.lower()}" for name in self.scanners}
            
            if not self.risk_initialized:
                try:
                    val = float(self.query_one("#inp_risk_alloc").value)
                    self.risk_manager.set_bankroll(val, is_live=self.query_one("#cb_live").value)
                    self.risk_initialized = True
                except: pass
            is_new_window = False
            is_first_tick = (self.market_data["start_ts"] == 0)
            
            if ts_start != self.market_data["start_ts"]:
                if not is_first_tick:
                    is_new_window = True
                
                self.market_data["start_ts"] = ts_start # Latch immediately to prevent double-trigger
                self.sim_broker.promote_prebuy()  # Move any pre-buy shares/costs to current window
                now_ts = time.time()
                wall_time = datetime.fromtimestamp(now_ts).strftime('%H:%M:%S')
                self.log_msg(f"[{wall_time}] ════════ NEW WINDOW #{ts_start} STARTING ════════", level="ADMIN")
                
                self.window_settled = False # reset latch for new window
                self.last_second_exit_triggered = False # reset latch for late exits
                self.next_window_preview_triggered = False # reset next-window preview latch
                self.pre_buy_triggered = False # reset pre-buy latch for new window
                self.window_realized_revenue = 0.0 # reset revenue tracker for new window
                
                # Transfer any pre-buy position into window_bets so TP/SL monitors it
                if self.pre_buy_pending:
                    sd = self.pre_buy_pending.get("side", "??")
                    key = f"Momentum_PreBuy_{time.time()}"
                    self.window_bets[key] = self.pre_buy_pending
                    # Note: Shares are promoted by sim_broker.promote_prebuy() above.
                    self.pre_buy_pending = None
                    self.log_msg(f"[bold cyan]🚀 PRE-BUY {sd} transferred to new window — now under TP/SL monitoring[/]")

                self.skipped_logs.clear() # reset the spam preventer
                self.pending_bets.clear() # discard any stale pending bets from last window
                for sc in self.scanners.values(): sc.reset() # reset all scanner signals/timers
                
                if self.mid_window_lockout:
                    self.mid_window_lockout = False
                    self.log_msg("[bold green]Lockout Lifted. Clean Window Started. Trading Enabled.[/]")

            # Calculate correct elapsed time using the actual window start
            elapsed = int(now.timestamp()) - ts_start
            # Moved self.market_data["start_ts"] = ts_start up to the is_new_window block for race safety
            
            # Mid-Window Safety Lockout Activation (If booting the bot deeply into a round)
            if is_first_tick and elapsed > 10:
                self.mid_window_lockout = True
                self.log_msg(f"[bold yellow]Booted Mid-Round ({elapsed}s elapsed). Waiting for next clean window to start trading...[/]")
                
            # Initial 10-second Lockout (prevents instant execution before APIs stabilize)
            is_initial_lockout = elapsed < 10
            slug = f"btc-updown-5m-{ts_start}"
            
            import concurrent.futures

            # Fetch Kraken Open Price instantly to avoid API lag from other services
            cur = await asyncio.to_thread(self.market_data_manager.fetch_current_price)
            opn = await asyncio.to_thread(self.market_data_manager.update_history, cur, ts_start, elapsed)
            
            if is_new_window:
                if self.query_one("#cb_live").value:
                    self.live_broker.update_balance()
                
                # Check for active positions inherited (like pre-buys)
                active_str = ""
                open_bets = [info for info in self.window_bets.values() if not info.get("closed")]
                if open_bets:
                    unique_sides = sorted(list(set(info["side"] for info in open_bets)))
                    active_str = f" | [bold green]Active: {', '.join(unique_sides)}[/]"
                
                self.log_msg(f"NEW WINDOW STARTED | Open: [bold white]${opn:,.2f}[/]{active_str}")

            def gather_rest():
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                    f1 = executor.submit(self.market_data_manager.update_4h_trend)
                    f2 = executor.submit(self.market_data_manager.update_1h_trend)
                    f3 = executor.submit(self.market_data_manager.fetch_candles_60m)
                    f4 = executor.submit(self.market_data_manager.fetch_polymarket, slug)
                    f1.result() # trend is just an internal state update
                    f2.result() # 1h trend is just an internal state update
                    return f3.result(), f4.result()

            candles, poly = await asyncio.to_thread(gather_rest)
            c60, l60, h60, _ = candles
            
            # Update ATR 5m
            if h60 and l60 and c60:
                self.market_data_manager.atr_5m = calculate_atr(h60, l60, c60, period=5)
            
            d = {"c60":c60, "l60":l60, "h60":h60, "cur":cur, "opn":opn, "poly":poly}
            
            self.market_data.update({
                "btc_price": d["cur"], "btc_open": d["opn"],
                "up_price": d["poly"]["up_price"], "down_price": d["poly"]["down_price"],
                "up_bid": d["poly"]["up_bid"], "down_bid": d["poly"]["down_bid"],
                "up_ask": d["poly"]["up_ask"], "down_ask": d["poly"]["down_ask"],
                "up_id": d["poly"]["up_id"], "down_id": d["poly"]["down_id"]
            })
            
            rsi = calculate_rsi(d["c60"])
            self.market_data['rsi'] = rsi # Store for manual access
            _, _, lbb = calculate_bb(d["c60"])
            ph = self.market_data_manager.price_history
            fbb = calculate_bb([p['price'] for p in ph[-20:]]) if len(ph) >= 20 else (0,0,0)

            # --- Momentum Analytics (v5.9.4) ---
            cur_btc = d["cur"]
            if self.mom_analytics["window_low"] is None or cur_btc < self.mom_analytics["window_low"]:
                self.mom_analytics["window_low"] = cur_btc
            if self.mom_analytics["window_high"] is None or cur_btc > self.mom_analytics["window_high"]:
                self.mom_analytics["window_high"] = cur_btc

            if elapsed == 5 and self.mom_analytics["gap_5s"] is None:
                self.mom_analytics["gap_5s"] = d["poly"]["up_ask"] - d["poly"]["down_ask"]
                self.mom_analytics["btc_5s"] = d["cur"]
            elif elapsed == 10 and self.mom_analytics["gap_10s"] is None:
                self.mom_analytics["gap_10s"] = d["poly"]["up_ask"] - d["poly"]["down_ask"]
                self.mom_analytics["btc_10s"] = d["cur"]
            elif elapsed == 15 and self.mom_analytics["gap_15s"] is None:
                self.mom_analytics["gap_15s"] = d["poly"]["up_ask"] - d["poly"]["down_ask"]
                self.mom_analytics["btc_15s"] = d["cur"]
                self.mom_analytics["up_bid_15s"] = d["poly"]["up_bid"]
                self.mom_analytics["down_bid_15s"] = d["poly"]["down_bid"]
                # Capture spread at 15s entry mark (standardized for UP side)
                u_ask, u_bid = d["poly"]["up_ask"], d["poly"]["up_bid"]
                if u_ask > 0 and u_bid > 0:
                    self.mom_analytics["spread_15s"] = u_ask - u_bid

            # Monitor Milestones: 55c, 60c, 65c
            u_bid, d_bid = d["poly"]["up_bid"], d["poly"]["down_bid"]
            for threshold in [0.55, 0.60, 0.65]:
                key_s = f"first_{int(threshold*100)}c_side"
                key_t = f"first_{int(threshold*100)}c_time"
                if self.mom_analytics[key_s] is None:
                    if u_bid >= threshold:
                        self.mom_analytics[key_s], self.mom_analytics[key_t] = "UP", elapsed
                    elif d_bid >= threshold:
                        self.mom_analytics[key_s], self.mom_analytics[key_t] = "DOWN", elapsed
            # -----------------------------------

            scanner_map = {"NPattern":"#cb_npa","Fakeout":"#cb_fak","Momentum":"#cb_mom","RSI":"#cb_rsi","TrapCandle":"#cb_tra","MidGame":"#cb_mid","LateReversal":"#cb_lat","BullFlag":"#cb_sta","PostPump":"#cb_pos","StepClimber":"#cb_ste","Slingshot":"#cb_sli","MinOne":"#cb_min","Liquidity":"#cb_liq","Cobra":"#cb_cob","Mesa":"#cb_mes","MeanReversion":"#cb_mea","GrindSnap":"#cb_gri","VolCheck":"#cb_vol","Moshe":"#cb_mos","ZScore":"#cb_zsc"}
                        # --- Check Pending Bets First ---
            if not self.mid_window_lockout and not is_initial_lockout:
                try: min_pr = float(self.query_one("#inp_min_price").value)
                except: min_pr = 0.01
                try: max_pr = float(self.query_one("#inp_max_price").value)
                except: max_pr = 0.99
                
                for name, info in list(self.pending_bets.items()):
                    # Re-check price logic
                    sd = info["side"]
                    bs = info["bs"]
                    res = info["res"]
                    pr = self.market_data["up_ask"] if sd == "UP" else self.market_data["down_ask"]
                    
                    if min_pr <= pr <= max_pr:
                        # Execution criteria met! But first, check we have enough bankroll.
                        if self.risk_manager.risk_bankroll < bs:
                            # Not enough risk bankroll - skip without logging spam
                            continue
                        is_l = self.query_one("#cb_live").value
                        ctx = {'signal_price': d["cur"], 'rsi': rsi, 'trend': self.market_data_manager.trend_4h, 'risk_bal': self.risk_manager.risk_bankroll}
                        
                        ok, msg = self.trade_executor.execute_buy(is_l, sd, bs, pr, d["poly"]["up_id" if sd=="UP" else "down_id"], context=ctx, reason=f"Pending: {res}")
                        if ok:
                            self.window_bets[f"{name}_{time.time()}"] = {"side":sd,"entry":pr,"cost":bs}
                            self.risk_manager.register_bet(bs); self.portfolios[name].record_trade(sd, pr, bs, bs/pr)
                            self.log_msg(f"[bold green]EXECUTED PENDING {name}[/]: {msg}")
                        else:
                            self.log_msg(f"[bold red]FAILED PENDING {name}[/]: {msg}")
                            
                        # Cleanup pending state regardless of result
                        del self.pending_bets[name]
                        try:
                            lbl = self.query_one(f"#lbl_{name[:3].lower()}")
                            lbl.remove_class("blinking")
                        except: pass
            # --------------------------------

                for name, sc in self.scanners.items():
                    if not self.query_one(scanner_map[name]).value: continue
                    
                    # 1. Check Signal
                    res = sc.get_signal(d) if hasattr(sc, "get_signal") else "WAIT"
                    # Backward compatibility for scanners without get_signal() wrapper
                    if res == "WAIT" and name == "NPattern": res = sc.analyze(ph, d["opn"])
                    elif res == "WAIT" and name == "Fakeout": res = sc.analyze(ph, d["opn"], "GREEN" if d["cur"] > d["opn"] else "RED")
                    elif res == "WAIT" and name == "Momentum":
                        base_t = getattr(sc, "base_threshold", sc.threshold)
                        if self.mom_buy_mode == "ADV":
                            atr = getattr(self.market_data_manager, "atr_5m", 0)
                            adj = 0
                            if atr <= self.mom_adv_settings["atr_low"]: adj = self.mom_adv_settings["stable_offset"] / 100.0
                            elif atr >= self.mom_adv_settings["atr_high"]: adj = self.mom_adv_settings["chaos_offset"] / 100.0
                            sc.threshold = base_t + adj
                        else:
                            # Standard mode uses the base directly. No UI querying here!
                            sc.threshold = base_t
                        res = sc.analyze(elapsed, d["poly"]["up_bid"], d["poly"]["down_bid"])
                    elif res == "WAIT" and name == "RSI": res = sc.analyze(rsi, d["cur"], lbb, 300-elapsed)
                    elif res == "WAIT" and name == "TrapCandle": res = sc.analyze(ph, d["opn"])
                    elif res == "WAIT" and name == "MidGame": res = sc.analyze(ph, d["opn"], elapsed, self.market_data_manager.trend_4h)
                    elif res == "WAIT" and name == "LateReversal": res = sc.analyze(ph, d["opn"], elapsed)
                    elif res == "WAIT" and name == "BullFlag": res = sc.analyze(d["c60"])
                    elif res == "WAIT" and name == "PostPump": res = sc.analyze(d["cur"], d["opn"], {})
                    elif res == "WAIT" and name == "StepClimber": res = sc.analyze(d["c60"])
                    elif res == "WAIT" and name == "Slingshot": res = sc.analyze(d["c60"])
                    elif res == "WAIT" and name == "MinOne": res = sc.analyze(ph, elapsed)
                    elif res == "WAIT" and name == "Liquidity": res = sc.analyze(d["cur"], min(d["l60"]) if d["l60"] else 0, d["opn"])
                    elif res == "WAIT" and name == "Cobra": res = sc.analyze(d["c60"], d["cur"], elapsed)
                    elif res == "WAIT" and name == "Mesa": res = sc.analyze(ph, d["opn"], elapsed)
                    elif res == "WAIT" and name == "MeanReversion": res = sc.analyze(ph, fbb, self.market_data_manager.trend_4h)
                    elif res == "WAIT" and name == "GrindSnap": res = sc.analyze(ph, elapsed)
                    elif res == "WAIT" and name == "VolCheck": res = sc.analyze(d["c60"], d["cur"], d["opn"], elapsed, d["poly"]["up_bid"], d["poly"]["down_bid"])
                    elif res == "WAIT" and name == "Moshe": res = sc.analyze(elapsed, d["cur"], d["opn"], self.market_data_manager.trend_4h, d["poly"]["up_bid"], d["poly"]["down_bid"])
                    elif res == "WAIT" and name == "ZScore": res = sc.analyze(ph, d["opn"], elapsed)

                    if res == "WAIT": continue
                    if res == "NONE":
                        reason = getattr(sc, "last_skip_reason", None)
                        if reason and f"SKIP_{name}_{reason}" not in self.skipped_logs:
                            self.log_msg(f"SKIP {name} | {reason}", level="SCAN")
                            self.skipped_logs.add(f"SKIP_{name}_{reason}")
                        continue
                        
                    if "BET_" in str(res) and not any(k.startswith(f"{name}_") for k in self.window_bets):
                        # 2. 1-Trade-Max Guard
                        if self.query_one("#cb_one_trade").value and self.window_bets: continue
                        
                        # 3. Strong Only Filter
                        if self.query_one("#cb_strong").value:
                            strong_keywords = {"STRONG", "CONFIRMED", "HEAVY", "MAX", "90", "SNIPER"}
                            if not any(k in str(res).upper() for k in strong_keywords):
                                if f"SKIP_STRONG_{name}" not in self.skipped_logs:
                                    self.log_msg(f"SKIP {name} | Strong Only active (Sig: {res})", level="SCAN")
                                    self.skipped_logs.add(f"SKIP_STRONG_{name}")
                                continue

                        # 4. Minimum Difference Filter
                        try: min_diff = float(self.query_one("#inp_min_diff").value)
                        except: min_diff = 0
                        if abs(d["cur"] - d["opn"]) < min_diff:
                            if f"SKIP_DIFF_{name}" not in self.skipped_logs:
                                self.log_msg(f"SKIP {name} | Diff ${abs(d['cur']-d['opn']):.2f} < Min ${min_diff:.2f}", level="SCAN")
                                self.skipped_logs.add(f"SKIP_DIFF_{name}")
                            continue

                        # 5. Bet Sizing
                        bs = self.risk_manager.calculate_bet_size(str(res), self.portfolios[name].balance, self.portfolios[name].consecutive_losses, {'trend_4h':self.market_data_manager.trend_4h, 'direction':"UP" if "UP" in str(res) else "DOWN"})
                        if "MOM" in str(res):
                            if getattr(self, "mom_buy_mode", "STD") != "STD":
                                continue
                            try: bs = float(self.query_one("#inp_amount").value)
                            except: bs = self.portfolios[name].balance * 0.12
                        
                        weight = self.scanner_weights.get(name[:3].upper(), 1.0)
                        bs = bs * weight

                        # 6. Whale Protect
                        if self.query_one("#cb_whale").value:
                            max_whale = self.risk_manager.risk_bankroll * 0.25
                            if bs > max_whale:
                                self.log_msg(f"Whale Protect cap {name} ${bs:.2f} -> ${max_whale:.2f}", level="ADMIN")
                                bs = max_whale
                        
                        if bs > 0:
                            sd = "UP" if "UP" in str(res) else "DOWN"
                            pr = self.market_data["up_ask"] if sd == "UP" else self.market_data["down_ask"]
                            
                            # 7. Price Bounds
                            try: min_pr = float(self.query_one("#inp_min_price").value)
                            except: min_pr = 0.01
                            try: max_pr = float(self.query_one("#inp_max_price").value)
                            except: max_pr = 0.99
                            
                            if pr < min_pr or pr > max_pr:
                                if pr < min_pr and name not in self.pending_bets:
                                    self.pending_bets[name] = {"side": sd, "bs": bs, "res": res}
                                    try: self.query_one(f"#lbl_{name[:3].lower()}").add_class("blinking")
                                    except: pass
                                    self.log_msg(f"QUEUED {name} {sd} | Wait for {min_pr*100:.1f}c (Now {pr*100:.1f}c)", level="SCAN")
                                elif pr > max_pr:
                                    if f"SKIP_MAX_{name}" not in self.skipped_logs:
                                        self.log_msg(f"SKIP {name} | Price {pr*100:.1f}c > Max {max_pr*100:.1f}c", level="SCAN")
                                        self.skipped_logs.add(f"SKIP_MAX_{name}")
                                continue

                            # 8. Moshe Override
                            if "MOSHE_90" in str(res):
                                pr = 0.86; moshe_scanner = self.scanners.get("Moshe")
                                bs = getattr(moshe_scanner, "bet_size", 1.00)
                                if bs > self.risk_manager.risk_bankroll: bs = self.risk_manager.risk_bankroll
                                if bs <= 0.05: continue
                                self.log_msg(f"MOSHE 0.86 Override | Payout Opt: 0.99", level="ADMIN")

                            if pr and 0.01 < pr < 0.99:
                                ok, msg = self.trade_executor.execute_buy(self.query_one("#cb_live").value, sd, bs, pr, d["poly"]["up_id" if sd=="UP" else "down_id"], context={'rsi':rsi,'trend':self.market_data_manager.trend_4h}, reason=res)
                                if ok:
                                    self.window_bets[f"{name}_{time.time()}"] = {"side":sd,"entry":pr,"cost":bs,"algorithm":name}
                                    self.risk_manager.register_bet(bs); self.portfolios[name].record_trade(sd, pr, bs, bs/pr)
                                    self.session_total_trades += 1
                                    self.log_msg(f"BUY {name} {sd} @ {pr*100:.1f}c | {msg}", level="TRADE")
                                else:
                                    self.log_msg(f"BUY FAILED {name}: {msg}", level="ERROR")                            

            await self._check_tpsl()
            self.update_balance_ui(); self.update_sell_buttons()
            self.query_one("#p_up").update(f"{self.market_data['up_ask']*100:.1f}¢")
            self.query_one("#p_down").update(f"{self.market_data['down_ask']*100:.1f}¢")
            self.query_one("#p_btc").update(f"${self.market_data['btc_price']:,.2f}")
            self.query_one("#p_trend").update(f"Trend 1H: {self.market_data_manager.trend_4h}")
            self.query_one("#p_atr").update(f"ATR 5m: ${self.market_data_manager.atr_5m:.2f}")
            self.query_one("#p_btc_open").update(f"Open: ${self.market_data['btc_open']:,.2f}")
            df = self.market_data['btc_price'] - self.market_data['btc_open']
            self.query_one("#p_btc_diff").update(f"Diff: {'+' if df>=0 else '-'}${abs(df):.2f}")
            self.query_one("#p_trend").update(f"Trend 1H: {self.market_data_manager.trend_4h}")

        except Exception as e: self.log_msg(f"[red]Loop Err: {e}[/]")

    async def _check_tpsl(self):
        is_tp_active = self.query_one("#cb_tp_active").value
        tp = self.committed_tp
        sl = self.committed_sl
        for bid, info in list(self.window_bets.items()):
            if not isinstance(info, dict): continue
            if info.get("closed"): continue
            side = info["side"]; ent = info["entry"]; cur = self.market_data["up_price"] if side=="UP" else self.market_data["down_price"]
            roi = (cur-ent)/ent; reason = None
            
            # 1. Universal Max Profit (99c Guaranteed Win Exit)
            if cur >= 0.99: 
                reason = f"MAX PROFIT (99¢) | Ent: {ent*100:.1f}¢ -> {cur*100:.1f}¢ (+{roi*100:.1f}%)"
            # 2. UI-configurable TP/SL Check
            # TP is a PRICE threshold (TP 80 = sell at 80¢). Binary options cap at 99¢,
            # so ROI-based TP from a 62¢ entry would require 111¢ — never reachable.
            # SL stays ROI-based (SL 40 = cut loss when down 40% from entry).
            elif is_tp_active:
                if cur >= tp: reason = f"TP HIT | Ent: {ent*100:.1f}¢ -> {cur*100:.1f}¢ (+{roi*100:.1f}%)"
                elif roi <= -sl: reason = f"SL HIT | Ent: {ent*100:.1f}¢ -> {cur*100:.1f}¢ ({roi*100:.1f}%)"
                
            if reason:
                is_l = self.query_one("#cb_live").value
                cbid = self.market_data["up_bid"] if side=="UP" else self.market_data["down_bid"]
                lp = cbid if not is_l else max(0.02, cbid-0.02)
                ok, msg, realized_rev = await asyncio.to_thread(self.trade_executor.execute_sell, is_l, side, self.market_data["up_id" if side=="UP" else "down_id"], lp, cbid, reason=reason)
                if ok:
                    info["closed"] = True
                    realized_loss = info["cost"] - realized_rev
                    if realized_rev > 0: self._add_risk_revenue(realized_rev)
                    
                    if realized_rev > info["cost"]:
                        self.session_win_count += 1 # TP/Max Profit hit
                        self.log_msg(f"{reason} | [bold green]WIN[/] | Closed {side} @ {cur*100:.1f}c", level="MONEY")
                    else:
                        self.log_msg(f"{reason} | [bold red]LOSS[/] | Closed {side} @ {cur*100:.1f}c", level="MONEY")
                    
                    # --- SL+ RECOVERY LOGIC ---
                    # Guard: never chain recovery on a recovery bet to prevent infinite loops
                    is_recovery_bet = bid.startswith("SL+_Recovery")
                    if reason.startswith("SL HIT") and self.sl_plus_mode and realized_loss > 0 and not is_recovery_bet:
                        opp_side = "DOWN" if side == "UP" else "UP"
                        opp_p = self.market_data["up_ask" if opp_side == "UP" else "down_ask"]
                        if 0.05 < opp_p < 0.90:
                            # Recovery = original cost, capped only as absolute safety floor (must have at least $1 left after)
                            rec_cost = info["cost"]
                            if rec_cost > self.risk_manager.risk_bankroll - 1.0:
                                rec_cost = max(0, self.risk_manager.risk_bankroll - 1.0)
                                self.log_msg(f"[yellow]SL+ RECOVERY CAP:[/][dim] Original ${info['cost']:.2f} capped at available bankroll (${rec_cost:.2f})[/]")
                            
                            if rec_cost >= 0.10:
                                self.log_msg(f"[bold cyan]SL+ RECOVERY:[/][dim] Loss ${realized_loss:.2f} -> Buying ${rec_cost:.2f} {opp_side} @ {opp_p*100:.1f}¢[/]")
                                ok_rec, msg_rec = await asyncio.to_thread(self.trade_executor.execute_buy, is_l, opp_side, rec_cost, opp_p, self.market_data["up_id" if opp_side=="UP" else "down_id"], context={}, reason="SL+_Recovery")
                                if ok_rec:
                                    self.window_bets[f"SL+_Recovery_{time.time()}"] = {"side":opp_side,"entry":opp_p,"cost":rec_cost}
                                    self.risk_manager.register_bet(rec_cost)
                                    self.log_msg(f"[bold green]RECOVERY EXECUTED:[/] {msg_rec}")
                                    self.update_balance_ui() # Refresh bankroll display
                                else:
                                    self.log_msg(f"[bold red]RECOVERY FAILED:[/] {msg_rec}")

    async def _run_last_second_exit(self, is_live):
        # if not is_live: return # REMOVED: We want Sim Logic for Hypothetical Logging
        sides = set()
        if is_live: sides.update(info["side"] for info in self.window_bets.values() if not info.get("closed"))
        else:
            if self.sim_broker.shares["UP"] > 0: sides.add("UP")
            if self.sim_broker.shares["DOWN"] > 0: sides.add("DOWN")
        
        for side in sides:
            # Emergency Whale Shield (v5.9)
            if self.mom_buy_mode == "ADV":
                adv = self.mom_adv_settings
                rem = TradingConfig.WINDOW_SECONDS - (time.time() - self.market_data["start_ts"])
                if rem <= adv["shield_time"]:
                    up_p = self.market_data.get("up_price", 0.5)
                    reach = adv["shield_reach"] / 100.0
                    if abs(up_p - 0.50) <= reach:
                        self.log_msg(f"🛡️ WHALE SHIELD: Market too tight ({up_p*100:.1f}¢). Emergency Exit.", level="MONEY")
                        await self.trigger_sell_all("UP")
                        await self.trigger_sell_all("DOWN")
                        self.last_second_exit_triggered = True
                        return

            tid = self.market_data["up_id" if side=="UP" else "down_id"]
            cbid = self.market_data["up_bid"] if side=="UP" else self.market_data["down_bid"]

            # Standard TP/SL Exit logic
            if not is_live:
                # SIM HYPOTHETICAL LOGGING
                # Calculate exact shares from window_bets for THIS window
                shares = sum((info["cost"]/info.get("entry", 0.5)) for info in self.window_bets.values() if info["side"] == side and not info.get("closed"))
                if shares > 0:
                    revenue = shares * cbid
                    # "If we were live we would sell X shares of winning side at 99c right now..."
                    self.log_msg(f"[bold magenta]SIM INFO: Live would sell {shares:.2f} {side} @ {cbid*100:.1f}¢ (Value: ${revenue:.2f})[/]")
                continue # Skip actual execution for Sim, let it expire/settle at $1.00

            # LIVE: Skip if position has clearly lost (bid < 10¢ with no triggered SL).
            # At this point with seconds left, anything under 10¢ will expire worthless —
            # attempting a sell just generates PolyApiException / "Size too small" errors.
            if cbid < 0.10:
                self.log_msg(f"[dim]⏱ SKIP FINAL EXIT {side} — position at {cbid*100:.1f}¢, clearly lost. Letting expire.[/]")
                continue

            # For LIVE: User requested strict resting limit order at $0.99
            lp = 0.99 if is_live else 0.0
            
            
            # Execute synchronously in a background thread to prevent UI lockup 
            ok, msg, _ = await asyncio.to_thread(self.trade_executor.execute_sell, is_live, side, tid, lp, cbid, "Last Second Exit")
            if ok:
                self.log_msg(f"[bold {'red' if is_live else 'green'}]⏱ FINAL EXIT {side}: {msg}[/]")
                for info in self.window_bets.values(): 
                    if info["side"] == side: info["closed"] = True
                try:
                    # Parse revenue from LIVE msg: "Total: $3.45)" OR SIM msg: "for $3.45 ("
                    if "Total: $" in msg:
                        revenue = float(msg.split("Total: $")[1].split(")")[0])
                    elif " for $" in msg:
                        revenue = float(msg.split(" for $")[1].split(" ")[0])
                    else:
                        revenue = 0.0
                    if revenue > 0: self._add_risk_revenue(revenue)
                except: pass
            else:
                self.log_msg(f"[bold red]⏱ FINAL EXIT {side} FAILED:[/] {msg}")

    async def update_timer(self):
        # Update session runtime regardless of market data status
        run = int(time.time() - self.app_start_time)
        self.query_one("#lbl_runtime").update(f" | RUN: {run//3600:02d}:{(run%3600)//60:02d}:{run%60:02d}")

        if not self.market_data["start_ts"]: return
        
        rem = max(0, TradingConfig.WINDOW_SECONDS - int(time.time() - self.market_data["start_ts"]))
        self.time_rem_str = f"{rem//60:02d}:{rem%60:02d}"
        self.query_one("#lbl_timer_big").update(self.time_rem_str)
        if rem <= 1 and not self.last_second_exit_triggered:
            self.last_second_exit_triggered = True
            await self._run_last_second_exit(self.query_one("#cb_live").value)

        # --- ADV MOM Analytics: 60s Pre-Open Velocity ---
        if rem == 60 and self.mom_analytics["btc_pre_60s"] is None:
            self.mom_analytics["btc_pre_60s"] = self.market_data.get("btc_price", 0)

        # --- NEXT WINDOW PREVIEW ---
        # 20 seconds before end, fetch the NEXT window's UP/DOWN prices and log them.
        # Next slug = btc-updown-5m-{current_start_ts + 300}
        if rem <= 20 and not self.next_window_preview_triggered and self.market_data["start_ts"] > 0:
            self.next_window_preview_triggered = True
            next_ts = self.market_data["start_ts"] + TradingConfig.WINDOW_SECONDS
            next_slug = f"btc-updown-5m-{next_ts}"
            def _fetch_next():
                try:
                    d = self.market_data_manager.fetch_polymarket(next_slug)
                    up_bid  = d.get("up_bid",  0)
                    dn_bid  = d.get("down_bid", 0)
                    up_ask  = d.get("up_ask",  0)
                    dn_ask  = d.get("down_ask", 0)
                    if up_bid > 0 or dn_bid > 0:
                        self.call_from_thread(
                            self.log_msg,
                            f"NEXT WINDOW ({next_slug}): "
                            f"UP bid=[dim]{up_bid*100:.1f}¢[/] ask=[bold green]{up_ask*100:.1f}¢[/]  "
                            f"DN bid=[dim]{dn_bid*100:.1f}¢[/] ask=[bold red]{dn_ask*100:.1f}¢[/]"
                        )
                    else:
                        self.call_from_thread(self.log_msg, f"[dim]🔭 Next window not yet available ({next_slug})[/]")
                except Exception as e:
                    self.call_from_thread(self.log_msg, f"[dim]🔭 Next window fetch failed: {e}[/]")
            import threading
            threading.Thread(target=_fetch_next, daemon=True).start()
        # ---------------------------

        # --- PRE-BUY NEXT WINDOW (rem <= 15, MOM Pre-Buy or Hybrid mode) ---
        if (rem <= 15 and not self.pre_buy_triggered
                and self.mom_buy_mode in ["PRE", "HYBRID"]
                and self.market_data["start_ts"] > 0
                and self.query_one("#cb_mom").value):
            self.pre_buy_triggered = True
            next_ts   = self.market_data["start_ts"] + TradingConfig.WINDOW_SECONDS
            next_slug = f"btc-updown-5m-{next_ts}"
            is_live   = self.query_one("#cb_live").value
            try: bet_size = float(self.query_one("#inp_amount").value)
            except: bet_size = 1.0
            trend = self.market_data_manager.trend_4h  # "UP" / "DOWN" / "NEUTRAL"

            def _do_prebuy():
                try:
                    d = self.market_data_manager.fetch_polymarket(next_slug)
                    up_ask = d.get("up_ask", 0)
                    dn_ask = d.get("down_ask", 0)
                    if up_ask <= 0 and dn_ask <= 0:
                        self.call_from_thread(self.log_msg, "[dim]🚀 PRE-BUY skipped — next window prices unavailable[/]")
                        return

                    # Calculate BTC Velocity and RSI for enhanced decision making
                    btc_open = self.market_data.get("btc_open", 0)
                    btc_pre_60s = self.mom_analytics.get("btc_pre_60s")
                    velocity = (btc_open - btc_pre_60s) if btc_open and btc_pre_60s else 0
                    
                    # Calculate 1m RSI
                    rsi_1m = 50.0
                    try:
                        closes, _, _, _ = self.market_data_manager.fetch_candles_60m()
                        if closes:
                            from .market import calculate_rsi
                            rsi_1m = calculate_rsi(closes, period=14)
                    except:
                        pass

                    # Capture exact 15s pre-window gap and BTC price for analytics
                    price_diff = up_ask - dn_ask
                    if self.mom_analytics["pre_15s_gap"] is None:
                        self.mom_analytics["pre_15s_gap"] = price_diff
                        self.mom_analytics["btc_pre_15s"] = self.market_data.get("btc_price", 0)
                    
                    # Debug: Log price difference calculation
                    self.call_from_thread(self.log_msg, f"[dim]DEBUG PRE-BUY: UP ask={up_ask*100:.1f}¢, DN ask={dn_ask*100:.1f}¢, diff={price_diff*100:.1f}¢, abs={abs(price_diff)*100:.1f}¢[/]")
                    
                    # Enhanced Decision Logic with Priority System:
                    # Priority 1: Velocity Reversion (Significantly negative velocity -> UP bet for mean reversion)
                    # Priority 2: RSI Trend (High RSI > 70 -> UP bet for trend continuation)
                    # Priority 3: Price Gap (Follow lead or reverse based on gap size)
                    
                    decision_reason = None
                    side = None
                    price = None
                    
                    if self.mom_buy_mode == "ADV":
                        atr = getattr(self.main_app.market_data_manager, "atr_5m", 0)
                        adv = self.main_app.mom_adv_settings
                        if atr >= adv["atr_high"] and adv["auto_stn_chaos"]:
                            self.call_from_thread(self.log_msg, f"[dim]PRE-BUY chaos skip (ATR:{atr:.1f}) -> Forcing STN[/]")
                            return
                    
                    # Priority 1: Velocity Reversion Check
                    if velocity <= -300:  # Increased threshold for more reliable signals
                        side = "UP"
                        price = up_ask
                        decision_reason = f"Velocity Reversion (BTC moved {velocity:.0f} down in 60s)"
                        self.call_from_thread(self.log_msg, f"[dim]PRE-BUY velocity reversion -> {side} ({velocity:.0f} move)[/]")
                    
                    # Priority 2: RSI Momentum Check (only if velocity didn't trigger)
                    elif side is None and rsi_1m > 70:
                        # Add trend context check with 1h trend strength levels
                        trend_1h = self.market_data_manager.trend_1h
                        
                        if trend_1h in ["S-DOWN", "M-DOWN", "W-DOWN"]:
                            # Skip RSI momentum signals during downtrends (insufficient data)
                            decision_reason = f"RSI Momentum skipped (RSI: {rsi_1m:.1f} > 70 but 1h trend is {trend_1h})"
                            self.call_from_thread(self.log_msg, f"[dim]PRE-BUY RSI momentum skipped (RSI: {rsi_1m:.1f}) - {trend_1h} detected[/]")
                            # Don't set side/price, let it fall through to price gap logic
                        else:
                            # Allow RSI momentum in uptrends or sideways markets
                            side = "UP"
                            price = up_ask
                            decision_reason = f"RSI Momentum (RSI: {rsi_1m:.1f} > 70, 1h Trend: {trend_1h})"
                            self.call_from_thread(self.log_msg, f"[dim]PRE-BUY RSI momentum -> {side} (RSI: {rsi_1m:.1f}, 1h Trend: {trend_1h})[/]")
                    
                    # Priority 3: Price Gap Logic (enhanced based on log analysis)
                    elif side is None:
                        # Enhanced gap logic: Consider market context before following lead
                        cur_up = self.market_data.get("up_price", 0.5)
                        cur_dn = self.market_data.get("down_price", 0.5)
                        winner = "UP" if cur_up >= cur_dn else "DOWN"
                        
                        # If strong velocity signal exists, prioritize it over gap following
                        if velocity <= -300:
                            # Strong negative velocity overrides gap following
                            side = "UP"
                            price = up_ask
                            decision_reason = f"Velocity Override (gap:{abs(price_diff)*100:.1f}¢, vel:{velocity:.0f})"
                            self.call_from_thread(self.log_msg, f"[dim]PRE-BUY velocity override -> {side} (gap:{abs(price_diff)*100:.1f}¢, vel:{velocity:.0f})[/]")
                        elif abs(price_diff) >= 0.03:  # Large gap (3¢+) - follow lead
                            side, price = ("UP", up_ask) if up_ask > dn_ask else ("DOWN", dn_ask)
                            if self.mom_buy_mode == "HYBRID":
                                decision_reason = f"Hybrid Lead ({abs(price_diff)*100:.1f}¢ gap)"
                                self.call_from_thread(self.log_msg, f"[dim]PRE-BUY hybrid lead ({abs(price_diff)*100:.1f}¢ gap) -> {side}[/]")
                            else:
                                decision_reason = f"Follow Lead ({abs(price_diff)*100:.1f}¢ gap)"
                                self.call_from_thread(self.log_msg, f"[dim]PRE-BUY follow lead ({abs(price_diff)*100:.1f}¢ gap) -> {side}[/]")
                        else:
                            # Small gaps (0¢-2¢) - make decision based on other factors
                            atr = getattr(self.market_data_manager, "atr_5m", 0)
                            trend_1h = self.market_data_manager.trend_1h
                            
                            # Decision logic for small gaps based on market factors
                            if trend_1h in ["S-DOWN", "M-DOWN"] and velocity < -100:
                                # Strong/Medium downtrend with some negative velocity -> UP (mean reversion)
                                side = "UP"
                                price = up_ask
                                decision_reason = f"Small Gap Mean Reversion (gap:{abs(price_diff)*100:.1f}¢, 1h trend:{trend_1h}, vel:{velocity:.0f})"
                            elif trend_1h in ["S-UP", "M-UP"] and rsi_1m < 60:
                                # Strong/Medium uptrend with low RSI -> UP (trend continuation)
                                side = "UP"
                                price = up_ask
                                decision_reason = f"Small Gap Trend Follow (gap:{abs(price_diff)*100:.1f}¢, 1h trend:{trend_1h}, rsi:{rsi_1m:.1f})"
                            elif atr > 100:
                                # High volatility ATR -> follow current winner
                                side = winner
                                price = up_ask if side == "UP" else dn_ask
                                decision_reason = f"Small Gap Volatility Follow (gap:{abs(price_diff)*100:.1f}¢, atr:{atr:.1f})"
                            else:
                                # Default: reversal for small gaps
                                side = "DOWN" if winner == "UP" else "UP"
                                price = up_ask if side == "UP" else dn_ask
                                decision_reason = f"Small Gap Reversal (gap:{abs(price_diff)*100:.1f}¢, winner:{winner})"
                            
                            self.call_from_thread(self.log_msg, f"[dim]PRE-BUY small gap decision -> {side} ({decision_reason})[/]")
                            
                            # Reversal: Identify who is winning CURRENTLY (proxy for "just won")
                            # and pick the opposite for the next window.
                            cur_up = self.market_data.get("up_price", 0.5)
                            cur_dn = self.market_data.get("down_price", 0.5)
                            winner = "UP" if cur_up >= cur_dn else "DOWN"
                            side = "DOWN" if winner == "UP" else "UP"
                            price = up_ask if side == "UP" else dn_ask
                            decision_reason = f"Reversal (gap:{abs(price_diff)*100:.1f}¢ | Winner:{winner})"
                            self.call_from_thread(self.log_msg, f"[dim]PRE-BUY reversal (gap:{abs(price_diff)*100:.1f}¢ | Winner:{winner}) -> {side}[/]")
                    
                    # ADV mode special handling for small gaps
                    if self.mom_buy_mode == "ADV" and side is None:
                        self.call_from_thread(self.log_msg, f"[dim]PRE-BUY adv skip (gap:{abs(price_diff)*100:.1f}¢) -> Deferring[/]")
                        return

                    # Execute the trade if we have a decision
                    if side and price:
                        token_id = d.get("up_id" if side == "UP" else "down_id")
                        ok, msg = self.trade_executor.execute_buy(
                            is_live, side, bet_size, price, token_id,
                            context={}, reason=f"PreBuy_{decision_reason}"
                        )
                        if ok:
                            pending = {"side": side, "entry": price, "cost": bet_size, "algorithm": "BullFlag"}
                            self.session_total_trades += 1 # Pre-Buy Trade
                            def _commit(p=pending, s=side, pr=price, m=msg, bs=bet_size):
                                self.pre_buy_pending = p
                                self.risk_manager.register_bet(bs)
                                self.log_msg(
                                    f"PRE-BUY NEXT {s} @ {pr*100:.1f}¢[dim] — "
                                    f"${bs:.2f} committed. {decision_reason}. Holding for next window ({next_slug})[/]"
                                )
                                self.update_balance_ui()
                            self.call_from_thread(_commit)
                        else:
                            self.call_from_thread(self.log_msg, f"[bold red]🚀 PRE-BUY FAILED:[/] {msg}")
                except Exception as e:
                    self.call_from_thread(self.log_msg, f"[dim]🚀 PRE-BUY error: {e}[/]")

            import threading
            threading.Thread(target=_do_prebuy, daemon=True).start()
        # ----------------------------------------------------------
            
        # Trigger Settlement precisely on the exact dot of the 59th second
        if rem <= 1 and not self.window_settled:
            self.window_settled = True
            self.trigger_settlement()

    def _check_bankroll_exhaustion(self):
        """After each settlement, freeze the bot if it can no longer afford another bet."""
        if self.halted: return

        br = self.risk_manager.risk_bankroll
        try: min_bet = float(self.query_one("#inp_amount").value)
        except: min_bet = 1.0
        hard_floor = 1.0  # Absolute minimum to even consider a bet

        # Only freeze if a bet was actually placed this window (we lost) AND
        # the bankroll can no longer cover the minimum bet size.
        had_bet = bool(self.window_bets)
        cannot_afford = br < max(min_bet, hard_floor)

        if had_bet and cannot_afford:
            self.halted = True
            is_live = self.query_one("#cb_live").value
            mode_str = "LIVE" if is_live else "SIM"

            # Final CSV snapshot
            self.dump_state_log()

            final_msg = (
                f"🔴 BOT FROZEN [{mode_str}] | Bankroll: ${br:.2f} | "
                f"Min Bet: ${min_bet:.2f} | Cannot place another trade. All scanning stopped."
            )
            self.log_msg(f"[bold red]{final_msg}[/]")

            # Write final line to console log file
            try:
                from datetime import datetime as _dt
                with open(self.console_log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*60}\nFINAL LOG — {_dt.now().strftime('%Y-%m-%d %H:%M:%S')}\n{final_msg}\n{'='*60}\n")
            except: pass

            # Show frozen modal (must run on UI thread)
            self.push_screen(BankrollExhaustedModal(br, min_bet, mode_str))

    def trigger_settlement(self):
        if self.market_data["start_ts"] == 0: return

        # 1. Poly-Decisive Logic (v5.9.4)
        # If token price is > 0.90, that side is the definitive winner regardless of BTC sync issues.
        up_bid = self.market_data.get("up_bid", 0)
        dn_bid = self.market_data.get("down_bid", 0)
        btc_p = self.market_data.get("btc_price", 0)
        btc_o = self.market_data.get("btc_open", 0)
        
        if up_bid >= 0.90:
            winner = "UP"
            reason = "UP side won decisively"
        elif dn_bid >= 0.90:
            winner = "DOWN"
            reason = "DOWN side won decisively"
        else:
            winner = "UP" if btc_p >= btc_o else "DOWN"
            reason = f"BTC Move (${btc_p:,.2f} vs Open ${btc_o:,.2f})"

        self.log_msg(f"SETTLED: [bold white]{winner}[/] | [dim]{reason}[/]", level="MONEY")
        payout, net_pnl = self.sim_broker.settle_window(winner)
        
        # BullFlag Research Logging - Log trades with settings
        for info in self.window_bets.values():
            if not info.get("closed") and info.get("algorithm") == "BullFlag":
                bullflag_scanner = self.scanners.get("BullFlag")
                if bullflag_scanner and hasattr(bullflag_scanner, 'log_research_trade'):
                    # Get current market data for research logging
                    rsi_1m = getattr(self.market_data_manager, 'rsi_1m', 0)
                    btc_velocity = getattr(self.market_data_manager, 'btc_velocity', 0)
                    atr_5m = getattr(self.market_data_manager, 'atr_5m', 0)
                    
                    # Log the trade with research data
                    result = "WIN" if info.get("side") == winner else "LOSS"
                    bullflag_scanner.log_research_trade(
                        info.get("entry", 0),  # Entry price stored when signal triggered
                        self.market_data.get("btc_price", 0),  # Exit price at settlement
                        result,
                        self.market_data.get("start_ts", 0),  # Window ID
                        rsi_1m,
                        btc_velocity,
                        atr_5m
                    )
        
        for p in self.portfolios.values(): p.settle_window(winner, self.market_data["btc_price"], self.market_data["btc_open"])
        
        is_live = self.query_one("#cb_live").value
        # Accuracy: Count settlement winners
        for info in self.window_bets.values():
            if not info.get("closed") and info.get("side") == winner:
                self.session_win_count += 1
        
        self.session_windows_settled += 1
        if self.session_windows_settled > 1:
            acc_val = (self.session_win_count / self.session_total_trades * 100) if self.session_total_trades > 0 else 0
            acc_str = f"{acc_val:.1f}%"
        else:
            acc_str = "N/A"

        upt = int(time.time() - self.app_start_time)
        upt_str = f"{upt//3600:02d}:{(upt%3600)//60:02d}:{upt%60:02d}"
        self.log_msg(f"PULSE | RUN: {upt_str} | Session Trades: {self.session_total_trades} | Accuracy: {acc_str}", level="ADMIN")
        
        self._add_risk_revenue(payout)

        # --- BANKROLL EXHAUSTION CHECK ---
        self._check_bankroll_exhaustion()
        if self.halted: return

        # --- LIVE SETTLEMENT REFILL ---
        if is_live:
            live_win_payout = 0.0
            for info in self.window_bets.values():
                if info.get("closed"): continue
                if info["side"] != winner: continue
                entry = info.get("entry", 0)
                cost  = info.get("cost", 0)
                if entry > 0 and cost > 0:
                    shares = cost / entry
                    live_win_payout += shares * 1.00  # Settles at $1.00/share
            if live_win_payout > 0:
                self.log_msg(f"LIVE Settlement Refill: +${live_win_payout:.2f} (winning shares x $1.00)", level="MONEY")
                self._add_risk_revenue(live_win_payout)

        self.risk_manager.reset_window(); self.last_second_exit_triggered = False
        self.update_balance_ui(); self.window_bets.clear()
        for s in self.scanners.values(): s.reset()
        self.market_data_manager.reset_history()

        # --- Write Momentum Analytics (v5.9.4) ---
        try:
            ma = self.mom_analytics
            btc_open = self.market_data.get("btc_open", 0)
            btc_pre_60 = ma.get("btc_pre_60s")
            velocity = (btc_open - btc_pre_60) if btc_open and btc_pre_60 else 0
            
            dd_up = (btc_open - ma["window_low"]) if btc_open and ma["window_low"] else 0
            dd_dn = (ma["window_high"] - btc_open) if btc_open and ma["window_high"] else 0

            # 1m RSI and Volume
            rsi_1m, vol_1m = 50.0, 0.0
            try:
                closes, _, _, raw = self.market_data_manager.fetch_candles_60m()
                if closes:
                    from .market import calculate_rsi
                    rsi_1m = calculate_rsi(closes, period=14)
                    if len(raw) >= 2:
                        vol_1m = float(raw[-2][5]) # Index 5 is volume
            except: pass

            line = (
                f"{self.market_data['start_ts']},"
                f"{ma['pre_15s_gap'] if ma['pre_15s_gap'] is not None else ''},"
                f"{ma['btc_pre_15s'] if ma['btc_pre_15s'] is not None else ''},"
                f"{ma['btc_pre_60s'] if ma['btc_pre_60s'] is not None else ''},"
                f"{velocity:.2f},"
                f"{ma['gap_5s'] if ma['gap_5s'] is not None else ''},"
                f"{ma['btc_5s'] if ma['btc_5s'] is not None else ''},"
                f"{ma['gap_10s'] if ma['gap_10s'] is not None else ''},"
                f"{ma['btc_10s'] if ma['btc_10s'] is not None else ''},"
                f"{ma['gap_15s'] if ma['gap_15s'] is not None else ''},"
                f"{ma['btc_15s'] if ma['btc_15s'] is not None else ''},"
                f"{ma['spread_15s'] if ma['spread_15s'] is not None else ''},"
                f"{ma['up_bid_15s'] if ma['up_bid_15s'] is not None else ''},"
                f"{ma['down_bid_15s'] if ma['down_bid_15s'] is not None else ''},"
                f"{ma['first_55c_side'] or ''},{ma['first_55c_time'] if ma['first_55c_time'] is not None else ''},"
                f"{ma['first_60c_side'] or ''},{ma['first_60c_time'] if ma['first_60c_time'] is not None else ''},"
                f"{ma['first_65c_side'] or ''},{ma['first_65c_time'] if ma['first_65c_time'] is not None else ''},"
                f"{rsi_1m:.2f},{vol_1m:.0f},"
                f"{dd_up:.2f},{dd_dn:.2f},"
                f"{self.market_data_manager.atr_5m:.2f},"
                f"{btc_open:.2f},"
                f"{self.market_data.get('btc_price', 0):.2f},"
                f"{winner}"
            )
            with open(self.mom_adv_log_file, 'a') as f:
                f.write(line + "\n")
        except Exception as e:
            self.log_msg(f"[yellow]MOM Analytics Log Error: {e}[/]")

        self.mom_analytics = self._reset_mom_analytics()

        self.log_msg("────────────────── WINDOW END ──────────────────", level="ADMIN")
        self.log_msg("") # Whitespace after window end

    def _add_risk_revenue(self, amount):
        """Adds revenue back to the usable bankroll with strict wallet clamping."""
        if not self.risk_initialized: return
        
        is_live = self.query_one("#cb_live").value
        main_bal = self.live_broker.balance if is_live else self.sim_broker.balance

        # 1. Add revenue to current bankroll
        self.risk_manager.risk_bankroll += amount
        self.window_realized_revenue += amount  # track for settlement log

        # 2. In LIVE mode: allow target_bankroll to grow with wins so the bankroll
        #    compounds. Without this, every win was silently clamped back to the
        #    initial target set at session start.
        #    In SIM mode: keep the hard clamp so the sim can't exceed its theoretical cap.
        if is_live:
            if self.risk_manager.risk_bankroll > self.risk_manager.target_bankroll:
                self.risk_manager.target_bankroll = self.risk_manager.risk_bankroll
        else:
            if self.risk_manager.risk_bankroll > self.risk_manager.target_bankroll:
                self.risk_manager.risk_bankroll = self.risk_manager.target_bankroll

        # 3. Always cap by actual wallet balance (live balance updates via API)
        if is_live:
            self.live_broker.update_balance()
            main_bal = self.live_broker.balance
        if self.risk_manager.risk_bankroll > main_bal:
            self.risk_manager.risk_bankroll = main_bal
            if is_live and self.risk_manager.target_bankroll > main_bal:
                self.risk_manager.target_bankroll = main_bal
           
        self.update_balance_ui()

    async def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "btn_settings":
            self.push_screen(GlobalSettingsModal(self))
        elif "btn_buy_" in bid: 
            await self.trigger_buy("UP" if "_up" in bid else "DOWN")
        elif "btn_sell_" in bid:
            await self.trigger_sell_all("UP" if "_up" in bid else "DOWN")

    async def trigger_buy(self, side):
        if hasattr(self, "_last_manual_buy") and time.time() - self._last_manual_buy < 2.0:
            return self.log_msg("[yellow]Manual Buy Debounce Active...[/]")
        self._last_manual_buy = time.time()
        
        try: val = float(self.query_one("#inp_amount").value)
        except: return self.log_msg("[red]Invalid Amount[/]")
        if self.risk_initialized and val > self.risk_manager.risk_bankroll + 0.01: return self.log_msg("[red]Insuff Risk Cap[/]")
        is_l = self.query_one("#cb_live").value
        pr = self.market_data["up_ask" if side=="UP" else "down_ask"]
        if is_l and pr >= 0.98: return self.log_msg("[red]Price too high[/]")
        tid = self.market_data["up_id" if side=="UP" else "down_id"]
        
        # Manual Context
        ctx = {
            'signal_price': self.market_data.get('btc_price', 0),
            'rsi': self.market_data.get('rsi', 0),
            'trend': self.market_data_manager.trend_4h,
            'risk_bal': self.risk_manager.risk_bankroll
        }
        
        ok, msg = self.trade_executor.execute_buy(is_l, side, val, pr or 0.5, tid, context=ctx, reason="Manual")
        if ok:
            self.session_total_trades += 1 # Manual Buy
            self.log_msg(f"[bold {'red' if is_l else 'green'}]{msg}[/]")
            if self.risk_initialized: self.risk_manager.register_bet(val)
            self.window_bets[f"Manual_{time.time()}"] = {"side":side,"entry":pr or 0.5,"cost":val}
        else:
            self.log_msg(f"[bold red]MANUAL BUY FAILED:[/] {msg}")
            
        self.update_balance_ui(); self.update_sell_buttons()

    async def trigger_sell_all(self, side):
        is_l = self.query_one("#cb_live").value
        tid = self.market_data["up_id" if side=="UP" else "down_id"]
        # Use simple ternary for bid to avoid confusion
        cbid = self.market_data["up_bid"] if side=="UP" else self.market_data["down_bid"]
        lp = cbid if not is_l else max(0.02, cbid-0.05)
        
        # Debug shares in sim mode
        if not is_l:
            s_shares = self.sim_broker.shares.get(side, 0.0)
            if s_shares <= 0:
                self.log_msg(f"[dim]Admin:[/] Manual Sell {side} requested but local shares = {s_shares:.2f}")

        ok, msg, revenue = self.trade_executor.execute_sell(is_l, side, tid, lp, cbid, reason="Manual")
        if ok:
            self.log_msg(f"[bold {'red' if is_l else 'green'}]{msg}[/]")
            if revenue > 0:
                self._add_risk_revenue(revenue)
                # Count as win if realized revenue exceeds total cost of that side
                side_cost = sum(info["cost"] for info in self.window_bets.values() if info.get("side") == side and not info.get("closed"))
                if revenue > side_cost:
                    self.session_win_count += 1
            # Mark window_bets as closed so settlement refill doesn't double-count
            for info in self.window_bets.values():
                if info.get("side") == side and not info.get("closed"):
                    info["closed"] = True
        else:
            self.log_msg(f"[bold red]MANUAL SELL FAILED:[/] {msg}")
            
        self.update_balance_ui(); self.update_sell_buttons()

from textual.screen import ModalScreen
from .scanners import ALGO_INFO

from textual.widgets import Static

class GlobalSettingsModal(ModalScreen):
    """A modal that shows global settings like CSV log frequency."""
    BINDINGS = [("escape", "dismiss", "Dismiss")]
    def __init__(self, main_app=None):
        super().__init__()
        self.main_app = main_app

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield Static("[bold #00ffff]Global Settings[/]", id="modal_title")
            with Horizontal(id="modal_csv_freq"):
                yield Label("CSV Log Freq (s):", id="lbl_csv_freq")
                yield Input(placeholder="15", id="inp_csv_freq")
            with Horizontal(id="modal_footer"):
                yield Button("SAVE & CLOSE", id="btn_modal_close", variant="primary")

    def on_mount(self):
        self.styles.align = ("center", "middle")
        
        container = self.query_one("#modal_container")
        container.styles.background = "#222222"
        container.styles.border = ("thick", "#00ffff")
        container.styles.padding = (1, 2)
        container.styles.width = 40
        container.styles.height = "auto"
        container.styles.align = ("center", "middle")
        
        self.query_one("#modal_title").styles.margin = (0, 0, 1, 0)
        self.query_one("#modal_title").styles.text_align = "center"
        self.query_one("#modal_title").styles.width = "100%"
        
        row = self.query_one("#modal_csv_freq")
        row.styles.height = 3
        row.styles.align = ("center", "middle")
        row.styles.margin = (0, 0, 2, 0)
        
        self.query_one("#inp_csv_freq").styles.width = 10
        self.query_one("#lbl_csv_freq").styles.margin = (1, 1, 0, 0)
        
        if self.main_app and hasattr(self.main_app, "csv_log_freq"):
            self.query_one("#inp_csv_freq").value = str(self.main_app.csv_log_freq)

        footer = self.query_one("#modal_footer")
        footer.styles.height = "auto"
        footer.styles.align = ("center", "middle")
        footer.styles.width = "100%"

    @on(Button.Pressed, "#btn_modal_close")
    def close_modal(self):
        if self.main_app:
            try:
                freq = int(self.query_one("#inp_csv_freq").value)
                if freq > 0:
                    self.main_app.csv_log_freq = freq
            except Exception:
                pass
        self.dismiss()

from textual.widgets import Static

class AlgoInfoModal(ModalScreen):
    """A modal that shows algo details."""
    BINDINGS = [("escape", "dismiss", "Dismiss")]
    def __init__(self, name, full_name, description, main_app=None):
        super().__init__()
        self.algo_id = name
        self.full_name = full_name
        self.description = description
        self.main_app = main_app

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield Static(f"[bold cyan]{self.algo_id}[/] - {self.full_name}", id="modal_title")
            yield Static(self.description, id="modal_body")
            
            with Horizontal(id="modal_algo_weight"):
                yield Label("Algo Weight (x):", id="lbl_algo_weight")
                yield Input(placeholder="1.0", id="inp_algo_weight")
            
            # Additional settings for specific algorithms
            if self.algo_id == "MOS":
                with Horizontal(id="modal_mos_bet"):
                    yield Label("Bet Size ($):", id="lbl_mos_bet")
                    yield Input(placeholder="1.00", id="inp_mos_bet")
                with Horizontal(id="modal_mos_pt1"):
                    yield Label("Pt1 (T / D$):", id="lbl_mos_pt1")
                    yield Input(placeholder="Time 1", id="inp_mos_t1")
                    yield Input(placeholder="Diff 1", id="inp_mos_d1")
                with Horizontal(id="modal_mos_pt2"):
                    yield Label("Pt2 (T / D$):", id="lbl_mos_pt2")
                    yield Input(placeholder="Time 2", id="inp_mos_t2")
                    yield Input(placeholder="Diff 2", id="inp_mos_d2")
                with Horizontal(id="modal_mos_pt3"):
                    yield Label("Pt3 (T / D$):", id="lbl_mos_pt3")
                    yield Input(placeholder="Time 3", id="inp_mos_t3")
                    yield Input(placeholder="Diff 3", id="inp_mos_d3")
            elif self.algo_id == "MOM":
                with Horizontal(id="modal_mom_row1"):
                    yield Label("Mode:", id="lbl_mom_mode")
                    yield Input(placeholder="TIME", id="inp_mom_mode")
                    yield Label("Duration(s):", id="lbl_mom_duration")
                    yield Input(placeholder="10", id="inp_mom_duration")
                with Horizontal(id="modal_mom_threshold"):
                    yield Label("Threshold ¢ (51-70):", id="lbl_mom_threshold")
                    yield Input(placeholder="60", id="inp_mom_threshold")
                with Vertical(id="modal_mom_buymode_grid"):
                    yield Label("Buy Mode:", id="lbl_mom_buymode")
                    with Horizontal(classes="buy_mode_row"):
                        yield Checkbox(label="STN",  value=True,  id="cb_mom_std", tooltip="Standard Momentum — Threshold/time signals after window opens.")
                        yield Checkbox(label="PBN", value=False, id="cb_mom_pre", tooltip="Pre-Buy Next — Prediction-based entry at T-15s using velocity and RSI.")
                    with Horizontal(classes="buy_mode_row"):
                        yield Checkbox(label="HBR", value=False, id="cb_mom_hybrid", tooltip="Hybrid Mode — Pre-buys on strong leads, otherwise waits for STN.")
                        yield Checkbox(label="ADV", value=False, id="cb_mom_adv", tooltip="Advanced/ATR — Uses dynamic ATR tiers to shift thresholds and behavior.")
                with Horizontal(id="modal_mom_adv_btn"):
                    yield Button("CONFIGURE ADV", id="btn_mom_adv", variant="warning")
            with Horizontal(id="modal_footer"):
                yield Button("CLOSE/SAVE", id="close_btn", variant="primary")

    def on_mount(self):
        # Center the modal on screen
        self.styles.align = ("center", "middle")
        
        container = self.query_one("#modal_container")
        container.styles.background = "#222222"
        container.styles.border = ("thick", "cyan")
        container.styles.padding = (1, 2)
        container.styles.width = 62
        container.styles.height = "auto"
        container.styles.max_height = "90vh"
        container.styles.align = ("center", "middle")
        
        self.query_one("#modal_title").styles.margin = (0, 0, 1, 0)
        self.query_one("#modal_title").styles.text_align = "center"
        self.query_one("#modal_title").styles.width = "100%"
        
        self.query_one("#modal_body").styles.margin = (0, 0, 2, 0)
        self.query_one("#modal_body").styles.text_align = "center"
        self.query_one("#modal_body").styles.width = "100%"

        row_w = self.query_one("#modal_algo_weight")
        row_w.styles.height = 3
        row_w.styles.align = ("center", "middle")
        row_w.styles.margin = (0, 0, 0, 0)
        row_w.styles.border = ("ascii", "#333333")
        self.query_one("#inp_algo_weight").styles.width = 10
        
        if self.main_app:
            w = self.main_app.scanner_weights.get(self.algo_id, 1.0)
            self.query_one("#inp_algo_weight").value = str(w)

        if self.algo_id == "MOS":
            for row_id in ["#modal_mos_bet", "#modal_mos_pt1", "#modal_mos_pt2", "#modal_mos_pt3"]:
                row = self.query_one(row_id)
                row.styles.height = 3
                row.styles.align = ("center", "middle")
                row.styles.margin = (0, 0, 1, 0)
                row.styles.border = ("ascii", "#333333")
            
            for inp_id in ["#inp_mos_bet", "#inp_mos_t1", "#inp_mos_d1", "#inp_mos_t2", "#inp_mos_d2", "#inp_mos_t3", "#inp_mos_d3"]:
                self.query_one(inp_id).styles.width = 10
            
            if self.main_app and "Moshe" in self.main_app.scanners:
                moshe = self.main_app.scanners["Moshe"]
                if hasattr(moshe, "bet_size"): self.query_one("#inp_mos_bet").value = str(moshe.bet_size)
                if hasattr(moshe, "t1"): self.query_one("#inp_mos_t1").value = str(moshe.t1)
                if hasattr(moshe, "d1"): self.query_one("#inp_mos_d1").value = str(moshe.d1)
                if hasattr(moshe, "t2"): self.query_one("#inp_mos_t2").value = str(moshe.t2)
                if hasattr(moshe, "d2"): self.query_one("#inp_mos_d2").value = str(moshe.d2)
                if hasattr(moshe, "t3"): self.query_one("#inp_mos_t3").value = str(moshe.t3)
                if hasattr(moshe, "d3"): self.query_one("#inp_mos_d3").value = str(moshe.d3)
        elif self.algo_id == "MOM":
            for row_id in ["#modal_mom_row1", "#modal_mom_threshold"]:
                row = self.query_one(row_id)
                row.styles.height = "auto"
                row.styles.align = ("center", "middle")
                row.styles.margin = (0, 0, 1, 0)

            # Buy Mode 2x2 Grid Layout (v5.9.2)
            grid = self.query_one("#modal_mom_buymode_grid")
            grid.styles.height = "auto"
            grid.styles.align = ("center", "middle")
            grid.styles.margin = (1, 0, 0, 0)
            grid.styles.padding = (0, 0)
            
            self.query_one("#lbl_mom_buymode").styles.text_align = "center"
            self.query_one("#lbl_mom_buymode").styles.width = "100%"
            self.query_one("#lbl_mom_buymode").styles.margin = (0, 0, 0, 0)

            for row in self.query(".buy_mode_row"):
                row.styles.height = "auto"
                row.styles.align = ("center", "middle")
                row.styles.width = "100%"
                row.styles.margin = (0, 0)

            for cbid in ["#cb_mom_std", "#cb_mom_pre", "#cb_mom_hybrid", "#cb_mom_adv"]:
                cb = self.query_one(cbid)
                cb.styles.width = 15
                cb.styles.margin = (0, 1)

            abt = self.query_one("#modal_mom_adv_btn")
            abt.styles.align = ("center", "middle")
            abt.styles.width = "100%"
            abt.styles.margin = (1, 0, 0, 0)

            self.query_one("#inp_mom_mode").styles.width = 10
            self.query_one("#inp_mom_duration").styles.width = 6
            self.query_one("#lbl_mom_duration").styles.margin = (1, 0, 0, 1)
            self.query_one("#inp_mom_threshold").styles.width = 8

            if self.main_app and "Momentum" in self.main_app.scanners:
                mom = self.main_app.scanners["Momentum"]
                self.query_one("#inp_mom_mode").value = str(getattr(mom, "mode", "TIME"))
                self.query_one("#inp_mom_threshold").value = str(int(getattr(mom, "threshold", 0.6) * 100))
                self.query_one("#inp_mom_duration").value = str(getattr(mom, "duration", 10))

            # Set Buy Mode checkboxes from app state
            if self.main_app:
                m = self.main_app.mom_buy_mode
                try: self.query_one("#cb_mom_std").value = (m == "STD")
                except: pass
                try: self.query_one("#cb_mom_pre").value = (m == "PRE")
                except: pass
                try: self.query_one("#cb_mom_hybrid").value = (m == "HYBRID")
                except: pass
                try: self.query_one("#cb_mom_adv").value = (m == "ADV")
                except: pass
                try: self.query_one("#btn_mom_adv").disabled = (m != "ADV")
                except: pass

        footer = self.query_one("#modal_footer")
        footer.styles.height = "auto"
        footer.styles.align = ("center", "middle")
        footer.styles.width = "100%"

    @on(Button.Pressed, "#close_btn")
    def close_modal(self):
        if self.main_app:
            try:
                w = float(self.query_one("#inp_algo_weight").value)
                self.main_app.scanner_weights[self.algo_id] = w
                self.main_app.save_settings()
            except: pass

        if self.algo_id == "MOS" and self.main_app and "Moshe" in self.main_app.scanners:
            moshe = self.main_app.scanners["Moshe"]
            
            try: moshe.bet_size = float(self.query_one("#inp_mos_bet").value)
            except: getattr(moshe, "bet_size", None)
            
            try: moshe.t1 = int(self.query_one("#inp_mos_t1").value)
            except: getattr(moshe, "t1", None)
            try: moshe.d1 = float(self.query_one("#inp_mos_d1").value)
            except: getattr(moshe, "d1", None)
            
            try: moshe.t2 = int(self.query_one("#inp_mos_t2").value)
            except: getattr(moshe, "t2", None)
            try: moshe.d2 = float(self.query_one("#inp_mos_d2").value)
            except: getattr(moshe, "d2", None)
            
            try: moshe.t3 = int(self.query_one("#inp_mos_t3").value)
            except: getattr(moshe, "t3", None)
            try: moshe.d3 = float(self.query_one("#inp_mos_d3").value)
            except: getattr(moshe, "d3", None)
            
        elif self.algo_id == "MOM" and self.main_app and "Momentum" in self.main_app.scanners:
            mom = self.main_app.scanners["Momentum"]
            m = self.query_one("#inp_mom_mode").value.strip().upper()
            if m in ["TIME", "PRICE", "DURATION"]:
                mom.mode = m
            try:
                t = int(self.query_one("#inp_mom_threshold").value)
                if 51 <= t <= 70:
                    mom.threshold = t / 100.0
                    mom.base_threshold = t / 100.0
            except: pass
            try:
                d = int(self.query_one("#inp_mom_duration").value)
                if d > 0:
                    mom.duration = d
            except: pass
            # Save Buy Mode
            try:
                if self.query_one("#cb_mom_pre").value:
                    self.main_app.mom_buy_mode = "PRE"
                elif self.query_one("#cb_mom_hybrid").value:
                    self.main_app.mom_buy_mode = "HYBRID"
                elif self.query_one("#cb_mom_adv").value:
                    self.main_app.mom_buy_mode = "ADV"
                else:
                    self.main_app.mom_buy_mode = "STD"
                self.main_app.save_settings()
            except: pass
            
        self.dismiss()

    @on(Checkbox.Changed, "#cb_mom_std")
    def _mom_std_toggled(self, event: Checkbox.Changed):
        if event.value:
            try:
                self.query_one("#cb_mom_pre").value = False
                self.query_one("#cb_mom_hybrid").value = False
                self.query_one("#cb_mom_adv").value = False
                self.query_one("#btn_mom_adv").disabled = True
            except: pass

    @on(Checkbox.Changed, "#cb_mom_pre")
    def _mom_pre_toggled(self, event: Checkbox.Changed):
        if event.value:
            try:
                self.query_one("#cb_mom_std").value = False
                self.query_one("#cb_mom_hybrid").value = False
                self.query_one("#cb_mom_adv").value = False
                self.query_one("#btn_mom_adv").disabled = True
            except: pass
        else:
            # Prevent all being unchecked — revert to Standard
            try:
                if (not self.query_one("#cb_mom_std").value and 
                    not self.query_one("#cb_mom_hybrid").value and
                    not self.query_one("#cb_mom_adv").value):
                    self.query_one("#cb_mom_std").value = True
            except: pass

    @on(Checkbox.Changed, "#cb_mom_hybrid")
    def _mom_hybrid_toggled(self, event: Checkbox.Changed):
        if event.value:
            try:
                self.query_one("#cb_mom_std").value = False
                self.query_one("#cb_mom_pre").value = False
                self.query_one("#cb_mom_adv").value = False
                self.query_one("#btn_mom_adv").disabled = True
            except: pass
        else:
            # Prevent all being unchecked
            try:
                if (not self.query_one("#cb_mom_std").value and 
                    not self.query_one("#cb_mom_pre").value and
                    not self.query_one("#cb_mom_adv").value):
                    self.query_one("#cb_mom_std").value = True
            except: pass

    @on(Checkbox.Changed, "#cb_mom_adv")
    def _mom_adv_toggled(self, event: Checkbox.Changed):
        if event.value:
            try:
                self.query_one("#cb_mom_std").value = False
                self.query_one("#cb_mom_pre").value = False
                self.query_one("#cb_mom_hybrid").value = False
                self.query_one("#btn_mom_adv").disabled = False
            except: pass
        else:
            # Prevent all being unchecked
            try:
                if (not self.query_one("#cb_mom_std").value and 
                    not self.query_one("#cb_mom_pre").value and
                    not self.query_one("#cb_mom_hybrid").value):
                    self.query_one("#cb_mom_std").value = True
                self.query_one("#btn_mom_adv").disabled = True
            except: pass

    @on(Button.Pressed, "#btn_mom_adv")
    def _on_mom_adv_click(self):
        if self.main_app:
            self.main_app.push_screen(MOMExpertModal(self.main_app))


class MOMExpertModal(ModalScreen):
    """Advanced Momentum settings based on Volatility/ATR."""
    BINDINGS = [("escape", "dismiss", "Dismiss")]
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.s = main_app.mom_adv_settings

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield Static("[bold #ffaa00]MOM - Advanced Volatility & ATR Logic[/]", id="modal_title")
            
            with Vertical(id="modal_expert_payload"):
                with Vertical(classes="exp_section"):
                    yield Label("1. ATR Gateways (Tiers)", classes="exp_sec_title")
                    with Horizontal(classes="exp_row"):
                        yield Label("Stable Boundary (¢):")
                        yield Input(placeholder="20", value=str(self.s["atr_low"]), id="exp_atr_low")
                        yield Label("Chaos Boundary (¢):")
                        yield Input(placeholder="40", value=str(self.s["atr_high"]), id="exp_atr_high")
                
                with Vertical(classes="exp_section"):
                    yield Label("2. Dynamic Threshold Offsets", classes="exp_sec_title")
                    with Horizontal(classes="exp_row"):
                        yield Label("Stable Side Offset (¢):")
                        yield Input(placeholder="-5", value=str(self.s["stable_offset"]), id="exp_off_stable")
                        yield Label("Chaos Side Offset (¢):")
                        yield Input(placeholder="10", value=str(self.s["chaos_offset"]), id="exp_off_chaos")
                
                with Vertical(classes="exp_section"):
                    yield Label("3. Auto-Mode Overrides", classes="exp_sec_title")
                    with Horizontal(classes="exp_row"):
                        yield Checkbox(label="STN on Chaos (Safe)", value=self.s["auto_stn_chaos"], id="exp_over_stn")
                        yield Checkbox(label="PBN on Stable (Aggro)", value=self.s["auto_pbn_stable"], id="exp_over_pbn")
                
                with Vertical(classes="exp_section"):
                    yield Label("4. Whale Shield Emergency", classes="exp_sec_title")
                    with Horizontal(classes="exp_row"):
                        yield Label("Zone (s):")
                        yield Input(placeholder="45", value=str(self.s["shield_time"]), id="exp_wh_time")
                        yield Label("Reach (¢):")
                        yield Input(placeholder="5", value=str(self.s["shield_reach"]), id="exp_wh_reach")
                
                yield Static("", id="exp_preview")
                yield Button("SAVE & CLOSE", id="btn_exp_save", variant="primary")

    def on_mount(self):
        self.styles.align = ("center", "middle")
        c = self.query_one("#modal_container")
        c.styles.background = "#1a1a1a"
        c.styles.border = ("thick", "#ffaa00")
        c.styles.padding = (0, 2)
        c.styles.width = 65
        c.styles.height = "auto"
        
        self.query_one("#modal_title").styles.text_align = "center"
        self.query_one("#modal_title").styles.margin = (0, 0, 1, 0)
        self.query_one("#modal_title").styles.color = "#ffaa00"
        
        payload = self.query_one("#modal_expert_payload")
        payload.styles.align = ("center", "middle")
        payload.styles.height = "auto"

        for sec in self.query(".exp_section"):
            sec.styles.border = ("ascii", "#333333")
            sec.styles.padding = (0, 1)
            sec.styles.margin = (0, 0, 1, 0)
            sec.styles.height = "auto"
            sec.styles.width = "100%"

        for title in self.query(".exp_sec_title"):
            title.styles.color = "#888888"
            title.styles.bold = True
            title.styles.width = "100%"
            title.styles.text_align = "left"

        for row in self.query(".exp_row"):
            row.styles.height = "auto"
            row.styles.align = ("center", "middle")
            row.styles.width = "100%"

        for inp in self.query(Input):
            inp.styles.width = 6
            inp.styles.margin = (0, 1, 0, 0)
        
        for cb in self.query(Checkbox):
            cb.styles.width = 25
            cb.styles.margin = (0, 0)
        
        prev = self.query_one("#exp_preview")
        prev.styles.text_align = "center"
        prev.styles.color = "#aaaaaa"
        prev.styles.height = 3
        prev.styles.margin = (0, 0)
        
        save_btn = self.query_one("#btn_exp_save")
        save_btn.styles.margin = (1, 0, 0, 0)
        save_btn.styles.width = 25
        save_btn.styles.align = ("center", "middle")
        
        self.set_interval(1.0, self._update_preview)

    def _update_preview(self):
        if not self.main_app: return
        atr = getattr(self.main_app.market_data_manager, "atr_5m", 0)
        mom = self.main_app.scanners.get("Momentum")
        base_t = int(getattr(mom, "threshold", 0.6) * 100) if mom else 60
        
        # Logic Tier
        tier = 2 # Neutral
        adj = 0
        if atr <= self.s["atr_low"]:
            tier = 1; adj = self.s["stable_offset"]
        elif atr >= self.s["atr_high"]:
            tier = 3; adj = self.s["chaos_offset"]
        
        final_t = base_t + adj
        status = "Stable" if tier == 1 else ("Chaos" if tier == 3 else "Neutral")
        color = "green" if tier == 1 else ("red" if tier == 3 else "cyan")
        
        preview = (
            f"Curr ATR: {float(atr):.1f} | Tier: [bold {color}]{status}[/] | "
            f"Base: {base_t}¢ | Offset: {adj:+}¢ | [bold white]Target: {final_t}¢[/]"
        )
        self.query_one("#exp_preview").update(preview)

    @on(Button.Pressed, "#btn_exp_save")
    def save_and_close(self):
        try:
            self.s["atr_low"] = int(self.query_one("#exp_atr_low").value)
            self.s["atr_high"] = int(self.query_one("#exp_atr_high").value)
            self.s["stable_offset"] = int(self.query_one("#exp_off_stable").value)
            self.s["chaos_offset"] = int(self.query_one("#exp_off_chaos").value)
            self.s["auto_stn_chaos"] = self.query_one("#exp_over_stn").value
            self.s["auto_pbn_stable"] = self.query_one("#exp_over_pbn").value
            self.s["shield_time"] = int(self.query_one("#exp_wh_time").value)
            self.s["shield_reach"] = int(self.query_one("#exp_wh_reach").value)
            self.main_app.save_settings()
        except: pass
        self.dismiss()


class ResearchLogger:
    """Handles BullFlag research logging with performance analytics."""
    
    def __init__(self, main_app):
        self.main_app = main_app
        self.session_stats = {}
        self.current_settings = {}
        
    def log_trade(self, settings, entry_price, exit_price, side, result, window_id, rsi_1m, btc_velocity, atr_5m):
        """Log a BullFlag trade with current settings and outcome."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate profit/loss
        if side == "UP":
            profit = (exit_price - entry_price) if result == "WIN" else (entry_price - exit_price)
        else:
            profit = (entry_price - exit_price) if result == "WIN" else (exit_price - entry_price)
        
        # Log to research file
        log_entry = [
            timestamp,
            settings["max_price"],
            "ON" if settings.get("volume_confirm") else "OFF",
            settings["entry_timing"],
            "ON" if settings.get("pullback") else "OFF",
            f"{settings['tolerance_pct']:.2f}",
            f"{settings['atr_multiplier']:.1f}",
            f"{entry_price*100:.1f}",
            f"{exit_price*100:.1f}",
            side,
            result,
            f"{profit:+.2f}" if profit != 0 else "0.00",
            window_id,
            f"{rsi_1m:.1f}",
            f"{btc_velocity:.0f}",
            f"{atr_5m:.1f}"
        ]
        
        # Update session statistics
        self.session_stats[timestamp] = log_entry
        
        # Write to research log file
        if settings.get("research_enabled"):
            session_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = f"lg/bullflag_research_{session_time}.csv"
            
            # Write header if file doesn't exist
            if not os.path.exists(log_file):
                with open(log_file, 'w', newline='') as f:
                    f.write("Timestamp,Max_Price,Volume_Filter,Entry_Timing,Pullback_Detection,Tolerance,ATR_Multiplier,Entry_Price,Exit_Price,Side,Result,Profit_Loss,Window_ID,RSI_1m,BTC_Velocity,ATR_5m\n")
            
            # Append trade data
            with open(log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(log_entry)
            
            self.main_app.log_msg(f"📊 BullFlag research logged: {log_file}")
    
    def get_session_stats(self):
        """Calculate session performance statistics."""
        if not self.session_stats:
            return "No data"
        
        trades = list(self.session_stats.values())
        if not trades:
            return "No trades"
        
        wins = sum(1 for trade in trades if trade[11] == "WIN")
        losses = sum(1 for trade in trades if trade[11] == "LOSS")
        total_profit = sum(float(trade[12]) for trade in trades)
        
        return f"Trades: {len(trades)}, Wins: {wins}, Losses: {losses}, Win Rate: {wins/len(trades)*100:.1f}%, Total Profit: ${total_profit:+.2f}"


class BankrollExhaustedModal(ModalScreen):
    """Full-screen alert shown when the bankroll can no longer cover the minimum bet."""

    def __init__(self, bankroll: float, min_bet: float, mode: str):
        super().__init__()
        self.bankroll = bankroll
        self.min_bet  = min_bet
        self.mode     = mode

    def compose(self) -> ComposeResult:
        with Vertical(id="frozen_container"):
            yield Label("🔴  BOT FROZEN", id="frozen_title")
            yield Label(
                f"Mode: {self.mode}  |  Bankroll: ${self.bankroll:.2f}  |  Min Bet: ${self.min_bet:.2f}",
                id="frozen_details"
            )
            yield Label(
                "The bankroll has dropped below minimum bet size.\n"
                "All market scanning and trade execution has been stopped.\n"
                "A final CSV snapshot and console log entry have been written.\n\n"
                "Please top up your bankroll or reduce Bet $ amount\n"
                "before restarting bot.",
                id="frozen_body"
            )
            yield Button("OK  —  I understand", id="btn_frozen_ok", variant="error")

    def on_mount(self):
        c = self.query_one("#frozen_container")
        c.styles.align    = ("center", "middle")
        c.styles.width    = "80%"
        c.styles.height   = "auto"
        c.styles.background = "#1a0000"
        c.styles.border   = ("heavy", "red")
        c.styles.padding  = (2, 4)

        t = self.query_one("#frozen_title")
        t.styles.text_align  = "center"
        t.styles.color       = "red"
        t.styles.text_style  = "bold"
        t.styles.margin      = (0, 0, 1, 0)
        t.styles.width       = "100%"

        d = self.query_one("#frozen_details")
        d.styles.text_align  = "center"
        d.styles.color       = "#ff6666"
        d.styles.margin      = (0, 0, 2, 0)
        d.styles.width       = "100%"

        b = self.query_one("#frozen_body")
        b.styles.text_align  = "center"
        b.styles.color       = "white"
        b.styles.margin      = (0, 0, 2, 0)
        b.styles.width       = "100%"

        btn = self.query_one("#btn_frozen_ok")
        btn.styles.width = "50%"
        btn.styles.align = ("center", "middle")

        self.styles.align = ("center", "middle")
        self.styles.background = "rgba(0,0,0,0.85)"

    @on(Button.Pressed, "#btn_frozen_ok")
    def dismiss_modal(self):
        self.dismiss()


class BullFlagSettingsModal(ModalScreen):
    """Quick settings modal for BullFlag algorithm improvements."""
    BINDINGS = [("escape", "dismiss", "Dismiss")]
    
    def __init__(self, main_app=None):
        super().__init__()
        self.main_app = main_app
        self.main_app = main_app
        
    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield Static("[bold yellow]⚡ BULLFLAG SETTINGS[/]", id="modal_title")
            
            with Horizontal(id="settings_grid"):
                # Quick improvement options
                yield Static("🎯 Max Price Threshold:", id="label_max_price")
                yield Input(placeholder="80", id="inp_max_price", value="80")
                
                yield Static("📊 Volume Filter:", id="label_volume")
                yield Checkbox("Enable volume confirmation", id="cb_volume_confirm", value=False)
                
                yield Static("⚡ Entry Timing:", id="label_entry_timing")
                yield Radio("Aggressive", id="rb_aggressive", value=True, name="entry_timing")
                yield Radio("Conservative", id="rb_conservative", value=False, name="entry_timing")
                
                yield Static("🔧 Pullback Detection:", id="label_pullback")
                yield Checkbox("Enable pullback detection", id="cb_pullback", value=False)
                
                yield Static("🎯 Dynamic Tolerance:", id="label_tolerance")
                yield Slider(0.05, 0.2, 0.15, 0.3, id="slider_tolerance", value="0.1")
                
                yield Static("📈 ATR Multiplier:", id="label_atr_mult")
                yield Slider(1.0, 1.5, 2.0, 3.0, id="slider_atr_mult", value="1.5")
                
                yield Static("📊 Research Log:", id="label_research_log")
                yield Checkbox("Enable research logging", id="cb_research_log", value=False)
                
            with Horizontal(id="button_row"):
                yield Button("APPLY (A)", id="btn_apply", variant="primary")
                yield Button("RESET (R)", id="btn_reset", variant="default")
                yield Button("DISMISS", id="btn_dismiss")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_apply":
            self._apply_settings()
        elif event.button.id == "btn_reset":
            self._reset_settings()
        elif event.button.id == "btn_dismiss":
            self.dismiss()
    
    def _apply_settings(self):
        """Apply BullFlag improvements based on user selections."""
        max_price = float(self.query_one("#inp_max_price").value)
        volume_confirm = self.query_one("#cb_volume_confirm").value
        entry_timing = self.query_one("#rb_aggressive").value
        pullback = self.query_one("#cb_pullback").value
        tolerance = float(self.query_one("#slider_tolerance").value)
        atr_mult = float(self.query_one("#slider_atr_mult").value)
        research_enabled = self.query_one("#cb_research_log").value
        
        # Update BullFlag scanner with new settings
        if hasattr(self.main_app, 'scanners') and 'BullFlag' in self.main_app.scanners:
            bullflag_scanner = self.main_app.scanners['BullFlag']
            bullflag_scanner.max_price = max_price
            bullflag_scanner.volume_confirm = volume_confirm
            bullflag_scanner.entry_timing = "AGGRESSIVE" if entry_timing else "CONSERVATIVE"
            bullflag_scanner.pullback = pullback
            bullflag_scanner.tolerance_pct = tolerance
            bullflag_scanner.atr_multiplier = atr_mult
            bullflag_scanner.research_enabled = research_enabled
            
            # Initialize research logger if enabled
            if research_enabled and not hasattr(bullflag_scanner, 'research_logger'):
                bullflag_scanner.research_logger = ResearchLogger(self.main_app)
            
            self.main_app.log_msg("⚡ BullFlag settings applied: Max=$.2f, Volume=%s, Entry=%s, Pullback=%s, Tolerance=%.2f, ATR=%.1fx, Research=%s" % (
                max_price, "ON" if volume_confirm else "OFF",
                entry_timing, "ON" if pullback else "OFF", 
                tolerance, atr_mult,
                "ON" if research_enabled else "OFF"))
    
    def _reset_settings(self):
        """Reset BullFlag settings to defaults."""
        self.query_one("#inp_max_price").value = "80"
        self.query_one("#cb_volume_confirm").value = False
        self.query_one("#rb_aggressive").value = True
        self.query_one("#cb_pullback").value = False
        self.query_one("#slider_tolerance").value = "0.1"
        self.query_one("#slider_atr_mult").value = "1.5"
        
        self.main_app.log_msg("🔄 BullFlag settings reset to defaults")
    """Full-screen alert shown when the bankroll can no longer cover the minimum bet."""

    def __init__(self, bankroll: float, min_bet: float, mode: str):
        super().__init__()
        self.bankroll = bankroll
        self.min_bet  = min_bet
        self.mode     = mode

    def compose(self) -> ComposeResult:
        with Vertical(id="frozen_container"):
            yield Label("🔴  BOT FROZEN", id="frozen_title")
            yield Label(
                f"Mode: {self.mode}  |  Bankroll: ${self.bankroll:.2f}  |  Min Bet: ${self.min_bet:.2f}",
                id="frozen_details"
            )
            yield Label(
                "The bankroll has dropped below the minimum bet size.\n"
                "All market scanning and trade execution has been stopped.\n"
                "A final CSV snapshot and console log entry have been written.\n\n"
                "Please top up your bankroll or reduce the Bet $ amount\n"
                "before restarting the bot.",
                id="frozen_body"
            )
            yield Button("OK  —  I understand", id="btn_frozen_ok", variant="error")

    def on_mount(self):
        c = self.query_one("#frozen_container")
        c.styles.align    = ("center", "middle")
        c.styles.width    = "80%"
        c.styles.height   = "auto"
        c.styles.background = "#1a0000"
        c.styles.border   = ("heavy", "red")
        c.styles.padding  = (2, 4)

        t = self.query_one("#frozen_title")
        t.styles.text_align  = "center"
        t.styles.color       = "red"
        t.styles.text_style  = "bold"
        t.styles.margin      = (0, 0, 1, 0)
        t.styles.width       = "100%"

        d = self.query_one("#frozen_details")
        d.styles.text_align  = "center"
        d.styles.color       = "#ff6666"
        d.styles.margin      = (0, 0, 2, 0)
        d.styles.width       = "100%"

        b = self.query_one("#frozen_body")
        b.styles.text_align  = "center"
        b.styles.color       = "white"
        b.styles.margin      = (0, 0, 2, 0)
        b.styles.width       = "100%"

        btn = self.query_one("#btn_frozen_ok")
        btn.styles.width = "50%"
        btn.styles.align = ("center", "middle")

        self.styles.align = ("center", "middle")
        self.styles.background = "rgba(0,0,0,0.85)"

    @on(Button.Pressed, "#btn_frozen_ok")
    def dismiss_modal(self):
        self.dismiss()
