import time
import asyncio
import json
import os
import csv
from datetime import datetime, timezone
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Button, RichLog, Label, Checkbox, RadioButton, RadioSet, Static
from textual import work, on, events

from .config import TradingConfig, POLYGON_RPC_LIST, CHAINLINK_BTC_FEED, CHAINLINK_ABI
from .market import MarketDataManager, calculate_rsi, calculate_bb, calculate_atr
from .risk import RiskManager, AlgorithmPortfolio
from .broker import TradeExecutor
from .scanners import ALGO_INFO
from .scanners import (
    NPatternScanner, FakeoutScanner, MomentumScanner, RsiScanner, TrapCandleScanner,
    MidGameScanner, LateReversalScanner, StaircaseBreakoutScanner, PostPumpScanner,
    StepClimberScanner, SlingshotScanner, MinOneScanner, LiquidityVacuumScanner,
    CobraScanner, MesaCollapseScanner, MeanReversionScanner, GrindSnapScanner,
    VolCheckScanner, MosheSpecializedScanner, ZScoreBreakoutScanner
)

from .ui_modals import (
    GlobalSettingsModal, AlgoInfoModal, BullFlagSettingsModal,
    BankrollExhaustedModal, MOMExpertModal, ResearchLogger
)
from .trade_engine import TradeEngineMixin


class SniperApp(TradeEngineMixin, App):
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
            if code in ALGO_INFO:
                desc = ALGO_INFO[code]["desc"]
                self.push_screen(AlgoInfoModal(code, ALGO_INFO[code]["name"], desc, self))
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
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(script_dir, "lg")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        base_log_name = os.path.basename(self.sim_broker.log_file).replace(".csv", "_console.txt")
        self.console_log_file = os.path.join(log_dir, base_log_name)
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
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.settings_file = os.path.join(script_dir, "v5_settings.json")
        
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
        # Create a time-signatured log file for this session in lg/ subdirectory of current script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(script_dir, "lg")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        session_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.mom_adv_log_file = os.path.join(log_dir, f"momentum_adv_{session_time}.csv")
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

    # --- Trade engine methods are inherited from TradeEngineMixin ---
    # fetch_market_loop, _check_tpsl, _run_last_second_exit, update_timer,
    # _check_bankroll_exhaustion, trigger_settlement, _add_risk_revenue,
    # trigger_buy, trigger_sell_all

    async def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "btn_settings":
            self.push_screen(GlobalSettingsModal(self))
        elif "btn_buy_" in bid: 
            await self.trigger_buy("UP" if "_up" in bid else "DOWN")
        elif "btn_sell_" in bid:
            await self.trigger_sell_all("UP" if "_up" in bid else "DOWN")
