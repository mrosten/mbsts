import time
import asyncio
from datetime import datetime, timezone
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Button, RichLog, Label, Checkbox
from textual import work, on, events

from .config import TradingConfig, POLYGON_RPC_LIST, CHAINLINK_BTC_FEED, CHAINLINK_ABI
from .market import MarketDataManager, calculate_rsi, calculate_bb
from .risk import RiskManager, AlgorithmPortfolio
from .broker import TradeExecutor
from .scanners import (
    NPatternScanner, FakeoutScanner, TailWagScanner, RsiScanner, TrapCandleScanner,
    MidGameScanner, LateReversalScanner, StaircaseBreakoutScanner, PostPumpScanner,
    StepClimberScanner, SlingshotScanner, MinOneScanner, LiquidityVacuumScanner,
    CobraScanner, MesaCollapseScanner, MeanReversionScanner, GrindSnapScanner,
    VolCheckScanner, MosheSpecializedScanner, ZScoreBreakoutScanner
)

class SniperApp(App):
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
    .algo_item { width: 1fr; height: 1; layout: horizontal; align: center middle; }
    .algo_item Checkbox { width: auto; margin: 0; padding: 0; border: none; }
    .algo_item Label { width: auto; margin: 0 0 0 1; color: #666666; }
    .algo_item Label:hover { color: cyan; text-style: underline; }
    
    .live_row { align: center middle; height: 1; background: #220000; padding: 0 1; border-top: solid #440000; }
    .live_row Checkbox { width: auto; margin: 0 1; background: #220000; color: #aaaaaa; border: none; }
    
    #cb_live { color: #ff0000; text-style: bold; }
    RichLog { height: 1fr; min-height: 5; background: #111111; color: #eeeeee; }
    """

    @on(Checkbox.Changed)
    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        cb_id = event.checkbox.id
        if cb_id and cb_id.startswith("cb_"):
            code = cb_id[3:]
            try:
                lbl = self.query_one(f"#lbl_{code}")
                if event.value:
                    lbl.styles.color = "#00ff00"
                    lbl.styles.text_style = "bold"
                else:
                    lbl.styles.color = "#666666"
                    lbl.styles.text_style = "none"
            except: pass

    @on(events.Click, "Label")
    def on_label_click(self, event: events.Click) -> None:
        lbl_id = event.control.id
        if lbl_id and lbl_id.startswith("lbl_"):
            code = lbl_id[4:].upper()
            info = ALGO_INFO.get(code)
            if info:
                self.push_screen(AlgoInfoModal(code, info['name'], info['desc']))
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
        
        self.scanners = {
            "NPattern": NPatternScanner(),
            "Fakeout": FakeoutScanner(),
            "TailWag": TailWagScanner(),
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
        self.last_second_exit_triggered = False 
        self.app_start_time = time.time()
        self.time_rem_str = "00:00"

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Label(f"SIM | Bal: ${self.sim_broker.balance:.2f}", id="header_stats"),
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
                Label("Trend 4H: NEUTRAL", id="p_trend", classes="price_sub"),
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
            Input(placeholder="TP %", value="100", id="inp_tp"),
            Label("SL %:", classes="lbl_sm"),
            Input(placeholder="SL %", value="100", id="inp_sl"),
            classes="input_group"
        )
        yield Container(
            Label("Sim Bal:", classes="lbl_sm"),
            Input(placeholder="Sim Bal", value=f"{self.sim_broker.balance:.2f}", id="inp_sim_bal"),
            Label("Min Diff:", classes="lbl_sm"),
            Input(placeholder="Min Diff $", value="0", id="inp_min_diff"),
            Label("Min Price:", classes="lbl_sm"),
            Input(placeholder="Min Price", value="0.01", id="inp_min_price"),
            Label("Max Price:", classes="lbl_sm"),
            Input(placeholder="Max Price", value="0.99", id="inp_max_price"),
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
            Horizontal(Checkbox(value=True, id="cb_cob"), Label("COB", id="lbl_cob"), classes="algo_item"),
            Horizontal(Checkbox(value=True, id="cb_fak"), Label("FAK", id="lbl_fak"), classes="algo_item"),
            Horizontal(Checkbox(value=True, id="cb_gri"), Label("GRI", id="lbl_gri"), classes="algo_item"),
            Horizontal(Checkbox(value=True, id="cb_lat"), Label("LAT", id="lbl_lat"), classes="algo_item"),
            Horizontal(Checkbox(value=True, id="cb_liq"), Label("LIQ", id="lbl_liq"), classes="algo_item"),
            Horizontal(Checkbox(value=True, id="cb_mea"), Label("MEA", id="lbl_mea"), classes="algo_item"),
            classes="algo_row"
        )
        yield Horizontal(
            Horizontal(Checkbox(value=True, id="cb_mes"), Label("MES", id="lbl_mes"), classes="algo_item"),
            Horizontal(Checkbox(value=True, id="cb_mid"), Label("MID", id="lbl_mid"), classes="algo_item"),
            Horizontal(Checkbox(value=True, id="cb_min"), Label("MIN", id="lbl_min"), classes="algo_item"),
            Horizontal(Checkbox(value=True, id="cb_mos"), Label("MOS", id="lbl_mos"), classes="algo_item"),
            Horizontal(Checkbox(value=True, id="cb_npa"), Label("NPA", id="lbl_npa"), classes="algo_item"),
            Horizontal(Checkbox(value=True, id="cb_pos"), Label("POS", id="lbl_pos"), classes="algo_item"),
            classes="algo_row"
        )
        yield Horizontal(
            Horizontal(Checkbox(value=True, id="cb_rsi"), Label("RSI", id="lbl_rsi"), classes="algo_item"),
            Horizontal(Checkbox(value=True, id="cb_sli"), Label("SLI", id="lbl_sli"), classes="algo_item"),
            Horizontal(Checkbox(value=True, id="cb_sta"), Label("STA", id="lbl_sta"), classes="algo_item"),
            Horizontal(Checkbox(value=True, id="cb_ste"), Label("STE", id="lbl_ste"), classes="algo_item"),
            Horizontal(Checkbox(value=True, id="cb_tai"), Label("TAI", id="lbl_tai"), classes="algo_item"),
            Horizontal(Checkbox(value=True, id="cb_tra"), Label("TRA", id="lbl_tra"), classes="algo_item"),
            classes="algo_row"
        )
        yield Horizontal(
            Horizontal(Checkbox(value=True, id="cb_vol"), Label("VOL", id="lbl_vol"), classes="algo_item"),
            Horizontal(Checkbox(value=False, id="cb_zsc"), Label("ZSC", id="lbl_zsc"), classes="algo_item"),
            classes="algo_row"
        )
        yield Horizontal(
            Checkbox("TP/SL", value=True, id="cb_tp_active"),
            Checkbox("Strong Only", value=False, id="cb_strong"),
            Checkbox("1 Trade Max", value=False, id="cb_one_trade"), 
            Checkbox("Whale Protect", value=True, id="cb_whale"),
            Checkbox("LIVE MODE", value=False, id="cb_live"),
            id="live_row",
            classes="live_row"
        )
        yield RichLog(id="log_window", highlight=True, markup=True)

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
        self.set_interval(15, self.dump_state_log)
        if self.start_live_mode:
            self.query_one("#cb_live").value = True 

    @on(Checkbox.Changed, "#cb_live")
    def on_live_toggle(self, event: Checkbox.Changed):
        if event.value: 
            self.log_msg("[bold red]LIVE MODE ENABLED! All Algos deselected for safety.[/]")
            all_cbs = ["#cb_cob", "#cb_fak", "#cb_gri", "#cb_lat", "#cb_liq", "#cb_mea", "#cb_mes", "#cb_mid", "#cb_min", "#cb_mos", "#cb_npa", "#cb_pos", "#cb_rsi", "#cb_sli", "#cb_sta", "#cb_ste", "#cb_tai", "#cb_tra", "#cb_vol", "#cb_zsc"]
            for cid in all_cbs: self.query_one(cid).value = False
            lb = self.live_broker.balance
            if lb > 0:
                self.query_one("#inp_risk_alloc").value = f"{lb/TradingConfig.LIVE_RISK_DIVISOR:.2f}"
                self.risk_manager.set_bankroll(lb, is_live=True)
                self.risk_initialized = True
        else:
            sb = self.sim_broker.balance
            self.query_one("#inp_risk_alloc").value = f"{sb:.2f}"
            self.risk_manager.set_bankroll(sb, is_live=False)
            self.risk_initialized = True

    def log_msg(self, msg):
        self.query_one(RichLog).write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def dump_state_log(self):
        is_live = self.query_one("#cb_live").value
        self.sim_broker.log_snapshot(self.market_data, self.time_rem_str, is_live, self.live_broker.balance, self.risk_manager.risk_bankroll)

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
        cap_display = f" (Bankroll: ${self.risk_manager.risk_bankroll:.2f})" if self.risk_initialized else ""
        if is_live:
            lbl.update(f"[bold red]LIVE[/] | Bal: ${self.live_broker.balance:.2f}{cap_display}")
            lbl.classes = "live_mode"
        else:
            lbl.update(f"SIM | Bal: ${self.sim_broker.balance:.2f}{cap_display}")
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
        try:
            now = datetime.now(timezone.utc); floor = (now.minute // 5) * 5
            ts_start = int(now.replace(minute=floor, second=0, microsecond=0).timestamp())
            if not self.risk_initialized:
                try:
                    val = float(self.query_one("#inp_risk_alloc").value)
                    self.risk_manager.set_bankroll(val, is_live=self.query_one("#cb_live").value)
                    self.risk_initialized = True
                except: pass
            if self.market_data["start_ts"] != 0 and ts_start != self.market_data["start_ts"]:
                winner = "UP" if self.market_data["btc_price"] >= self.market_data["btc_open"] else "DOWN"
                self.log_msg(f"[bold yellow]SETTLED:[/][bold white] {winner}[/]")
                
                self.sim_broker.settle_window(winner)
                for p in self.portfolios.values(): p.settle_window(winner, self.market_data["btc_price"], self.market_data["btc_open"])
                
                # Calculate what we would have won from open bets
                total_payout = sum((info["cost"]/info["entry"] if info["side"]==winner else 0) for info in self.window_bets.values() if not info.get("closed"))
                if total_payout > 0:
                    self.log_msg(f"[cyan]💰 Settlement Revenue: +${total_payout:.2f}[/]")
                    self._add_risk_revenue(total_payout)
                else:
                    self._add_risk_revenue(0) # Logic for refill if lost

                self.risk_manager.reset_window(); self.last_second_exit_triggered = False
                self.update_balance_ui(); self.window_bets.clear()
                for s in self.scanners.values(): s.reset()
                self.market_data_manager.reset_history()

            self.market_data["start_ts"] = ts_start
            elapsed = int(now.timestamp()) - ts_start
            slug = f"btc-updown-5m-{ts_start}"
            
            # Direct sync fetcher for background data gathering
            def sync_fetch():
                self.market_data_manager.update_4h_trend()
                c60, l60, h60, _ = self.market_data_manager.fetch_candles_60m()
                cur = self.market_data_manager.fetch_current_price()
                opn = self.market_data_manager.update_history(cur, ts_start, elapsed)
                poly = self.market_data_manager.fetch_polymarket(slug)
                return {"c60":c60, "l60":l60, "h60":h60, "cur":cur, "opn":opn, "poly":poly}

            d = await asyncio.to_thread(sync_fetch)
            
            self.market_data.update({
                "btc_price": d["cur"], "btc_open": d["opn"],
                "up_price": d["poly"]["up_price"], "down_price": d["poly"]["down_price"],
                "up_bid": d["poly"]["up_bid"], "down_bid": d["poly"]["down_bid"],
                "up_ask": d["poly"]["up_ask"], "down_ask": d["poly"]["down_ask"],
                "up_id": d["poly"]["up_id"], "down_id": d["poly"]["down_id"]
            })
            
            rsi = calculate_rsi(d["c60"])
            _, _, lbb = calculate_bb(d["c60"])
            ph = self.market_data_manager.price_history
            fbb = calculate_bb([p['price'] for p in ph[-20:]]) if len(ph) >= 20 else (0,0,0)

            scanner_map = {"NPattern":"#cb_npa","Fakeout":"#cb_fak","TailWag":"#cb_tai","RSI":"#cb_rsi","TrapCandle":"#cb_tra","MidGame":"#cb_mid","LateReversal":"#cb_lat","BullFlag":"#cb_sta","PostPump":"#cb_pos","StepClimber":"#cb_ste","Slingshot":"#cb_sli","MinOne":"#cb_min","Liquidity":"#cb_liq","Cobra":"#cb_cob","Mesa":"#cb_mes","MeanReversion":"#cb_mea","GrindSnap":"#cb_gri","VolCheck":"#cb_vol","Moshe":"#cb_mos","ZScore":"#cb_zsc"}
            
            for name, sc in self.scanners.items():
                if not self.query_one(scanner_map[name]).value: continue
                res = "WAIT"
                if name == "NPattern": res = sc.analyze(ph, d["opn"])
                elif name == "Fakeout": res = sc.analyze(ph, d["opn"], "GREEN" if d["cur"] > d["opn"] else "RED")
                elif name == "TailWag": res = sc.analyze(300-elapsed, 0, 1000, "UP" if d["poly"]["up_bid"]>d["poly"]["down_bid"] else "DOWN", d["cur"], ph)
                elif name == "RSI": res = sc.analyze(rsi, d["cur"], lbb, 300-elapsed)
                elif name == "TrapCandle": res = sc.analyze(ph, d["opn"])
                elif name == "MidGame": res = sc.analyze(ph, d["opn"], elapsed, self.market_data_manager.trend_4h)
                elif name == "LateReversal": res = sc.analyze(ph, d["opn"], elapsed)
                elif name == "BullFlag": res = sc.analyze(d["c60"])
                elif name == "PostPump": res = sc.analyze(d["cur"], d["opn"], {})
                elif name == "StepClimber": res = sc.analyze(d["c60"])
                elif name == "Slingshot": res = sc.analyze(d["c60"])
                elif name == "MinOne": res = sc.analyze(ph, elapsed)
                elif name == "Liquidity": res = sc.analyze(d["cur"], min(d["l60"]) if d["l60"] else 0, d["opn"])
                elif name == "Cobra": res = sc.analyze(d["c60"], d["cur"], elapsed)
                elif name == "Mesa": res = sc.analyze(ph, d["opn"], elapsed)
                elif name == "MeanReversion": res = sc.analyze(ph, fbb, self.market_data_manager.trend_4h)
                elif name == "GrindSnap": res = sc.analyze(ph, elapsed)
                elif name == "VolCheck": res = sc.analyze(d["c60"], d["cur"], d["opn"], elapsed, d["poly"]["up_bid"], d["poly"]["down_bid"])
                elif name == "Moshe": res = sc.analyze(elapsed, d["cur"], d["opn"], self.market_data_manager.trend_4h, d["poly"]["up_bid"], d["poly"]["down_bid"])
                elif name == "ZScore": res = sc.analyze(ph, d["opn"], elapsed)

                if res and "BET_" in str(res) and not any(k.startswith(f"{name}_") for k in self.window_bets):
                    if self.query_one("#cb_one_trade").value and self.window_bets: continue
                    bs = self.risk_manager.calculate_bet_size(str(res), self.portfolios[name].balance, self.portfolios[name].consecutive_losses, {'trend_4h':self.market_data_manager.trend_4h, 'direction':"UP" if "UP" in str(res) else "DOWN"})
                    if bs > 0:
                        sd = "UP" if "UP" in str(res) else "DOWN"
                        pr = self.market_data["up_ask"] if sd == "UP" else self.market_data["down_ask"]
                        if pr and 0.01 < pr < 0.99:
                            is_l = self.query_one("#cb_live").value
                            ok, msg = self.trade_executor.execute_buy(is_l, sd, bs, pr, d["poly"]["up_id" if sd=="UP" else "down_id"], reason=res)
                            if ok:
                                self.window_bets[f"{name}_{time.time()}"] = {"side":sd,"entry":pr,"cost":bs}
                                self.risk_manager.register_bet(bs); self.portfolios[name].record_trade(sd, pr, bs, bs/pr)
                                self.log_msg(f"[bold green]EXECUTED {name}[/]: {msg}")

            self._check_tpsl()
            self.update_balance_ui(); self.update_sell_buttons()
            self.query_one("#p_up").update(f"{self.market_data['up_price']*100:.1f}¢")
            self.query_one("#p_down").update(f"{self.market_data['down_price']*100:.1f}¢")
            self.query_one("#p_btc").update(f"${self.market_data['btc_price']:,.2f}")
            self.query_one("#p_btc_open").update(f"Open: ${self.market_data['btc_open']:,.2f}")
            df = self.market_data['btc_price'] - self.market_data['btc_open']
            self.query_one("#p_btc_diff").update(f"Diff: {'+' if df>=0 else '-'}${abs(df):.2f}")
            self.query_one("#p_trend").update(f"Trend 4H: {self.market_data_manager.trend_4h}")

        except Exception as e: self.log_msg(f"[red]Loop Err: {e}[/]")

    def _check_tpsl(self):
        if not self.query_one("#cb_tp_active").value: return
        try: tp = float(self.query_one("#inp_tp").value)/100; sl = float(self.query_one("#inp_sl").value)/100
        except: tp=1.0; sl=1.0
        for bid, info in list(self.window_bets.items()):
            if info.get("closed"): continue
            side = info["side"]; ent = info["entry"]; cur = self.market_data["up_price"] if side=="UP" else self.market_data["down_price"]
            roi = (cur-ent)/ent; reason = None
            if cur >= 0.99: reason = f"MAX PROFIT (99¢) | Ent: {ent*100:.1f}¢ -> {cur*100:.1f}¢ (+{roi*100:.1f}%)"
            elif roi >= tp: reason = f"TP HIT | Ent: {ent*100:.1f}¢ -> {cur*100:.1f}¢ (+{roi*100:.1f}%)"
            elif roi <= -sl: reason = f"SL HIT | Ent: {ent*100:.1f}¢ -> {cur*100:.1f}¢ ({roi*100:.1f}%)"
            if reason:
                is_l = self.query_one("#cb_live").value
                cbid = self.market_data["up_bid"] if side=="UP" else self.market_data["down_bid"]
                lp = 0.99 if not is_l and cbid >= 0.95 else max(0.02, cbid-0.02)
                ok, msg = self.trade_executor.execute_sell(is_l, side, self.market_data["up_id" if side=="UP" else "down_id"], lp, cbid, reason=reason)
                if ok:
                    self.log_msg(f"[bold yellow]⚡ {reason} | Closed {side} @ {cur*100:.1f}¢[/]")
                    info["closed"] = True
                    try: 
                        # Extract revenue from msg: "Sold X shares for $Y.ZZ (Reason)"
                        revenue = float(msg.split("$")[1].split(" ")[0])
                        self._add_risk_revenue(revenue)
                    except: pass

    async def _run_last_second_exit(self, is_live):
        sides = set()
        if is_live: sides.update(info["side"] for info in self.window_bets.values() if not info.get("closed"))
        else:
            if self.sim_broker.shares["UP"] > 0: sides.add("UP")
            if self.sim_broker.shares["DOWN"] > 0: sides.add("DOWN")
        for side in sides:
            tid = self.market_data["up_id" if side=="UP" else "down_id"]
            cbid = self.market_data["up_bid"] if side=="UP" else self.market_data["down_bid"]
            # For SIM: Sell at Bid (Realism). For LIVE: Sell at slightly below Bid to ensure fill (Limit Order)
            lp = cbid if not is_live else max(0.01, cbid - 0.05)
            # If Sim and Bid is 0, we can't sell (or sell for 0)
            if not is_live and lp <= 0.001: lp = 0.0
            
            ok, msg = self.trade_executor.execute_sell(is_live, side, tid, lp, cbid, reason="Last Second Exit")
            if ok:
                self.call_from_thread(self.log_msg, f"[bold {'red' if is_live else 'green'}]⏱ FINAL EXIT {side}: {msg}[/]")
                for info in self.window_bets.values(): 
                    if info["side"] == side: info["closed"] = True
                try: 
                    revenue = float(msg.split("$")[1].split(" ")[0])
                    self._add_risk_revenue(revenue)
                except: pass

    def update_timer(self):
        if not self.market_data["start_ts"]: return
        rem = max(0, TradingConfig.WINDOW_SECONDS - int(time.time() - self.market_data["start_ts"]))
        self.time_rem_str = f"{rem//60:02d}:{rem%60:02d}"
        self.query_one("#lbl_timer_big").update(self.time_rem_str)
        if rem <= 8 and not self.last_second_exit_triggered:
            self.last_second_exit_triggered = True
            self.run_worker(self._run_last_second_exit(self.query_one("#cb_live").value), thread=True)
        run = int(time.time() - self.app_start_time)
        self.query_one("#lbl_runtime").update(f" | RUN: {run//3600:02d}:{(run%3600)//60:02d}:{run%60:02d}")

    def _add_risk_revenue(self, amount):
        """Adds revenue back to the usable bankroll with strict wallet and target clamping."""
        if not self.risk_initialized: return
        
        is_live = self.query_one("#cb_live").value
        main_bal = self.live_broker.balance if is_live else self.sim_broker.balance

        # 1. Add revenue to current bankroll
        self.risk_manager.risk_bankroll += amount
        
        # 2. Hard Clamping: Never exceed the Wallet Balance
        if self.risk_manager.risk_bankroll > main_bal:
            self.risk_manager.risk_bankroll = main_bal

        # 3. Refill Logic: If we are below target, check if general balance allows for replenishment
        if self.risk_manager.risk_bankroll < self.risk_manager.target_bankroll:
            if main_bal >= self.risk_manager.target_bankroll:
                 self.risk_manager.risk_bankroll = self.risk_manager.target_bankroll
            else:
                 # If wallet is lower than target, bankroll IS the wallet
                 self.risk_manager.risk_bankroll = main_bal
        
        # 4. Final safety clamp: Never exceed Session Target
        if self.risk_manager.risk_bankroll > self.risk_manager.target_bankroll:
            self.risk_manager.risk_bankroll = self.risk_manager.target_bankroll
            
        self.update_balance_ui()

    async def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if "btn_buy_" in bid: 
            await self.trigger_buy("UP" if "_up" in bid else "DOWN")
        elif "btn_sell_" in bid:
            await self.trigger_sell_all("UP" if "_up" in bid else "DOWN")

    async def trigger_buy(self, side):
        try: val = float(self.query_one("#inp_amount").value)
        except: return self.log_msg("[red]Invalid Amount[/]")
        if self.risk_initialized and val > self.risk_manager.risk_bankroll + 0.01: return self.log_msg("[red]Insuff Risk Cap[/]")
        is_l = self.query_one("#cb_live").value
        pr = self.market_data["up_ask" if side=="UP" else "down_ask"]
        if is_l and pr >= 0.98: return self.log_msg("[red]Price too high[/]")
        tid = self.market_data["up_id" if side=="UP" else "down_id"]
        ok, msg = self.trade_executor.execute_buy(is_l, side, val, pr or 0.5, tid, reason="Manual")
        if ok:
            self.log_msg(f"[bold {'red' if is_l else 'green'}]{msg}[/]")
            if self.risk_initialized: self.risk_manager.register_bet(val)
            self.window_bets[f"Manual_{time.time()}"] = {"side":side,"entry":pr or 0.5,"cost":val}
        self.update_balance_ui(); self.update_sell_buttons()

    async def trigger_sell_all(self, side):
        is_l = self.query_one("#cb_live").value
        tid = self.market_data["up_id" if side=="UP" else "down_id"]
        cbid = self.market_data["up_bid" if side=="UP" else "down_bid"]
        ok, msg = self.trade_executor.execute_sell(is_l, side, tid, max(0.02, cbid-0.05), cbid, reason="Manual")
        if ok:
            self.log_msg(f"[bold {'red' if is_l else 'green'}]{msg}[/]")
            try: 
                revenue = float(msg.split("$")[1].split(" ")[0])
                self._add_risk_revenue(revenue)
            except: pass
        self.update_balance_ui(); self.update_sell_buttons()

from textual.screen import ModalScreen
from .scanners import ALGO_INFO

from textual.widgets import Static

class AlgoInfoModal(ModalScreen):
    """A modal that shows algo details."""
    def __init__(self, name, full_name, description):
        super().__init__()
        self.algo_id = name
        self.full_name = full_name
        self.description = description

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield Static(f"[bold cyan]{self.algo_id}[/] - {self.full_name}", id="modal_title")
            yield Static(self.description, id="modal_body")
            with Horizontal(id="modal_footer"):
                yield Button("CLOSE", id="close_btn", variant="primary")

    def on_mount(self):
        # Center the modal on screen
        self.styles.align = ("center", "middle")
        
        container = self.query_one("#modal_container")
        container.styles.background = "#222222"
        container.styles.border = ("thick", "cyan")
        container.styles.padding = (1, 2)
        container.styles.width = 60
        container.styles.height = "auto"
        container.styles.align = ("center", "middle")
        
        self.query_one("#modal_title").styles.margin = (0, 0, 1, 0)
        self.query_one("#modal_title").styles.text_align = "center"
        self.query_one("#modal_title").styles.width = "100%"
        
        self.query_one("#modal_body").styles.margin = (0, 0, 2, 0)
        self.query_one("#modal_body").styles.text_align = "center"
        self.query_one("#modal_body").styles.width = "100%"

        footer = self.query_one("#modal_footer")
        footer.styles.height = "auto"
        footer.styles.align = ("center", "middle")
        footer.styles.width = "100%"

    @on(Button.Pressed, "#close_btn")
    def close_modal(self):
        self.dismiss()
