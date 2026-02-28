import os
import csv
import time
from datetime import datetime

from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, Label, Input, Button, Checkbox, RadioButton, RadioSet
from textual import on

from .scanners import ALGO_INFO


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
    BINDINGS = [("escape", "dismiss", "Dismiss"), ("a", "apply", "Apply"), ("r", "reset", "Reset")]
    
    def __init__(self, main_app=None):
        super().__init__()
        self.main_app = main_app
        
    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield Static("[bold yellow]⚡ BULLFLAG SETTINGS[/]", id="modal_title")
            yield Static("[dim]Tune BullFlag (StaircaseBreakout) parameters live[/]", id="modal_subtitle")
            
            with Vertical(id="bf_scroll_area"):
                # --- Max Price Threshold ---
                yield Static("🎯 Max Price Threshold (¢):", id="label_max_price", classes="bf_label")
                with Horizontal(id="row_max_price", classes="bf_row"):
                    yield Input(placeholder="80", id="inp_max_price", value="80")
                    yield Static("[dim]Skip when price > threshold (70-90¢)[/]", classes="bf_hint")
                
                # --- Volume Filter ---
                yield Static("📊 Volume Filter:", id="label_volume", classes="bf_label")
                with Horizontal(id="row_volume", classes="bf_row"):
                    yield Checkbox("Enable volume confirmation", id="cb_volume_confirm", value=False)
                
                # --- Entry Timing ---
                yield Static("⚡ Entry Timing:", id="label_entry_timing", classes="bf_label")
                with Horizontal(id="row_entry_timing", classes="bf_row"):
                    with RadioSet(id="rs_entry_timing"):
                        yield RadioButton("Aggressive (enter immediately)", id="rb_aggressive", value=True)
                        yield RadioButton("Conservative (wait for confirmation)", id="rb_conservative")
                
                # --- Pullback Detection ---
                yield Static("🔧 Pullback Detection:", id="label_pullback", classes="bf_label")
                with Horizontal(id="row_pullback", classes="bf_row"):
                    yield Checkbox("Enable pullback detection (wait for retest)", id="cb_pullback", value=False)
                
                # --- Dynamic Tolerance ---
                yield Static("🎯 Dynamic Tolerance (ATR-based %):", id="label_tolerance", classes="bf_label")
                with Horizontal(id="row_tolerance", classes="bf_row"):
                    yield Input(placeholder="0.1", id="inp_tolerance", value="0.1")
                    yield Static("[dim]Range: 0.05 – 0.30[/]", classes="bf_hint")
                
                # --- ATR Multiplier ---
                yield Static("📈 ATR Multiplier:", id="label_atr_mult", classes="bf_label")
                with Horizontal(id="row_atr_mult", classes="bf_row"):
                    yield Input(placeholder="1.5", id="inp_atr_mult", value="1.5")
                    yield Static("[dim]Range: 1.0x – 3.0x[/]", classes="bf_hint")
                
                # --- Research Log ---
                yield Static("📊 Research Log:", id="label_research_log", classes="bf_label")
                with Horizontal(id="row_research", classes="bf_row"):
                    yield Checkbox("Enable research logging (lg/bullflag_research_*.csv)", id="cb_research_log", value=False)
            
            # --- Status + Buttons pinned at bottom ---
            yield Static("", id="bf_status")
            with Horizontal(id="bf_button_row"):
                yield Button("APPLY & CLOSE (A)", id="btn_bf_apply", variant="primary")
                yield Button("RESET (R)", id="btn_bf_reset", variant="default")
                yield Button("DISMISS", id="btn_bf_dismiss")

    def on_mount(self):
        self.styles.align = ("center", "middle")
        self.styles.background = "rgba(0,0,0,0.85)"
        
        c = self.query_one("#modal_container")
        c.styles.background = "#1a1a00"
        c.styles.border = ("thick", "#ffaa00")
        c.styles.padding = (1, 2)
        c.styles.width = 70
        c.styles.height = "auto"
        c.styles.max_height = "85vh"
        c.styles.align = ("center", "middle")
        c.styles.overflow_y = "hidden"
        
        # Scrollable settings area
        sa = self.query_one("#bf_scroll_area")
        sa.styles.height = "auto"
        sa.styles.max_height = "60vh"
        sa.styles.overflow_y = "auto"
        sa.styles.width = "100%"
        
        self.query_one("#modal_title").styles.text_align = "center"
        self.query_one("#modal_title").styles.width = "100%"
        self.query_one("#modal_title").styles.margin = (0, 0, 0, 0)
        
        self.query_one("#modal_subtitle").styles.text_align = "center"
        self.query_one("#modal_subtitle").styles.width = "100%"
        self.query_one("#modal_subtitle").styles.margin = (0, 0, 1, 0)
        
        # Style all section labels
        for lbl in self.query(".bf_label"):
            lbl.styles.color = "#ffaa00"
            lbl.styles.text_style = "bold"
            lbl.styles.margin = (1, 0, 0, 0)
            lbl.styles.width = "100%"
        
        # Style all rows
        for row in self.query(".bf_row"):
            row.styles.height = "auto"
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 2)
            row.styles.width = "100%"
        
        # Style hint text
        for hint in self.query(".bf_hint"):
            hint.styles.color = "#666666"
            hint.styles.margin = (1, 0, 0, 1)
        
        # Style input fields
        for inp_id in ["#inp_max_price", "#inp_tolerance", "#inp_atr_mult"]:
            self.query_one(inp_id).styles.width = 12
        
        # Status line
        st = self.query_one("#bf_status")
        st.styles.text_align = "center"
        st.styles.width = "100%"
        st.styles.margin = (1, 0, 0, 0)
        st.styles.color = "#666666"
        
        # Button row
        br = self.query_one("#bf_button_row")
        br.styles.height = "auto"
        br.styles.align = ("center", "middle")
        br.styles.margin = (1, 0, 0, 0)
        br.styles.width = "100%"
        
        # Load current scanner values if available
        self._load_current_settings()
    
    def _load_current_settings(self):
        """Pre-fill inputs from current scanner state."""
        if not self.main_app or not hasattr(self.main_app, 'scanners'):
            return
        if 'BullFlag' not in self.main_app.scanners:
            return
        sc = self.main_app.scanners['BullFlag']
        try:
            if hasattr(sc, 'max_price'):
                self.query_one("#inp_max_price").value = str(sc.max_price)
            if hasattr(sc, 'volume_confirm'):
                self.query_one("#cb_volume_confirm").value = bool(sc.volume_confirm)
            if hasattr(sc, 'entry_timing'):
                self.query_one("#rb_aggressive").value = (sc.entry_timing == "AGGRESSIVE")
            if hasattr(sc, 'pullback'):
                self.query_one("#cb_pullback").value = bool(sc.pullback)
            if hasattr(sc, 'tolerance_pct'):
                self.query_one("#inp_tolerance").value = str(sc.tolerance_pct)
            if hasattr(sc, 'atr_multiplier'):
                self.query_one("#inp_atr_mult").value = str(sc.atr_multiplier)
            if hasattr(sc, 'research_enabled'):
                self.query_one("#cb_research_log").value = bool(sc.research_enabled)
        except Exception:
            pass
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_bf_apply":
            self._apply_settings()
            self.dismiss()
        elif event.button.id == "btn_bf_reset":
            self._reset_settings()
        elif event.button.id == "btn_bf_dismiss":
            self.dismiss()
    
    def action_apply(self):
        self._apply_settings()
        self.dismiss()
    
    def action_reset(self):
        self._reset_settings()
    
    def _apply_settings(self):
        """Apply BullFlag improvements based on user selections."""
        try:
            max_price = float(self.query_one("#inp_max_price").value)
        except ValueError:
            max_price = 80.0
        volume_confirm = self.query_one("#cb_volume_confirm").value
        entry_timing = self.query_one("#rb_aggressive").value
        pullback = self.query_one("#cb_pullback").value
        try:
            tolerance = float(self.query_one("#inp_tolerance").value)
        except ValueError:
            tolerance = 0.1
        try:
            atr_mult = float(self.query_one("#inp_atr_mult").value)
        except ValueError:
            atr_mult = 1.5
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
            
            entry_str = "AGGRESSIVE" if entry_timing else "CONSERVATIVE"
            self.main_app.log_msg(
                "⚡ BullFlag settings applied: Max=$%.2f, Volume=%s, Entry=%s, Pullback=%s, Tolerance=%.2f, ATR=%.1fx, Research=%s" % (
                    max_price, "ON" if volume_confirm else "OFF",
                    entry_str, "ON" if pullback else "OFF",
                    tolerance, atr_mult,
                    "ON" if research_enabled else "OFF"))
            
            # Update status in modal
            self.query_one("#bf_status").update("[bold green]✓ Settings applied successfully[/]")
        else:
            self.query_one("#bf_status").update("[bold red]✗ BullFlag scanner not found[/]")
    
    def _reset_settings(self):
        """Reset BullFlag settings to defaults."""
        self.query_one("#inp_max_price").value = "80"
        self.query_one("#cb_volume_confirm").value = False
        self.query_one("#rb_aggressive").value = True
        self.query_one("#cb_pullback").value = False
        self.query_one("#inp_tolerance").value = "0.1"
        self.query_one("#inp_atr_mult").value = "1.5"
        self.query_one("#cb_research_log").value = False
        
        self.query_one("#bf_status").update("[bold cyan]↻ Settings reset to defaults[/]")
        if self.main_app:
            self.main_app.log_msg("🔄 BullFlag settings reset to defaults")
