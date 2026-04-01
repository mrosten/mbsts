import os
try:
    import winsound
except ImportError:
    class MockWinsound:
        SND_FILENAME = 131072
        SND_ASYNC = 1
        def Beep(self, f, d): pass
        def PlaySound(self, p, f): pass
    winsound = MockWinsound()
import threading
import csv
import time
import json
from datetime import datetime

from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Container, VerticalScroll
from textual.widgets import (
    Static, Label, Input, Button, Checkbox, RadioButton, RadioSet, 
    Select, Collapsible, DataTable, Markdown, TextArea, RichLog
)
from textual import on, events
import sqlite3

# Handle imports for both package and direct execution
try:
    from .scanners import ALGO_INFO
    from .darwin_agent import DarwinAgent, DARWIN_OBSERVATIONS, DARWIN_EXPERIMENT_LOG, DARWIN_CURRENT_ALGO
    from .config import DB_PATH
except ImportError:
    # Running directly from vortex_pulse directory
    from scanners import ALGO_INFO
    from darwin_agent import DarwinAgent, DARWIN_OBSERVATIONS, DARWIN_EXPERIMENT_LOG, DARWIN_CURRENT_ALGO
    from config import DB_PATH
# (Markdown, TextArea, RichLog moved to widgets import block)


class GlobalSettingsModal(ModalScreen):
    """A modal that shows global settings."""
    BINDINGS = [("escape", "dismiss", "Dismiss")]
    def __init__(self, main_app=None):
        super().__init__()
        self.main_app = main_app

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield Static("[bold #00ffff]Global Settings[/]", id="modal_title")
            
            with Collapsible(title="System & Logging", id="gp_system", classes="settings_group"):
                with Horizontal(classes="setting_row"):
                    yield Label("Full Wallet Sync:", classes="setting_label")
                    yield Checkbox(id="cb_sync_risk")
                with Horizontal(classes="setting_row"):
                    yield Label("Official Audit:", classes="setting_label")
                    yield Checkbox(id="cb_audit_enabled")
            
            with Collapsible(title="Trading & Risk Caps", id="gp_trading", classes="settings_group"):
                with Horizontal(classes="setting_row"):
                    yield Label("Safety Mode:", classes="setting_label")
                    yield Select([
                        ("Global Lock", "global_lock"),
                        ("Side Lock", "side_lock"),
                        ("Unrestricted", "unrestricted"),
                        ("Risk Cap", "risk_cap"),
                        ("Dynamic", "dynamic"),
                        ("Original (v5bu6)", "original")
                    ], id="sel_exec_safety", value="global_lock", classes="setting_select")
                
                with Horizontal(classes="setting_row"):
                    yield Label("Market Freq (m):", classes="setting_label")
                    yield Select([("5 Min", 5), ("15 Min", 15)], id="sel_market_freq", value=5, classes="setting_select")
                
                with Horizontal(classes="setting_row"):
                    yield Label("Total Risk Cap ($):", classes="setting_label")
                    yield Input(placeholder="30.00", id="inp_risk_cap", classes="setting_input")

            with Collapsible(title="Advanced Strategy Modules", id="gp_advanced", classes="sub_modal_group"):
                with Horizontal(classes="button_row"):
                    yield Button("TREND EFFICIENCY", id="btn_trend_eff", variant="warning")
                    yield Button("CONVICTION", id="btn_conviction_scaling", variant="success")
                with Horizontal(classes="button_row"):
                    yield Button("VOLATILITY SCALING", id="btn_vol_scaling", variant="default")
                    yield Button("VALUE RE-ENTRY (RD2)", id="btn_value_reentry", variant="default")

            with Collapsible(title="DB DATA LOGGING (Shared)", id="gp_db_logging", classes="settings_group"):
                with Horizontal(classes="setting_row"):
                    yield Label("Unified Event Log:", classes="setting_label")
                    yield Checkbox(id="cb_db_windows")
                with Horizontal(classes="setting_row"):
                    yield Label("Alpha Ledger:", classes="setting_label")
                    yield Checkbox(id="cb_db_alpha")
                with Horizontal(classes="setting_row"):
                    yield Label("Darwin AI Vault:", classes="setting_label")
                    yield Checkbox(id="cb_db_darwin")
                with Horizontal(classes="setting_row"):
                    yield Label("Granular Tick Archive:", classes="setting_label")
                    yield Checkbox(id="cb_db_ticks")
                with Horizontal(classes="setting_row"):
                    yield Label("Contextual Metadata:", classes="setting_label")
                    yield Checkbox(id="cb_db_context")
                with Horizontal(classes="setting_row"):
                    yield Label("Tick Freq (s):", classes="setting_label")
                    yield Input(placeholder="1", id="inp_tick_freq", classes="setting_input")
            
            with Collapsible(title="Darwin AI Mode", id="gp_darwin", classes="settings_group"):
                with Horizontal(classes="setting_row"):
                    yield Label("Operating Mode:", classes="setting_label")
                    yield RadioSet(
                        RadioButton("Observer (V1)", id="rb_v1"),
                        RadioButton("Experimenter (V2)", id="rb_v2"),
                        RadioButton("Director (V3)", id="rb_v3", value=True),
                        id="rs_darwin_mode"
                    )

            with Horizontal(id="modal_footer"):
                yield Button("SAVE & CLOSE", id="btn_modal_close", variant="primary")
                yield Button("CANCEL", id="btn_modal_cancel")

    def on_mount(self):
        self.styles.align = ("center", "middle")
        
        container = self.query_one("#modal_container")
        container.styles.background = "#1a1a1a"
        container.styles.border = ("thick", "#00ffff")
        container.styles.padding = (1, 2)
        container.styles.width = 54
        container.styles.height = "auto"
        container.styles.align = ("center", "middle")
        
        self.query_one("#modal_title").styles.margin = (0, 0, 1, 0)
        self.query_one("#modal_title").styles.text_align = "center"
        self.query_one("#modal_title").styles.width = "100%"
        
        # Style collapsibles
        for c in self.query("Collapsible"):
            c.styles.margin = (0, 0, 1, 0)
            # Remove default collapsible borders if they are too noisy
            # c.styles.border = ("solid", "#333333")
            
        # Style rows and labels
        for row in self.query(".setting_row"):
            row.styles.height = 3
            row.styles.align = ("left", "middle")
            row.styles.width = "100%"
            row.styles.margin = (0, 0)
            
        for label in self.query(".setting_label"):
            label.styles.width = 24
            label.styles.content_align = ("left", "middle")
            label.styles.margin = (0, 1, 0, 1) # Removed top margin for better vertical centering
            
        # Style inputs and selects
        for widget in self.query(".setting_input, .setting_select"):
            widget.styles.width = 20
            widget.styles.height = 3 # Increased from 1 to fix Select rendering issues
            
        self.query_one("#inp_risk_cap").styles.width = 12
        
        # CSV freq removed
        
        if self.main_app:
            self.query_one("#cb_sync_risk").value = getattr(self.main_app, "auto_sync_risk", False)
            self.query_one("#sel_exec_safety").value = getattr(self.main_app, "exec_safety_mode", "global_lock")
            self.query_one("#inp_risk_cap").value = str(getattr(self.main_app, "total_risk_cap", 30.0))
            if hasattr(self.main_app, "config"):
                self.query_one("#sel_market_freq").value = self.main_app.config.MARKET_FREQ

        # Load DB toggles
        if self.main_app:
            self.query_one("#cb_db_windows").value = getattr(self.main_app, "db_log_windows", False)
            self.query_one("#cb_db_alpha").value = getattr(self.main_app, "db_log_alpha", False)
            self.query_one("#cb_db_darwin").value = getattr(self.main_app, "db_log_darwin", False)
            self.query_one("#cb_db_ticks").value = getattr(self.main_app, "db_log_ticks", False)
            self.query_one("#cb_db_context").value = getattr(self.main_app, "db_log_context", False)
            self.query_one("#inp_tick_freq").value = str(getattr(self.main_app, "db_tick_freq", 1))
            self.query_one("#cb_audit_enabled").value = getattr(self.main_app, "official_audit_enabled", True)
            
            # Darwin Mode
            mode = self.main_app.config.DARWIN_MODE
            if mode == "v2": self.query_one("#rb_v2").value = True
            else: self.query_one("#rb_v1").value = True

        # Style button rows
        for row in self.query(".button_row"):
            row.styles.height = 3
            row.styles.align = ("center", "middle")
            row.styles.width = "100%"
            
        self.query_one("#btn_trend_eff").styles.width = 22
        self.query_one("#btn_conviction_scaling").styles.width = 22
        self.query_one("#btn_vol_scaling").styles.width = 22
        self.query_one("#btn_value_reentry").styles.width = 22

        footer = self.query_one("#modal_footer")
        footer.styles.height = "auto"
        footer.styles.align = ("center", "middle")
        footer.styles.width = "100%"
        footer.styles.margin = (1, 0, 0, 0)

    def action_dismiss(self):
        self.close_modal()

    @on(Button.Pressed, "#btn_trend_eff")
    def open_trend_eff(self):
        if self.main_app:
            self.main_app.push_screen(TrendEfficiencyModal(self.main_app))

    @on(Button.Pressed, "#btn_conviction_scaling")
    def open_conviction_scaling(self):
        if self.main_app:
            self.main_app.push_screen(ConvictionScalingModal(self.main_app))

    @on(Button.Pressed, "#btn_vol_scaling")
    def open_vol_scaling(self):
        if self.main_app:
            self.main_app.push_screen(VolatilityScalingModal(self.main_app))

    @on(Button.Pressed, "#btn_value_reentry")
    def open_value_reentry(self):
        if self.main_app:
            self.main_app.push_screen(ValueReentryModal(self.main_app))

    @on(Button.Pressed, "#btn_modal_cancel")
    def action_cancel(self):
        self.dismiss(False)

    @on(Button.Pressed, "#btn_modal_close")
    def close_modal(self):
        if self.main_app:
            try:
                # CSV freq removed
                pass
                self.main_app.auto_sync_risk = self.query_one("#cb_sync_risk").value
                self.main_app.exec_safety_mode = self.query_one("#sel_exec_safety").value
                self.main_app.total_risk_cap = float(self.query_one("#inp_risk_cap").value)
                
                # Save DB toggles
                self.main_app.db_log_windows = self.query_one("#cb_db_windows").value
                self.main_app.db_log_alpha   = self.query_one("#cb_db_alpha").value
                self.main_app.db_log_darwin  = self.query_one("#cb_db_darwin").value
                self.main_app.db_log_ticks   = self.query_one("#cb_db_ticks").value
                self.main_app.db_log_context = self.query_one("#cb_db_context").value
                
                try: self.main_app.db_tick_freq = int(self.query_one("#inp_tick_freq").value)
                except: pass
                
                aud_val = self.query_one("#cb_audit_enabled").value
                self.main_app.official_audit_enabled = aud_val
                self.main_app.log_msg(f"SETTING: Official Audit | Status: {'ENABLED' if aud_val else 'DISABLED'}", level="SYS")
                
                # Darwin Mode
                rs = self.query_one("#rs_darwin_mode")
                if rs.pressed_button:
                    new_mode = "v2" if rs.pressed_button.id == "rb_v2" else "v1"
                    if self.main_app.config.DARWIN_MODE != new_mode:
                        self.main_app.config.DARWIN_MODE = new_mode
                        if hasattr(self.main_app, "darwin"):
                            self.main_app.darwin.mode = new_mode
                            self.main_app.log_msg(f"🧬 Darwin AI Mode switched to [bold cyan]{new_mode.upper()}[/]")
                
                # Check for frequency change
                if hasattr(self.main_app, "config"):
                    old_freq = self.main_app.config.MARKET_FREQ
                    new_freq = int(self.query_one("#sel_market_freq").value)
                    if old_freq != new_freq:
                        # Push the safety prompt!
                        self.main_app.push_screen(FrequencySwitchPrompt(self.main_app, new_freq))
                        self.dismiss()
                        return

                self.main_app.save_settings()
            except Exception:
                pass
        self.dismiss()


class FrequencySwitchPrompt(ModalScreen):
    """A dialog that warns about frequency changes and offers position exit."""
    BINDINGS = [("escape", "dismiss", "Dismiss")]
    def __init__(self, main_app, new_freq):
        super().__init__()
        self.main_app = main_app
        self.new_freq = new_freq

    def compose(self) -> ComposeResult:
        pos_count = len(getattr(self.main_app, "window_bets", {}))
        with Vertical(id="modal_container"):
            yield Static("[bold yellow]⚠️ WARNING: MARKET FREQUENCY CHANGE[/]", id="modal_title")
            yield Static(f"Finalizing session for {self.main_app.config.MARKET_FREQ}m market.", classes="prompt_text")
            yield Static(f"New session will begin for [bold cyan]{self.new_freq}m[/] market.", classes="prompt_text")
            
            if pos_count > 0:
                yield Static(f"[bold red]CRITICAL:[/] You have {pos_count} active position(s).", id="pos_warning")
                yield Static("Changing frequency mid-stream may cause tracking issues.", classes="prompt_text")
                yield Horizontal(
                    Button("EXIT ALL & SWITCH", id="btn_exit_switch", variant="error"),
                    Button("SWITCH REGARDLESS", id="btn_just_switch", variant="warning"),
                    classes="prompt_row"
                )
            else:
                yield Static("No active positions found. Ready to transition.", classes="prompt_text")
                yield Horizontal(
                    Button("PROCEED WITH SWITCH", id="btn_just_switch", variant="primary"),
                    classes="prompt_row"
                )
            
            yield Horizontal(
                Button("CANCEL", id="btn_cancel", variant="default"),
                classes="prompt_row"
            )

    def on_mount(self):
        self.styles.align = ("center", "middle")
        c = self.query_one("#modal_container")
        c.styles.background = "#222222"
        c.styles.border = ("thick", "yellow")
        c.styles.padding = (1, 2)
        c.styles.width = 50
        c.styles.height = "auto"
        c.styles.align = ("center", "middle")
        
        self.query_one("#modal_title").styles.text_align = "center"
        self.query_one("#modal_title").styles.margin = (0, 0, 1, 0)

        for s in self.query(".prompt_text"):
            s.styles.text_align = "center"
            s.styles.margin = (0, 0, 1, 0)
            s.styles.width = "100%"

        if self.query("#pos_warning"):
            self.query_one("#pos_warning").styles.text_align = "center"
            self.query_one("#pos_warning").styles.margin = (1, 0)
            self.query_one("#pos_warning").styles.width = "100%"

        for r in self.query(".prompt_row"):
            r.styles.height = 3
            r.styles.align = ("center", "middle")
            r.styles.width = "100%"
            r.styles.margin = (1, 0, 0, 0)

    @on(Button.Pressed, "#btn_cancel")
    def on_cancel(self):
        self.dismiss()

    @on(Button.Pressed, "#btn_just_switch")
    async def on_just_switch(self):
        if self.main_app:
            await self.main_app.perform_frequency_switch(self.new_freq, exit_positions=False)
        self.dismiss()

    @on(Button.Pressed, "#btn_exit_switch")
    async def on_exit_switch(self):
        if self.main_app:
            await self.main_app.perform_frequency_switch(self.new_freq, exit_positions=True)
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
            
            # Enhanced weight section with help text
            with Vertical(id="modal_algo_weight", classes="setting_section"):
                yield Static("[bold #00ff88]Algorithm Weight[/]", classes="section_title")
                yield Static("Multiplier applied to bet size when this scanner triggers. Higher values = larger positions. Default: 1.0x", classes="help_text")
                with Horizontal():
                    yield Label("Weight Multiplier (x):", id="lbl_algo_weight")
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
            elif self.algo_id in ["MOM", "MM2"]:
                with Vertical(id="modal_momentum_settings", classes="setting_section"):
                    yield Static(f"[bold #00ff88]{self.algo_id} Strategy[/]", classes="section_title")
                    yield Static("Configure entry timing and threshold behavior for momentum-based trading.", classes="help_text")
                    
                    # --- Trading Mode ---
                    yield Static("[bold #aaaaaa]🎯 Trading Mode[/]", classes="subsection_title")
                    with Horizontal(id="modal_mom_row1", classes="spaced_row"):
                        yield Label("Mode:", classes="field_label")
                        if self.algo_id == "MM2":
                            modes = [("VECTOR", "VECTOR"), ("TIME", "TIME"), ("PRICE", "PRICE"), ("DURATION", "DURATION")]
                        else:
                            modes = [("TIME", "TIME"), ("PRICE", "PRICE"), ("DURATION", "DURATION")]
                        scanner_key = "Momentum" if self.algo_id == "MOM" else "MM2"
                        mom = self.main_app.scanners.get(scanner_key)
                        initial_mode = getattr(mom, "mode", "TIME" if self.algo_id == "MOM" else "VECTOR")
                        yield Select(modes, value=initial_mode, id="sel_mom_mode", classes="mode_select")
                    
                    with Vertical(id="modal_mode_explanation"):
                        yield Static("", id="lbl_mode_explanation")
                    
                    # --- Entry Thresholds ---
                    yield Static("[bold #aaaaaa]⚡ Entry Thresholds[/]", classes="subsection_title")
                    with Horizontal(id="modal_mom_threshold", classes="spaced_row"):
                        yield Label("Threshold (¢):", classes="field_label")
                        yield Input(placeholder="60", id="inp_mom_threshold")
                    with Horizontal(id="modal_mom_wait_time", classes="spaced_row"):
                        yield Label("Wait Time (s):", classes="field_label")
                        yield Input(placeholder="10", id="inp_mom_duration")
                    
                    # --- Buy Mode ---
                    yield Static("[bold #aaaaaa]💰 Buy Mode[/]", classes="subsection_title")
                    with Horizontal(classes="buymode_row"):
                        yield Checkbox(label="STN", value=True, id="cb_mom_std")
                        yield Static("Standard - Threshold/time signals", classes="mode_desc")
                    with Horizontal(classes="buymode_row"):
                        yield Checkbox(label="PBN", value=False, id="cb_mom_pre")
                        yield Static("Pre-Buy - Prediction at T-15s", classes="mode_desc")
                    with Horizontal(classes="buymode_row"):
                        yield Checkbox(label="HBR", value=False, id="cb_mom_hybrid")
                        yield Static("Hybrid - Pre-buys on strong leads", classes="mode_desc")
                    with Horizontal(classes="buymode_row"):
                        yield Checkbox(label="ADV", value=False, id="cb_mom_adv")
                        yield Static("Advanced - Dynamic ATR tiers", classes="mode_desc")
                    
                    # --- Advanced Button ---
                    with Horizontal(id="modal_mom_adv_btn"):
                        yield Button("⚙️ CONFIGURE ADVANCED", id="btn_mom_adv", variant="warning")
            elif self.algo_id == "NIT":
                with Horizontal(id="modal_nit_row1"):
                    yield Label("Time Cutoff (s):", id="lbl_nit_cutoff")
                    yield Input(placeholder="120", id="inp_nit_cutoff")
                with Horizontal(id="modal_nit_row2"):
                    yield Label("ATR Multiplier (x):", id="lbl_nit_atr")
                    yield Input(placeholder="1.0", id="inp_nit_atr")
            elif self.algo_id == "VSN":
                with Horizontal(id="modal_vsn_row1"):
                    yield Label("Time Cutoff (s):", id="lbl_vsn_cutoff")
                    yield Input(placeholder="60", id="inp_vsn_cutoff")
                with Horizontal(id="modal_vsn_row2"):
                    yield Label("Vol Difference B:", id="lbl_vsn_diff")
                    yield Input(placeholder="50.0", id="inp_vsn_diff")
            elif self.algo_id == "HDO":
                with Vertical(id="modal_hdo_settings", classes="setting_section"):
                    yield Static("[bold #00ff88]HDO Hedge Strategy[/]", classes="section_title")
                    yield Static("HDO (Hedge Direction Opposite) protects you when the market moves strongly against your current positions.", classes="help_text")
                    
                    # --- Trigger Price ---
                    yield Static("[bold #aaaaaa]⚡ Activation Trigger[/]", classes="subsection_title")
                    with Horizontal(classes="spaced_row"):
                        yield Label("Trigger Price (¢):", classes="field_label")
                        yield Input(placeholder="59", id="inp_hdo_thresh")
                    yield Static("The hedge fires when the 'other' side's price crosses this level. (e.g. 59¢)", classes="help_text_small")

                    # --- Hedge Mode ---
                    yield Static("[bold #aaaaaa]🛡️ Hedge Mode[/]", classes="subsection_title")
                    with Horizontal(classes="spaced_row"):
                        yield Label("Hedge Style:", classes="field_label")
                        yield Select([
                            ("Recovery", "recovery"),
                            ("Insurance (Delta-Neutral)", "delta_neutral")
                        ], id="sel_hdo_mode", value="recovery", classes="mode_select")
                    
                    with Vertical(id="hdo_mode_help"):
                        yield Static("RECOVERY: Tries to buy enough shares to get your original money back if the hedge wins.", classes="help_text_small", id="lbl_hdo_mode_desc")

                    # --- Coverage ---
                    yield Static("[bold #aaaaaa]📊 Risk Coverage[/]", classes="subsection_title")
                    with Horizontal(classes="spaced_row"):
                        yield Label("Coverage Amount (%):", classes="field_label")
                        yield Input(placeholder="100", id="inp_hdo_coverage")
                    yield Static("How much of the original cost to protect? 100% = Full protection, 50% = Half protection (safer if market reverses).", classes="help_text_small")
            with Horizontal(id="modal_footer"):
                yield Button("CLOSE/SAVE", id="close_btn", variant="primary")

    def on_mount(self):
        """Update the mode explanation on mount."""
        if self.algo_id in ["MOM", "MM2"]:
            self._update_mode_explanation()
        elif self.algo_id == "HDO":
            self._update_hdo_mode_explanation()
        # Center the modal on screen
        self.styles.align = ("center", "middle")
        
        container = self.query_one("#modal_container")
        container.styles.background = "#222222"
        container.styles.border = ("thick", "cyan")
        container.styles.padding = (1, 2)
        container.styles.width = 70
        container.styles.height = "auto"
        container.styles.max_height = "85vh"
        container.styles.overflow_y = "auto"
        container.styles.scrollbar_gutter = "stable"
        container.styles.align = ("center", "middle")
        
        self.query_one("#modal_title").styles.margin = (0, 0, 1, 0)
        self.query_one("#modal_title").styles.text_align = "center"
        self.query_one("#modal_title").styles.width = "100%"
        
        self.query_one("#modal_body").styles.margin = (0, 0, 2, 0)
        self.query_one("#modal_body").styles.text_align = "center"
        self.query_one("#modal_body").styles.width = "100%"

        row_w = self.query_one("#modal_algo_weight")
        row_w.styles.height = "auto"
        row_w.styles.min_height = 4
        row_w.styles.align = ("center", "middle")
        row_w.styles.margin = (0, 0, 1, 0)
        row_w.styles.border = ("ascii", "#444444")
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
        elif self.algo_id in ["MOM", "MM2"]:
            # Style the section container
            sec = self.query_one("#modal_momentum_settings")
            sec.styles.border = ("ascii", "#333333")
            sec.styles.padding = (1, 1)
            sec.styles.margin = (0, 0, 1, 0)
            sec.styles.height = "auto"

            # Style explanation box
            try:
                exp_box = self.query_one("#modal_mode_explanation")
                exp_box.styles.background = "#001a26"
                exp_box.styles.border = ("solid", "#004466")
                exp_box.styles.padding = (0, 1)
                exp_box.styles.margin = (0, 0, 1, 0)
                exp_box.styles.height = "auto"
                exp_box.styles.min_height = 5
                
                explanation = self.query_one("#lbl_mode_explanation")
                explanation.styles.width = "100%"
                explanation.styles.height = "auto"
                explanation.styles.content_align = ("center", "middle")
            except: pass

            # Style rows
            for row in self.query(".spaced_row, .buymode_row"):
                row.styles.height = 3
                row.styles.margin = (0, 0)
                row.styles.align = ("left", "middle")
            
            # Style labels
            for label in self.query(".field_label"):
                label.styles.width = 18
                label.styles.content_align = ("left", "middle")
            
            # Size inputs and selects
            self.query_one("#sel_mom_mode").styles.width = 22
            self.query_one("#sel_mom_mode").styles.height = 3
            self.query_one("#inp_mom_duration").styles.width = 8
            self.query_one("#inp_mom_threshold").styles.width = 8
            
            # Style checkboxes and descriptions
            for cbid in ["#cb_mom_std", "#cb_mom_pre", "#cb_mom_hybrid", "#cb_mom_adv"]:
                try: self.query_one(cbid).styles.margin = (0, 1, 0, 0)
                except: pass
            for desc in self.query(".mode_desc"):
                desc.styles.color = "#888888"
                desc.styles.text_style = "italic"

            # Advanced button
            try:
                self.query_one("#modal_mom_adv_btn").styles.height = 3
                self.query_one("#modal_mom_adv_btn").styles.align = ("center", "middle")
                self.query_one("#modal_mom_adv_btn").styles.margin = (1, 0, 0, 0)
                self.query_one("#btn_mom_adv").styles.width = 26
            except: pass

            if self.main_app:
                scanner_key = "Momentum" if self.algo_id == "MOM" else "MM2"
                if scanner_key in self.main_app.scanners:
                    mom = self.main_app.scanners[scanner_key]
                    self.query_one("#sel_mom_mode").value = str(getattr(mom, "mode", "TIME" if self.algo_id == "MOM" else "VECTOR"))
                    self.query_one("#inp_mom_threshold").value = str(int(getattr(mom, "threshold", 0.6) * 100))
                    self.query_one("#inp_mom_duration").value = str(getattr(mom, "duration", 10))

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
        elif self.algo_id == "NIT" and self.main_app:
            nit = self.main_app.nit_settings
            self.query_one("#inp_nit_cutoff").value = str(nit.get("time_cutoff", 120))
            self.query_one("#inp_nit_atr").value = str(nit.get("atr_multiplier", 1.0))
            
            self.query_one("#inp_nit_cutoff").styles.width = 10
            self.query_one("#inp_nit_atr").styles.width = 10
        elif self.algo_id == "VSN" and self.main_app:
            vsn = self.main_app.vsn_settings
            self.query_one("#inp_vsn_cutoff").value = str(vsn.get("time_cutoff", 60))
            self.query_one("#inp_vsn_diff").value = str(vsn.get("diff_threshold", 50.0))
            
            self.query_one("#inp_vsn_cutoff").styles.width = 10
            self.query_one("#inp_vsn_diff").styles.width = 10
        elif self.algo_id == "HDO" and self.main_app:
            # Style the section container
            sec = self.query_one("#modal_hdo_settings")
            sec.styles.border = ("ascii", "#333333")
            sec.styles.padding = (1, 1)
            sec.styles.margin = (0, 0, 1, 0)
            sec.styles.height = "auto"

            # Style rows
            for row in self.query(".spaced_row"):
                row.styles.height = 3
                row.styles.margin = (0, 0)
                row.styles.align = ("left", "middle")
            
            # Style help text
            for help_t in self.query(".help_text_small"):
                help_t.styles.color = "#888888"
                help_t.styles.text_style = "italic"
                help_t.styles.margin = (0, 0, 1, 1)
                help_t.styles.font_size = 12

            # Style labels
            for label in self.query(".field_label"):
                label.styles.width = 22
                label.styles.content_align = ("left", "middle")
            
            # Size inputs and selects
            self.query_one("#inp_hdo_thresh").styles.width = 10
            self.query_one("#inp_hdo_coverage").styles.width = 10
            self.query_one("#sel_hdo_mode").styles.width = 28
            self.query_one("#sel_hdo_mode").styles.height = 3

            if "HDO" in self.main_app.scanners:
                hdo = self.main_app.scanners["HDO"]
                self.query_one("#inp_hdo_thresh").value = str(int(getattr(hdo, "trigger_threshold", 0.59) * 100))
                self.query_one("#sel_hdo_mode").value = getattr(hdo, "hedge_mode", "recovery")
                self.query_one("#inp_hdo_coverage").value = str(int(getattr(hdo, "coverage_pct", 1.0) * 100))

        footer = self.query_one("#modal_footer")
        footer.styles.height = "auto"
        footer.styles.align = ("center", "middle")
        footer.styles.width = "100%"

    def action_dismiss(self):
        self.close_modal()

    @on(Select.Changed, "#sel_mom_mode")
    def _on_mode_change(self, event: Select.Changed):
        self._update_mode_explanation()

    @on(Select.Changed, "#sel_hdo_mode")
    def _on_hdo_mode_change(self, event: Select.Changed):
        self._update_hdo_mode_explanation()

    def _update_mode_explanation(self):
        """Update the explanation text based on the selected mode."""
        try:
            mode = self.query_one("#sel_mom_mode").value
            explanations = {
                "TIME": "[bold cyan]TIME Mode:[/] Classic leader-pick. Waits for the duration (default 10s) and then bets the side that is leading in cents.",
                "PRICE": "[bold cyan]PRICE Mode:[/] Immediate trigger. Bets as soon as either side hits the specified cent threshold (e.g. 60¢).",
                "DURATION": "[bold cyan]DURATION Mode:[/] Threshold hold. Bets if a side stays above the cent threshold for the full duration.",
                "VECTOR": "[bold cyan]VECTOR Mode (MM2):[/] Unified scoring. Analyzes Price Lead, BTC Velocity, 1H Trend, Sentiment, and RSI simultaneously."
            }
            explanation = explanations.get(mode, "Select a mode to see its behavior.")
            self.query_one("#lbl_mode_explanation").update(explanation)
        except:
            pass

    def _update_hdo_mode_explanation(self):
        """Update the HDO explanation text based on the selected mode."""
        try:
            mode = self.query_one("#sel_hdo_mode").value
            explanations = {
                "recovery": "[bold #00ff88]RECOVERY:[/] Tries to win back your original money. [italic]Risk: If the market flips back to your original side, you lose more.[/]",
                "delta_neutral": "[bold #00ff88]INSURANCE:[/] Buys exactly the same number of shares. [italic]Safe: You lock in a small, fixed loss but avoid a total wipeout.[/]"
            }
            explanation = explanations.get(mode, "Select a mode.")
            self.query_one("#lbl_hdo_mode_desc").update(explanation)
        except:
            pass

    @on(Button.Pressed, "#close_btn")
    def close_modal(self):
        changes = []
        if self.main_app:
            try:
                old_w = self.main_app.scanner_weights.get(self.algo_id, 1.0)
                new_w = float(self.query_one("#inp_algo_weight").value)
                if old_w != new_w:
                    self.main_app.scanner_weights[self.algo_id] = new_w
                    self.main_app.save_settings()
                    changes.append(f"Weight: {old_w} -> {new_w}")
            except: pass

        if self.algo_id == "MOS" and self.main_app and "Moshe" in self.main_app.scanners:
            moshe = self.main_app.scanners["Moshe"]
            
            def check_update(attr, html_id, type_func):
                try:
                    old_v = getattr(moshe, attr, None)
                    new_v = type_func(self.query_one(html_id).value)
                    if old_v != new_v:
                        setattr(moshe, attr, new_v)
                        changes.append(f"Moshe {attr}: {old_v} -> {new_v}")
                except: pass
                
            check_update("bet_size", "#inp_mos_bet", float)
            check_update("t1", "#inp_mos_t1", int)
            check_update("d1", "#inp_mos_d1", float)
            check_update("t2", "#inp_mos_t2", int)
            check_update("d2", "#inp_mos_d2", float)
            check_update("t3", "#inp_mos_t3", int)
            check_update("d3", "#inp_mos_d3", float)
            
        elif self.algo_id in ["MOM", "MM2"] and self.main_app:
            scanner_key = "Momentum" if self.algo_id == "MOM" else "MM2"
            if scanner_key in self.main_app.scanners:
                mom = self.main_app.scanners[scanner_key]
            
            try:
                m = self.query_one("#sel_mom_mode").value
                if m and m in ["TIME", "PRICE", "DURATION", "VECTOR"]:
                    if getattr(mom, "mode", None) != m:
                        changes.append(f"MOM Mode: {getattr(mom, 'mode', None)} -> {m}")
                        mom.mode = m
            except: pass
            try:
                t = int(self.query_one("#inp_mom_threshold").value)
                if 51 <= t <= 70:
                    old_t = int(getattr(mom, "threshold", 0.6) * 100)
                    if old_t != t:
                        mom.threshold = t / 100.0
                        mom.base_threshold = t / 100.0
                        changes.append(f"MOM Threshold: {old_t}¢ -> {t}¢")
            except: pass
            try:
                d = int(self.query_one("#inp_mom_duration").value)
                if d > 0:
                    old_d = getattr(mom, "duration", 10)
                    if old_d != d:
                        mom.duration = d
                        changes.append(f"MOM Duration: {old_d}s -> {d}s")
            except: pass
            # Save Buy Mode
            try:
                if self.query_one("#cb_mom_pre").value:
                    new_bm = "PRE"
                elif self.query_one("#cb_mom_hybrid").value:
                    new_bm = "HYBRID"
                elif self.query_one("#cb_mom_adv").value:
                    new_bm = "ADV"
                else:
                    new_bm = "STD"
                
                old_bm = self.main_app.mom_buy_mode
                if old_bm != new_bm:
                    self.main_app.mom_buy_mode = new_bm
                    self.main_app.save_settings()
                    changes.append(f"MOM Buy Mode: {old_bm} -> {new_bm}")
            except: pass
            
        elif self.algo_id == "NIT" and self.main_app:
            try:
                cutoff = int(self.query_one("#inp_nit_cutoff").value)
                mult = float(self.query_one("#inp_nit_atr").value)
                self.main_app.nit_settings["time_cutoff"] = cutoff
                self.main_app.nit_settings["atr_multiplier"] = mult
                self.main_app.save_settings()
                changes.append(f"NIT: Cutoff={cutoff}s, Mult={mult}x")
                
                # Update the scanner instance directly
                sc = self.main_app.scanners.get("Nitro")
                if sc:
                    sc.time_cutoff = cutoff
                    sc.atr_multiplier = mult
            except: pass
        elif self.algo_id == "VSN" and self.main_app:
            try:
                cutoff = int(self.query_one("#inp_vsn_cutoff").value)
                diff = float(self.query_one("#inp_vsn_diff").value)
                self.main_app.vsn_settings["time_cutoff"] = cutoff
                self.main_app.vsn_settings["diff_threshold"] = diff
                self.main_app.save_settings()
                changes.append(f"VSN: Cutoff={cutoff}s, Diff={diff}B")
                
                # Update the scanner instance directly
                sc = self.main_app.scanners.get("VolSnap")
                if sc:
                    sc.time_cutoff = cutoff
                    sc.diff_threshold = diff
            except: pass
        elif self.algo_id == "HDO" and self.main_app and "HDO" in self.main_app.scanners:
            hdo = self.main_app.scanners["HDO"]
            try:
                t = int(self.query_one("#inp_hdo_thresh").value)
                if 51 <= t <= 99:
                    old_t = int(getattr(hdo, "trigger_threshold", 0.59) * 100)
                    if old_t != t:
                        hdo.trigger_threshold = t / 100.0
                        changes.append(f"HDO Trigger: {old_t}¢ -> {t}¢")
                
                m = self.query_one("#sel_hdo_mode").value
                if m != getattr(hdo, "hedge_mode", "recovery"):
                    old_m = getattr(hdo, "hedge_mode", "recovery")
                    hdo.hedge_mode = m
                    changes.append(f"HDO Mode: {old_m} -> {m}")
                
                c = int(self.query_one("#inp_hdo_coverage").value)
                if 1 <= c <= 200:
                    old_c = int(getattr(hdo, "coverage_pct", 1.0) * 100)
                    if old_c != c:
                        hdo.coverage_pct = c / 100.0
                        changes.append(f"HDO Coverage: {old_c}% -> {c}%")
            except: pass
        elif self.algo_id == "PTP" and self.main_app and "PTP" in self.main_app.scanners:
            ptp = self.main_app.scanners["PTP"]
            try:
                p = float(self.query_one("#inp_ptp_prominence").value)
                if p != getattr(ptp, "prominence", 2.0):
                    ptp.prominence = p
                    changes.append(f"PTP Prom: {p}")
                
                t = int(self.query_one("#inp_ptp_tmid").value)
                if 10 <= t <= 90:
                    ptp.t_mid_pct = t / 100.0
                    changes.append(f"PTP T-Mid: {t}%")
                
                s = float(self.query_one("#inp_ptp_slope").value)
                if s != getattr(ptp, "min_slope", 0.0001):
                    ptp.min_slope = s
                    changes.append(f"PTP Slope: {s}")
                
                b = float(self.query_one("#inp_ptp_breakdown").value)
                if b != getattr(ptp, "breakdown_tolerance", 5.0):
                    ptp.breakdown_tolerance = b
                    changes.append(f"PTP Breakdown: {b}")
            except: pass
            
        if changes and self.main_app:
            change_str = ", ".join(changes)
            self.main_app.log_msg(f"⚙️ Config Update [{self.algo_id}]: {change_str}")
        
        # Always show current MOM settings in console when modal closes
        if self.algo_id in ["MOM", "MM2"] and self.main_app:
            scanner_key = "Momentum" if self.algo_id == "MOM" else "MM2"
            mom = self.main_app.scanners.get(scanner_key)
            if mom:
                self.main_app.log_msg(f"[bold cyan]📋 MOM Current Settings:[/]", level="ADMIN")
                self.main_app.log_msg(f"  [dim]• Mode:[/] {getattr(mom, 'mode', 'TIME')}", level="ADMIN")
                self.main_app.log_msg(f"  [dim]• Buy Mode:[/] {self.main_app.mom_buy_mode}", level="ADMIN")
                self.main_app.log_msg(f"  [dim]• Threshold:[/] {getattr(mom, 'threshold', 0.60):.2f}¢", level="ADMIN")
                self.main_app.log_msg(f"  [dim]• Duration:[/] {getattr(mom, 'duration', 10)}s", level="ADMIN")
                
                # Advanced settings
                adv = getattr(mom, 'adv_settings', {})
                self.main_app.log_msg(f"  [dim]• ATR Tiers:[/] Stable<{adv.get('atr_low', 20)}$ Chaos>{adv.get('atr_high', 40)}$", level="ADMIN")
                self.main_app.log_msg(f"  [dim]• Offsets:[/] Stable{adv.get('stable_offset', 0):+}¢ Chaos{adv.get('chaos_offset', 0):+}¢", level="ADMIN")
                self.main_app.log_msg(f"  [dim]• ATR Floor:[/] ${adv.get('atr_floor', 25.0)}", level="ADMIN")
                self.main_app.log_msg(f"  [dim]• Trend Penalty:[/] {adv.get('trend_penalty', 0.02)*100:.0f}¢", level="ADMIN")
                self.main_app.log_msg(f"  [dim]• Decisive Diff:[/] {adv.get('decisive_diff', 0.02)*100:.0f}¢", level="ADMIN")
                self.main_app.log_msg(f"  [dim]• Auto Switches:[/] PBN(Stable)={adv.get('auto_pbn_stable', False)} STN(Chaos)={adv.get('auto_stn_chaos', False)}", level="ADMIN")
                self.main_app.log_msg(f"  [dim]• Whale Shield:[/] {adv.get('shield_time', 45)}s reach {adv.get('shield_reach', 5)}¢", level="ADMIN")
                
                # Custom exits
                custom_tp = getattr(mom, 'custom_tp', None)
                custom_sl = getattr(mom, 'custom_sl', None)
                if custom_tp or custom_sl:
                    self.main_app.log_msg(f"  [dim]• Custom Exits:[/] TP={custom_tp or 'None'}¢ SL={custom_sl or 'None'}¢", level="ADMIN")
                else:
                    self.main_app.log_msg(f"  [dim]• Custom Exits:[/] Using global TP/SL settings", level="ADMIN")
                    
                self.main_app.log_msg("", level="ADMIN")
            
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
            self.main_app.push_screen(MOMExpertModal(self.main_app, algo_id=self.algo_id))


class MOMExpertModal(ModalScreen):
    """Advanced Momentum settings based on Volatility/ATR."""
    BINDINGS = [("escape", "dismiss", "Dismiss")]
    def __init__(self, main_app, algo_id="MOM"):
        super().__init__()
        self.main_app = main_app
        self.algo_id = algo_id
        if algo_id == "MM2":
            self.s = main_app.mm2_adv_settings
            self.mom = main_app.scanners.get("MM2")
        else:
            self.s = main_app.mom_adv_settings
            self.mom = main_app.scanners.get("Momentum")

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield Static("[bold #ffaa00]MOM — Advanced (ATR-Driven) Settings[/]", id="modal_title")
            yield Static("ATR tiers adjust thresholds and mode dynamically each tick.", id="modal_subtitle")

            with Vertical(id="modal_expert_payload"):
                with Horizontal(id="exp_preset_row"):
                    yield Button("[DEFAULT]", id="btn_preset_def")
                    yield Button("[VOL SHIELD]", id="btn_preset_vol", variant="success")
                    yield Button("[ULTRA PRE]", id="btn_preset_omega", variant="error")

                with Collapsible(title="1. Pre-Buy Mode Overrides", id="exp_coll_1", classes="exp_section"):
                    yield Static("Pre-buy fires at T-15s when ATR ≥ floor (Section 4).", classes="exp_sec_desc")
                    with Horizontal(classes="exp_row"):
                        yield Checkbox(label="PBN on Stable (Aggro)", value=self.s["auto_pbn_stable"], id="exp_over_pbn")
                        yield Checkbox(label="STN on Chaos (Safe)", value=self.s["auto_stn_chaos"], id="exp_over_stn")

                with Collapsible(title="2. ATR Tier Boundaries ($)", id="exp_coll_2", classes="exp_section"):
                    yield Static("BTC 5m ATR thresholds that define Stable / Neutral / Chaos regime.", classes="exp_sec_desc")
                    with Horizontal(classes="exp_row"):
                        yield Label("Stable Ceiling ($):")
                        yield Input(placeholder="20", value=str(self.s["atr_low"]), id="exp_atr_low")
                        yield Label("Chaos Floor ($):")
                        yield Input(placeholder="40", value=str(self.s["atr_high"]), id="exp_atr_high")

                with Collapsible(title="3. Entry Threshold Offsets (¢)", id="exp_coll_3", classes="exp_section"):
                    yield Static("Added to base threshold based on current ATR tier.", classes="exp_sec_desc")
                    with Horizontal(classes="exp_row"):
                        yield Label("Stable Offset (¢):")
                        yield Input(placeholder="-5", value=str(self.s["stable_offset"]), id="exp_off_stable")
                        yield Label("Chaos Offset (¢):")
                        yield Input(placeholder="10", value=str(self.s["chaos_offset"]), id="exp_off_chaos")

                with Collapsible(title="4. Pre-Buy Gate & Trend Filters", id="exp_coll_4", classes="exp_section"):
                    yield Static("Pre-buy is blocked if ATR < floor. Trend bonus widens needed lead.", classes="exp_sec_desc")
                    with Horizontal(classes="exp_row"):
                        yield Label("Min ATR Floor ($):")
                        yield Input(placeholder="25", value=str(self.s.get("atr_floor", 25)), id="exp_atr_floor")
                        yield Label("Trend Lead Bonus (¢):")
                        yield Input(placeholder="2", value=str(int(self.s.get("trend_penalty", 0.02) * 100)), id="exp_trend_penalty")
                    with Horizontal(classes="exp_row"):
                        yield Label("Decisive Lead (¢):")
                        yield Input(placeholder="2", value=str(int(self.s.get("decisive_diff", 0.02) * 100)), id="exp_decisive_diff")
                    
                    yield Static("--- [NEW] Optional Odds-Based Pre-Buy (v5.9.16) ---", classes="exp_sec_desc")
                    with Horizontal(classes="exp_row"):
                        yield Checkbox(label="Enable Odds PBN", value=self.s.get("pbn_odds_enabled", False), id="exp_pbn_odds_enabled")
                        yield Label("Odds Thresh (¢):")
                        yield Input(placeholder="2.0", value=str(self.s.get("pbn_odds_thresh", 2.0)), id="exp_pbn_odds_thresh")

                with Collapsible(title="5. Whale Shield Protection", id="exp_coll_5", classes="exp_section"):
                    yield Static("Final-second protection. Blocks trades if bid is too close to 50¢.", classes="exp_sec_desc")
                    with Horizontal(classes="exp_row"):
                        yield Label("Shield Time (T- s):")
                        yield Input(placeholder="45", value=str(self.s.get("shield_time", 45)), id="exp_shield_time")
                        yield Label("Shield Reach (¢):")
                        yield Input(placeholder="5", value=str(self.s.get("shield_reach", 5)), id="exp_shield_reach")

                with Collapsible(title="6. Custom Exits (optional)", id="exp_coll_6", classes="exp_section"):
                    with Horizontal(classes="exp_row"):
                        yield Label("Custom TP (¢):")
                        tp_val = str(getattr(self.mom, "custom_tp", "")) if self.mom and getattr(self.mom, "custom_tp", None) else ""
                        yield Input(placeholder="e.g. 90", value=tp_val, id="exp_custom_tp")
                        yield Label("Custom SL (¢):")
                        sl_val = str(getattr(self.mom, "custom_sl", "")) if self.mom and getattr(self.mom, "custom_sl", None) else ""
                        yield Input(placeholder="e.g. 40", value=sl_val, id="exp_custom_sl")

                with Collapsible(title="7. Simulation & Diagnostics", id="exp_coll_7", classes="exp_section"):
                    yield Static("Manually trigger a PBN calculation using current live data.", classes="exp_sec_desc")
                    with Vertical(id="mom_test_container"):
                        yield Button("🚀 RUN LIVE PBN TEST", id="btn_mom_test", variant="error")
                        yield Static("Ready to simulate PBN analysis...", id="lbl_mom_test_status")

                with Vertical(id="exp_preview_box"):
                    yield Static("", id="exp_preview")
                
                with Horizontal(id="modal_footer"):
                    yield Button("SAVE & CLOSE", id="btn_exp_save", variant="primary")

    def on_mount(self):
        self.styles.align = ("center", "middle")
        c = self.query_one("#modal_container")
        c.styles.background = "#1a1a1a"
        c.styles.border = ("thick", "#ffaa00")
        c.styles.padding = (0, 2)
        c.styles.width = 72
        c.styles.height = "auto"
        c.styles.max_height = "90vh"
        c.styles.overflow_y = "auto"
        c.styles.align = ("center", "middle")
        
        self.query_one("#modal_title").styles.text_align = "center"
        self.query_one("#modal_title").styles.margin = (0, 0, 0, 0)
        self.query_one("#modal_title").styles.color = "#ffaa00"
        try:
            sub = self.query_one("#modal_subtitle")
            sub.styles.text_align = "center"
            sub.styles.color = "#555555"
            sub.styles.margin = (0, 0, 1, 0)
        except: pass
        
        payload = self.query_one("#modal_expert_payload")
        payload.styles.align = ("center", "middle")
        payload.styles.height = "auto"

        prow = self.query_one("#exp_preset_row")
        prow.styles.height = 3
        prow.styles.align = ("center", "middle")
        prow.styles.margin = (0, 0, 1, 0)
        prow.styles.border = ("ascii", "#444444")
        for b in prow.query(Button):
            b.styles.min_width = 16
            b.styles.height = 1
            b.styles.margin = (0, 1)

        for sec in self.query(".exp_section"):
            sec.styles.margin = (0, 0, 1, 0)
            sec.styles.height = "auto"
            sec.styles.width = "100%"
            # Make the collapsible headers look like the old titles
            sec.styles.background = "#1a1a1a"

        for desc in self.query(".exp_sec_desc"):
            desc.styles.color = "#555555"
            desc.styles.width = "100%"
            desc.styles.text_align = "left"

        for row in self.query(".exp_row"):
            row.styles.height = "auto"
            row.styles.align = ("center", "middle")
            row.styles.width = "100%"

        for inp in self.query(Input):
            inp.styles.width = 8
            inp.styles.margin = (0, 1, 0, 0)
        
        for cb in self.query(Checkbox):
            cb.styles.width = 25
            cb.styles.margin = (0, 0)
        
        prev_box = self.query_one("#exp_preview_box")
        prev_box.styles.background = "#002233"
        prev_box.styles.border = ("solid", "#0088ff")
        prev_box.styles.padding = (0, 1)
        prev_box.styles.margin = (0, 0, 1, 0)
        prev_box.styles.height = 3
        prev_box.styles.align = ("center", "middle")

        prev = self.query_one("#exp_preview")
        prev.styles.text_align = "center"
        prev.styles.color = "#aaaaaa"
        prev.styles.width = "100%"
        
        footer = self.query_one("#modal_footer")
        footer.styles.height = 3
        footer.styles.margin = (1, 0, 0, 0)
        footer.styles.align = ("center", "middle")

        save_btn = self.query_one("#btn_exp_save")
        save_btn.styles.width = 25

        test_cont = self.query_one("#mom_test_container")
        test_cont.styles.border = ("double", "#ff0000")
        test_cont.styles.margin = (1, 0)
        test_cont.styles.padding = (0, 1)
        test_cont.styles.align = ("center", "middle")
        
        self.query_one("#btn_mom_test").styles.width = "100%"
        self.query_one("#lbl_mom_test_status").styles.text_align = "center"
        self.query_one("#lbl_mom_test_status").styles.color = "#aaaaaa"
        self.query_one("#lbl_mom_test_status").styles.margin = (0, 0)

        self.set_interval(1.0, self._update_preview)

    @on(Button.Pressed, "#btn_mom_test")
    def _on_mom_test(self):
        if not self.main_app or not self.mom: return
        
        # Manually run Momentum analysis logic
        md = self.main_app.market_data
        context = {
            "elapsed": 285, # Simulate PBN window
            "up_ask": md.get("up_price", 0.5),
            "down_ask": md.get("down_price", 0.5),
            "up_bid": md.get("up_bid", 0.5),
            "down_bid": md.get("down_bid", 0.5),
            "btc_price": md.get("btc_price", 0),
            "btc_open": md.get("btc_open", 0),
            "btc_dyn_rng": md.get("btc_dyn_rng", 0),
            "rsi_1m": getattr(self.main_app.market_data_manager, "rsi_1m", 50),
            "atr_5m": getattr(self.main_app.market_data_manager, "atr_5m", 0),
            "trend_1h": md.get("trend_1h", "NEUTRAL")
        }
        
        # Temporarily enable PBN mode in scanner for the test
        orig_buy_mode = self.main_app.mom_buy_mode
        self.main_app.mom_buy_mode = "PRE"
        orig_scanner_buy_mode = self.mom.buy_mode
        self.mom.buy_mode = "PRE"
        
        # Reset scanner triggers for the test
        self.mom.pre_buy_triggered = False
        self.mom.triggered_signal = None
        
        res = self.mom.get_signal(context)
        analysis = self.mom.pbn_analysis
        
        # Restore mode
        self.main_app.mom_buy_mode = orig_buy_mode
        self.mom.buy_mode = orig_scanner_buy_mode
        
        if analysis:
            side = analysis.get("decision", "SKIP")
            conf = analysis.get("confidence", "NONE")
            score = analysis.get("net_score", 0)
            reason = analysis.get("reason", "")
            
            color = "green" if side == "UP" else "red" if side == "DOWN" else "yellow"
            status_text = f"[bold {color}]TEST RESULT:[/] {side} ({conf}) | Score: {score:+d}\n[dim]{reason}[/]"
            self.query_one("#lbl_mom_test_status").update(status_text)
            
            # Also log to main console for permanence
            self.main_app.log_msg(f"[bold cyan]🧪 MOM PBN TEST RUN:[/]\n  Result: {side} | Score: {score:+d}\n  Reason: {reason}", level="ADMIN")
        else:
            self.query_one("#lbl_mom_test_status").update("[bold red]ERROR:[/] Analysis failed to generate.")

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

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn_preset_def":
            self.query_one("#exp_atr_low").value = "20"
            self.query_one("#exp_atr_high").value = "40"
            self.query_one("#exp_off_stable").value = "-5"
            self.query_one("#exp_off_chaos").value = "10"
            self.query_one("#exp_over_stn").value = True
            self.query_one("#exp_over_pbn").value = False
            self.query_one("#exp_atr_floor").value = "25"
            self.query_one("#exp_trend_penalty").value = "2"
            self.query_one("#exp_decisive_diff").value = "2"
            self.query_one("#exp_pbn_odds_enabled").value = False
            self.query_one("#exp_pbn_odds_thresh").value = "2.0"
            self.main_app.log_msg("[bold cyan]UI Presets:[/] Loaded [DEFAULT] MOM profile.")
        elif bid == "btn_preset_vol":
            self.query_one("#exp_atr_low").value = "25"
            self.query_one("#exp_atr_high").value = "120"
            self.query_one("#exp_off_stable").value = "-5"
            self.query_one("#exp_off_chaos").value = "25"
            self.query_one("#exp_over_stn").value = True
            self.query_one("#exp_over_pbn").value = False
            self.query_one("#exp_atr_floor").value = "40"
            self.query_one("#exp_trend_penalty").value = "4"
            self.query_one("#exp_decisive_diff").value = "3"
            self.main_app.log_msg("[bold gold3]UI Presets:[/] Loaded [VOL SHIELD] MOM profile.")
        elif bid == "btn_preset_omega":
            # OMEGA / ULTRA PRE
            self.query_one("#exp_atr_low").value = "30"
            self.query_one("#exp_atr_high").value = "120"
            self.query_one("#exp_off_stable").value = "-5"
            self.query_one("#exp_off_chaos").value = "25"
            self.query_one("#exp_over_stn").value = True
            self.query_one("#exp_over_pbn").value = False 
            self.query_one("#exp_atr_floor").value = "40"
            self.query_one("#exp_trend_penalty").value = "5"
            self.query_one("#exp_decisive_diff").value = "3"
            
            # Force Buy Mode to PRE in main app and sync UI
            if self.main_app:
                self.main_app.mom_buy_mode = "PRE"
                
                # Find the parent AlgoInfoModal if it's open to update its checkboxes
                for screen in self.main_app.screen_stack:
                    if hasattr(screen, "algo_id") and getattr(screen, "algo_id") == "MOM":
                        try:
                            screen.query_one("#cb_mom_std").value = False
                            screen.query_one("#cb_mom_pre").value = True
                            screen.query_one("#cb_mom_hybrid").value = False
                            screen.query_one("#cb_mom_adv").value = False
                            screen.query_one("#btn_mom_adv").disabled = True
                        except: pass
                
                self.main_app.log_msg("[bold red]UI Presets:[/] 🔥 Loaded [ULTRA PRE] (OMEGA) profile. Buy Mode set to PRE.")
                
        elif bid == "btn_exp_save":
            self.save_and_close()

    def save_and_close(self):
        try:
            self.s["atr_low"] = int(self.query_one("#exp_atr_low").value)
            self.s["atr_high"] = int(self.query_one("#exp_atr_high").value)
            self.s["stable_offset"] = int(self.query_one("#exp_off_stable").value)
            self.s["chaos_offset"] = int(self.query_one("#exp_off_chaos").value)
            self.s["auto_stn_chaos"] = self.query_one("#exp_over_stn").value
            self.s["auto_pbn_stable"] = self.query_one("#exp_over_pbn").value
        except: pass
        try:
            self.s["atr_floor"] = float(self.query_one("#exp_atr_floor").value)
            self.s["trend_penalty"] = float(self.query_one("#exp_trend_penalty").value) / 100.0
            self.s["decisive_diff"] = float(self.query_one("#exp_decisive_diff").value) / 100.0
            self.s["shield_time"] = int(self.query_one("#exp_shield_time").value)
            self.s["shield_reach"] = int(self.query_one("#exp_shield_reach").value)
            self.s["pbn_odds_enabled"] = self.query_one("#exp_pbn_odds_enabled").value
            self.s["pbn_odds_thresh"] = float(self.query_one("#exp_pbn_odds_thresh").value)
        except: pass
        try:
            if self.mom:
                tp_val = self.query_one("#exp_custom_tp").value.strip()
                sl_val = self.query_one("#exp_custom_sl").value.strip()
                self.mom.custom_tp = int(tp_val) if tp_val.isdigit() else None
                self.mom.custom_sl = int(sl_val) if sl_val.isdigit() else None
                # Sync back to scanner adv_settings
                self.mom.adv_settings = self.s
        except: pass
        try:
            self.main_app.save_settings()
            s = self.s
            pbn = "✓" if s.get("auto_pbn_stable") else "✗"
            stn = "✓" if s.get("auto_stn_chaos") else "✗"
            tp = getattr(self.mom, "custom_tp", None) if self.mom else None
            sl = getattr(self.mom, "custom_sl", None) if self.mom else None
            tp_str = f"{tp}¢" if tp else "off"
            sl_str = f"{sl}¢" if sl else "off"
            self.main_app.log_msg(f"[bold #ffaa00]⚙ {self.algo_id} ADV Settings Saved:[/]")
            self.main_app.log_msg(f"  [dim]• Tiers:[/] Stable<{s.get('atr_low')}$ Chaos>{s.get('atr_high')}$")
            self.main_app.log_msg(f"  [dim]• Offsets:[/] Stable{s.get('stable_offset'):+}¢ Chaos{s.get('chaos_offset'):+}¢")
            self.main_app.log_msg(f"  [dim]• Gates:[/] Floor={s.get('atr_floor')}$ Trnd={int(s.get('trend_penalty',0)*100)}¢ Ld={int(s.get('decisive_diff',0)*100)}¢")
            self.main_app.log_msg(f"  [dim]• Whale Shield:[/] T- {s.get('shield_time')}s Reach {s.get('shield_reach')}¢")
            self.main_app.log_msg(f"  [dim]• Overrides:[/] PBN(Stb)={pbn} STN(Chs)={stn}")
            self.main_app.log_msg(f"  [dim]• Exits:[/] TP={tp_str} SL={sl_str}")
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
        # BullFlag research logging removed
        pass
    
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


class ManualFreezeModal(ModalScreen):
    """A modal that appears when the user issues the freeze command."""
    BINDINGS = [] # Intentionally no escape binding to force user to click the button

    def __init__(self, main_app=None):
        super().__init__()
        self.main_app = main_app

    def compose(self) -> ComposeResult:
        with Vertical(id="frozen_container"):
            yield Static("MANUAL FREEZE ACTIVE", id="frozen_title")
            yield Static("Trading is currently paused.\nPress Resume to continue operations.", id="frozen_body")
            yield Button("RESUME TRADING", id="btn_frozen_resume", variant="success")

    def on_mount(self):
        c = self.query_one("#frozen_container")
        c.styles.background  = "#331111"
        c.styles.border      = ("heavy", "#ff4444")
        c.styles.padding     = (2, 4)
        c.styles.width       = 50
        c.styles.height      = "auto"
        c.styles.align       = ("center", "middle")

        t = self.query_one("#frozen_title")
        t.styles.text_align  = "center"
        t.styles.color       = "#ff4444"
        t.styles.text_style  = "bold"
        t.styles.margin      = (0, 0, 2, 0)
        t.styles.width       = "100%"

        b = self.query_one("#frozen_body")
        b.styles.text_align  = "center"
        b.styles.color       = "white"
        b.styles.margin      = (0, 0, 2, 0)
        b.styles.width       = "100%"

        btn = self.query_one("#btn_frozen_resume")
        btn.styles.width = "70%"
        btn.styles.align = ("center", "middle")
        btn.styles.margin = (1, 0, 0, 0)


        self.styles.align = ("center", "middle")
        self.styles.background = "rgba(0,0,0,0.85)"

    @on(Button.Pressed, "#btn_frozen_resume")
    def dismiss_modal(self):
        if self.main_app:
            self.main_app.log_msg("[bold green]Admin Command:[/] Manual Freeze LIFTED. Trading Resumed.")
            self.main_app.halted = False
        self.dismiss()

class CommandHelpModal(ModalScreen):
    """A modal that displays available admin commands."""
    BINDINGS = [("escape", "dismiss", "Dismiss")]

    def compose(self) -> ComposeResult:
        with Vertical(id="cmd_help_container"):
            yield Static("AVAILABLE COMMANDS", id="cmd_help_title")
            
            help_text = (
                "[bold cyan]?            [/] Show this help menu\n"
                "[bold cyan]analyze-pre  [/] Analyze pre-buy conditions and market sentiment\n"
                "[bold cyan]/hide SCAN,STATS[/] Hide specific log categories from console\n"
                "[bold cyan]/only RSLT,EXEC[/] Show ONLY these categories in console\n"
                "[bold cyan]/show all    [/] Disable all log filters (Show everything)\n"
                "[bold cyan]freeze=true  [/] Pause all trading immediately\n"
                "[bold cyan]risk_pct=0.10[/] Set bet size to 10% of risk bankroll\n"
                "[bold cyan]lo=false     [/] Cancel mid-window lockout\n"
                "[bold cyan]sl+ / sl-    [/] Toggle SL+ Recovery Mode\n"
                "[bold cyan]mom: key=val [/] Update MOM/MM2 advanced settings\n"
            )
            yield Static(help_text, id="cmd_help_body")
            yield Button("CLOSE (ESC)", id="btn_cmd_help_close", variant="primary")

    def on_mount(self):
        c = self.query_one("#cmd_help_container")
        c.styles.background  = "#222233"
        c.styles.border      = ("heavy", "cyan")
        c.styles.padding     = (2, 4)
        c.styles.width       = 60
        c.styles.height      = "auto"
        c.styles.align       = ("center", "middle")

        t = self.query_one("#cmd_help_title")
        t.styles.text_align  = "center"
        t.styles.color       = "cyan"
        t.styles.text_style  = "bold"
        t.styles.margin      = (0, 0, 1, 0)
        t.styles.width       = "100%"

        b = self.query_one("#cmd_help_body")
        b.styles.color       = "white"
        b.styles.margin      = (0, 0, 2, 0)
        b.styles.width       = "100%"

        btn = self.query_one("#btn_cmd_help_close")
        btn.styles.width = "50%"
        btn.styles.align = ("center", "middle")

        self.styles.align = ("center", "middle")
        self.styles.background = "rgba(0,0,0,0.85)"

    def action_dismiss(self):
        self.dismiss_modal()

    @on(Button.Pressed, "#btn_cmd_help_close")
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
                    # Research logging removed
                    pass
            
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
        c.styles.max_height = "90vh"
        c.styles.align = ("center", "middle")
        c.styles.overflow_y = "auto"
        
        # Scrollable settings area
        sa = self.query_one("#bf_scroll_area")
        sa.styles.height = "auto"
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
    
    def action_dismiss(self):
        self.action_apply()

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
        
        # Research logging checkbox was removed, set to False by default
        research_enabled = False
        
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


class CCOExpertModal(ModalScreen):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.s = main_app.scanners.get('CoiledCobra')

    def compose(self) -> ComposeResult:
        with Container(id="dialog_cco"):
            yield Label("Coiled Cobra Expert Settings", id="dialog_cco_title", classes="dialog_title")
            yield Label("Fine-tune volatility detection & memory", classes="dialog_subtitle")

            with Container(id="cco_form_area"):
                with Horizontal(classes="cco_row"):
                    yield Label("Maximum Coil Threshold (Pct):", classes="cco_lbl")
                    yield Input(
                        value=str(int(self.s.coil_threshold_pct * 100)) if self.s else "25",
                        id="cco_thresh", classes="cco_inp"
                    )
                with Horizontal(classes="cco_row"):
                    yield Label("Samples for Valid History:", classes="cco_lbl")
                    yield Input(
                        value=str(self.s.coil_lookback_history) if self.s else "60",
                        id="cco_hist", classes="cco_inp"
                    )
                with Horizontal(classes="cco_row"):
                    yield Label("Seconds to Remember Coil:", classes="cco_lbl")
                    yield Input(
                        value=str(self.s.coil_lookback_recent) if self.s else "10",
                        id="cco_rec", classes="cco_inp"
                    )
                with Horizontal(classes="cco_row"):
                    yield Label("Custom TP (¢, Opt.):", classes="cco_lbl")
                    tp_val = str(getattr(self.s, "custom_tp", "")) if self.s and getattr(self.s, "custom_tp", None) else ""
                    yield Input(placeholder="90", value=tp_val, id="cco_custom_tp", classes="cco_inp")
                with Horizontal(classes="cco_row"):
                    yield Label("Custom SL (¢, Opt.):", classes="cco_lbl")
                    sl_val = str(getattr(self.s, "custom_sl", "")) if self.s and getattr(self.s, "custom_sl", None) else ""
                    yield Input(placeholder="40", value=sl_val, id="cco_custom_sl", classes="cco_inp")
            
            with Horizontal(id="dialog_cco_buttons"):
                yield Button("Reset", id="btn_cco_reset", variant="warning")
                yield Button("Apply & Save", id="btn_cco_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_cco")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "skyblue")
        d.styles.padding = (0, 1)
        d.styles.width = 44
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_cco_title").styles.text_align = "center"
        self.query_one("#dialog_cco_title").styles.color = "skyblue"
        self.query_one("#dialog_cco_title").styles.text_style = "bold"
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 1, 0)
        
        form = self.query_one("#cco_form_area")
        form.styles.width = "100%"
        form.styles.height = "auto"
        form.styles.layout = "vertical"
        form.styles.align = ("center", "top")
        
        for row in self.query(".cco_row"):
            row.styles.height = 1
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 0)
            row.styles.padding = (0, 0, 0, 0)
            
        for lbl in self.query(".cco_lbl"):
            lbl.styles.width = "3fr"
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".cco_inp"):
            inp.styles.width = 6
            inp.styles.height = 1
            inp.styles.margin = (0, 0, 0, 0)
            inp.styles.padding = (0, 0, 0, 0)
            
        row = self.query_one("#dialog_cco_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (1, 0, 0, 0)
        row.styles.height = 1

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_cco_reset")
    def _reset_settings(self):
        self.query_one("#cco_thresh").value = "25"
        self.query_one("#cco_hist").value = "60"
        self.query_one("#cco_rec").value = "10"
        self.query_one("#cco_custom_tp").value = ""
        self.query_one("#cco_custom_sl").value = ""

    @on(Button.Pressed, "#btn_cco_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.coil_threshold_pct = int(self.query_one("#cco_thresh").value) / 100.0
                self.s.coil_lookback_history = int(self.query_one("#cco_hist").value)
                self.s.coil_lookback_recent = int(self.query_one("#cco_rec").value)
                
                tp_val = self.query_one("#cco_custom_tp").value.strip()
                sl_val = self.query_one("#cco_custom_sl").value.strip()
                self.s.custom_tp = int(tp_val) if tp_val.isdigit() else None
                self.s.custom_sl = int(sl_val) if sl_val.isdigit() else None
                
            if self.main_app:
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ CCO Config Updated | Thresh: {int(self.s.coil_threshold_pct*100)}% | Hist: {self.s.coil_lookback_history}s | Mem: {self.s.coil_lookback_recent}s", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving CCO: {e}", level="ERROR")
            

class GRISettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app, scanner_obj):
        super().__init__()
        self.main_app = main_app
        self.s = scanner_obj
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_gri"):
            yield Label("GrindSnap Configuration", id="dialog_gri_title")
            yield Label("Tune grind and snap ratios.", classes="dialog_subtitle")
            
            with Vertical(id="gri_form_area"):
                with Horizontal(classes="gri_row"):
                    yield Label("Grind Duration (s):", classes="gri_lbl")
                    val = str(getattr(self.s, "grind_duration", 100)) if self.s else "100"
                    yield Input(placeholder="100", value=val, id="gri_grind_dur", classes="gri_inp")
                with Horizontal(classes="gri_row"):
                    yield Label("Snap Duration (s):", classes="gri_lbl")
                    val = str(getattr(self.s, "snap_duration", 20)) if self.s else "20"
                    yield Input(placeholder="20", value=val, id="gri_snap_dur", classes="gri_inp")
                with Horizontal(classes="gri_row"):
                    yield Label("Min Grind Slope (%):", classes="gri_lbl")
                    val = str(getattr(self.s, "min_slope_pct", 0.1)) if self.s else "0.1"
                    yield Input(placeholder="0.1", value=val, id="gri_min_slope", classes="gri_inp")
                with Horizontal(classes="gri_row"):
                    yield Label("Reversal Ratio:", classes="gri_lbl")
                    val = str(getattr(self.s, "reversal_ratio", 0.60)) if self.s else "0.60"
                    yield Input(placeholder="0.60", value=val, id="gri_rev_ratio", classes="gri_inp")
            
            with Horizontal(id="dialog_gri_buttons"):
                yield Button("Reset", id="btn_gri_reset", variant="warning")
                yield Button("Apply & Save", id="btn_gri_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_gri")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "magenta")
        d.styles.padding = (0, 1)
        d.styles.width = 44
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_gri_title").styles.text_align = "center"
        self.query_one("#dialog_gri_title").styles.color = "magenta"
        self.query_one("#dialog_gri_title").styles.text_style = "bold"
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 1, 0)
        
        form = self.query_one("#gri_form_area")
        form.styles.width = "100%"
        form.styles.height = "auto"
        form.styles.layout = "vertical"
        form.styles.align = ("center", "top")
        
        for row in self.query(".gri_row"):
            row.styles.height = 1
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 0)
            row.styles.padding = (0, 0, 0, 0)
            
        for lbl in self.query(".gri_lbl"):
            lbl.styles.width = "3fr"
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".gri_inp"):
            inp.styles.width = 6
            inp.styles.height = 1
            inp.styles.margin = (0, 0, 0, 0)
            inp.styles.padding = (0, 0, 0, 0)
            
        row = self.query_one("#dialog_gri_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (1, 0, 0, 0)
        row.styles.height = 1

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_gri_reset")
    def _reset_settings(self):
        self.query_one("#gri_grind_dur").value = "100"
        self.query_one("#gri_snap_dur").value = "20"
        self.query_one("#gri_min_slope").value = "0.1"
        self.query_one("#gri_rev_ratio").value = "0.60"

    @on(Button.Pressed, "#btn_gri_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.grind_duration = int(self.query_one("#gri_grind_dur").value)
                self.s.snap_duration = int(self.query_one("#gri_snap_dur").value)
                self.s.min_slope_pct = float(self.query_one("#gri_min_slope").value)
                self.s.reversal_ratio = float(self.query_one("#gri_rev_ratio").value)
                
            if self.main_app:
                # Save into gri_settings dictionary in main_app so it persists
                self.main_app.gri_settings = {
                    "grind_duration": getattr(self.s, "grind_duration", 100),
                    "snap_duration": getattr(self.s, "snap_duration", 20),
                    "min_slope_pct": getattr(self.s, "min_slope_pct", 0.1),
                    "reversal_ratio": getattr(self.s, "reversal_ratio", 0.60)
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ GRI Config Updated | Grind: {self.s.grind_duration}s | Snap: {self.s.snap_duration}s | MinSlope: {self.s.min_slope_pct}% | RevRatio: {self.s.reversal_ratio}", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving GRI: {e}", level="ERROR")
            
        self.dismiss()


class RSISettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app, scanner_obj):
        super().__init__()
        self.main_app = main_app
        self.s = scanner_obj
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_rsi"):
            yield Label("RSI Configuration", id="dialog_rsi_title")
            yield Label("Tune standard RSI parameters.", classes="dialog_subtitle")
            
            with Vertical(id="rsi_form_area"):
                with Horizontal(classes="rsi_row"):
                    yield Label("RSI Threshold:", classes="rsi_lbl")
                    val = str(getattr(self.s, "rsi_threshold", 20)) if self.s else "20"
                    yield Input(placeholder="20", value=val, id="rsi_rsi_threshold", classes="rsi_inp")
                with Horizontal(classes="rsi_row"):
                    yield Label("Min Time Rem (s):", classes="rsi_lbl")
                    val = str(getattr(self.s, "time_remaining_min", 80)) if self.s else "80"
                    yield Input(placeholder="80", value=val, id="rsi_time_remaining_min", classes="rsi_inp")
            
            with Horizontal(id="dialog_rsi_buttons"):
                yield Button("Reset", id="btn_rsi_reset", variant="warning")
                yield Button("Apply & Save", id="btn_rsi_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_rsi")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "magenta")
        d.styles.padding = (0, 1)
        d.styles.width = 44
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_rsi_title").styles.text_align = "center"
        self.query_one("#dialog_rsi_title").styles.color = "magenta"
        self.query_one("#dialog_rsi_title").styles.text_style = "bold"
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 1, 0)
        
        form = self.query_one("#rsi_form_area")
        form.styles.width = "100%"
        form.styles.height = "auto"
        form.styles.layout = "vertical"
        form.styles.align = ("center", "top")
        
        for row in self.query(".rsi_row"):
            row.styles.height = 1
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 0)
            row.styles.padding = (0, 0, 0, 0)
            
        for lbl in self.query(".rsi_lbl"):
            lbl.styles.width = "3fr"
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".rsi_inp"):
            inp.styles.width = 10
            inp.styles.height = 1
            inp.styles.margin = (0, 0, 0, 0)
            inp.styles.padding = (0, 0, 0, 0)
            
        row = self.query_one("#dialog_rsi_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (1, 0, 0, 0)
        row.styles.height = 1

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_rsi_reset")
    def _reset_settings(self):
        self.query_one("#rsi_rsi_threshold").value = "20"
        self.query_one("#rsi_time_remaining_min").value = "80"

    @on(Button.Pressed, "#btn_rsi_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.rsi_threshold = int(self.query_one("#rsi_rsi_threshold").value)
                self.s.time_remaining_min = int(self.query_one("#rsi_time_remaining_min").value)
                
            if self.main_app:
                # Save into app dict so it persists
                self.main_app.rsi_settings = {
                    "rsi_threshold": getattr(self.s, "rsi_threshold", 20),
                    "time_remaining_min": getattr(self.s, "time_remaining_min", 80),
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ RSI Config Updated", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving RSI: {e}", level="ERROR")
            
        self.dismiss()


class TRASettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app, scanner_obj):
        super().__init__()
        self.main_app = main_app
        self.s = scanner_obj
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_tra"):
            yield Label("TrapCandle Configuration", id="dialog_tra_title")
            yield Label("Tune TrapCandle fade parameters.", classes="dialog_subtitle")
            
            with Vertical(id="tra_form_area"):
                with Horizontal(classes="tra_row"):
                    yield Label("Start Move %:", classes="tra_lbl")
                    val = str(getattr(self.s, "start_move_pct", 0.002)) if self.s else "0.002"
                    yield Input(placeholder="0.002", value=val, id="tra_start_move_pct", classes="tra_inp")
                with Horizontal(classes="tra_row"):
                    yield Label("Retrace Ratio:", classes="tra_lbl")
                    val = str(getattr(self.s, "retrace_ratio", 0.35)) if self.s else "0.35"
                    yield Input(placeholder="0.35", value=val, id="tra_retrace_ratio", classes="tra_inp")
            
            with Horizontal(id="dialog_tra_buttons"):
                yield Button("Reset", id="btn_tra_reset", variant="warning")
                yield Button("Apply & Save", id="btn_tra_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_tra")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "magenta")
        d.styles.padding = (0, 1)
        d.styles.width = 44
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_tra_title").styles.text_align = "center"
        self.query_one("#dialog_tra_title").styles.color = "magenta"
        self.query_one("#dialog_tra_title").styles.text_style = "bold"
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 1, 0)
        
        form = self.query_one("#tra_form_area")
        form.styles.width = "100%"
        form.styles.height = "auto"
        form.styles.layout = "vertical"
        form.styles.align = ("center", "top")
        
        for row in self.query(".tra_row"):
            row.styles.height = 1
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 0)
            row.styles.padding = (0, 0, 0, 0)
            
        for lbl in self.query(".tra_lbl"):
            lbl.styles.width = "3fr"
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".tra_inp"):
            inp.styles.width = 10
            inp.styles.height = 1
            inp.styles.margin = (0, 0, 0, 0)
            inp.styles.padding = (0, 0, 0, 0)
            
        row = self.query_one("#dialog_tra_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (1, 0, 0, 0)
        row.styles.height = 1

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_tra_reset")
    def _reset_settings(self):
        self.query_one("#tra_start_move_pct").value = "0.002"
        self.query_one("#tra_retrace_ratio").value = "0.35"

    @on(Button.Pressed, "#btn_tra_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.start_move_pct = float(self.query_one("#tra_start_move_pct").value)
                self.s.retrace_ratio = float(self.query_one("#tra_retrace_ratio").value)
                
            if self.main_app:
                # Save into app dict so it persists
                self.main_app.tra_settings = {
                    "start_move_pct": getattr(self.s, "start_move_pct", 0.002),
                    "retrace_ratio": getattr(self.s, "retrace_ratio", 0.35),
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ TRA Config Updated", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving TRA: {e}", level="ERROR")
            
        self.dismiss()


class MIDSettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app, scanner_obj):
        super().__init__()
        self.main_app = main_app
        self.s = scanner_obj
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_mid"):
            yield Label("MidGame Configuration", id="dialog_mid_title")
            yield Label("Tune fail-to-rescue parameters.", classes="dialog_subtitle")
            
            with Vertical(id="mid_form_area"):
                with Horizontal(classes="mid_row"):
                    yield Label("Min Elapsed (s):", classes="mid_lbl")
                    val = str(getattr(self.s, "min_elapsed", 90)) if self.s else "90"
                    yield Input(placeholder="90", value=val, id="mid_min_elapsed", classes="mid_inp")
                with Horizontal(classes="mid_row"):
                    yield Label("Max Grn Ticks:", classes="mid_lbl")
                    val = str(getattr(self.s, "max_green_ticks", 25)) if self.s else "25"
                    yield Input(placeholder="25", value=val, id="mid_max_green_ticks", classes="mid_inp")
            
            with Horizontal(id="dialog_mid_buttons"):
                yield Button("Reset", id="btn_mid_reset", variant="warning")
                yield Button("Apply & Save", id="btn_mid_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_mid")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "magenta")
        d.styles.padding = (0, 1)
        d.styles.width = 44
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_mid_title").styles.text_align = "center"
        self.query_one("#dialog_mid_title").styles.color = "magenta"
        self.query_one("#dialog_mid_title").styles.text_style = "bold"
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 1, 0)
        
        form = self.query_one("#mid_form_area")
        form.styles.width = "100%"
        form.styles.height = "auto"
        form.styles.layout = "vertical"
        form.styles.align = ("center", "top")
        
        for row in self.query(".mid_row"):
            row.styles.height = 1
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 0)
            row.styles.padding = (0, 0, 0, 0)
            
        for lbl in self.query(".mid_lbl"):
            lbl.styles.width = "3fr"
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".mid_inp"):
            inp.styles.width = 10
            inp.styles.height = 1
            inp.styles.margin = (0, 0, 0, 0)
            inp.styles.padding = (0, 0, 0, 0)
            
        row = self.query_one("#dialog_mid_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (1, 0, 0, 0)
        row.styles.height = 1

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_mid_reset")
    def _reset_settings(self):
        self.query_one("#mid_min_elapsed").value = "90"
        self.query_one("#mid_max_green_ticks").value = "25"

    @on(Button.Pressed, "#btn_mid_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.min_elapsed = int(self.query_one("#mid_min_elapsed").value)
                self.s.max_green_ticks = int(self.query_one("#mid_max_green_ticks").value)
                
            if self.main_app:
                # Save into app dict so it persists
                self.main_app.mid_settings = {
                    "min_elapsed": getattr(self.s, "min_elapsed", 90),
                    "max_green_ticks": getattr(self.s, "max_green_ticks", 25),
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ MID Config Updated", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving MID: {e}", level="ERROR")
            
        self.dismiss()


class LATSettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app, scanner_obj):
        super().__init__()
        self.main_app = main_app
        self.s = scanner_obj
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_lat"):
            yield Label("LateReversal Configuration", id="dialog_lat_title")
            yield Label("Tune late green surge parameters.", classes="dialog_subtitle")
            
            with Vertical(id="lat_form_area"):
                with Horizontal(classes="lat_row"):
                    yield Label("Min Elapsed (s):", classes="lat_lbl")
                    val = str(getattr(self.s, "min_elapsed", 200)) if self.s else "200"
                    yield Input(placeholder="200", value=val, id="lat_min_elapsed", classes="lat_inp")
                with Horizontal(classes="lat_row"):
                    yield Label("Surge Pct:", classes="lat_lbl")
                    val = str(getattr(self.s, "surge_pct", 1.0003)) if self.s else "1.0003"
                    yield Input(placeholder="1.0003", value=val, id="lat_surge_pct", classes="lat_inp")
            
            with Horizontal(id="dialog_lat_buttons"):
                yield Button("Reset", id="btn_lat_reset", variant="warning")
                yield Button("Apply & Save", id="btn_lat_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_lat")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "magenta")
        d.styles.padding = (0, 1)
        d.styles.width = 44
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_lat_title").styles.text_align = "center"
        self.query_one("#dialog_lat_title").styles.color = "magenta"
        self.query_one("#dialog_lat_title").styles.text_style = "bold"
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 1, 0)
        
        form = self.query_one("#lat_form_area")
        form.styles.width = "100%"
        form.styles.height = "auto"
        form.styles.layout = "vertical"
        form.styles.align = ("center", "top")
        
        for row in self.query(".lat_row"):
            row.styles.height = 1
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 0)
            row.styles.padding = (0, 0, 0, 0)
            
        for lbl in self.query(".lat_lbl"):
            lbl.styles.width = "3fr"
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".lat_inp"):
            inp.styles.width = 10
            inp.styles.height = 1
            inp.styles.margin = (0, 0, 0, 0)
            inp.styles.padding = (0, 0, 0, 0)
            
        row = self.query_one("#dialog_lat_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (1, 0, 0, 0)
        row.styles.height = 1

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_lat_reset")
    def _reset_settings(self):
        self.query_one("#lat_min_elapsed").value = "200"
        self.query_one("#lat_surge_pct").value = "1.0003"

    @on(Button.Pressed, "#btn_lat_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.min_elapsed = int(self.query_one("#lat_min_elapsed").value)
                self.s.surge_pct = float(self.query_one("#lat_surge_pct").value)
                
            if self.main_app:
                # Save into app dict so it persists
                self.main_app.lat_settings = {
                    "min_elapsed": getattr(self.s, "min_elapsed", 200),
                    "surge_pct": getattr(self.s, "surge_pct", 1.0003),
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ LAT Config Updated", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving LAT: {e}", level="ERROR")
            
        self.dismiss()


class POSSettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app, scanner_obj):
        super().__init__()
        self.main_app = main_app
        self.s = scanner_obj
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_pos"):
            yield Label("PostPump Configuration", id="dialog_pos_title")
            yield Label("Tune post-pump reversion metrics.", classes="dialog_subtitle")
            
            with Vertical(id="pos_form_area"):
                with Horizontal(classes="pos_row"):
                    yield Label("Min Pump %:", classes="pos_lbl")
                    val = str(getattr(self.s, "min_pump_pct", 0.003)) if self.s else "0.003"
                    yield Input(placeholder="0.003", value=val, id="pos_min_pump_pct", classes="pos_inp")
                with Horizontal(classes="pos_row"):
                    yield Label("Rvs Depth Pct:", classes="pos_lbl")
                    val = str(getattr(self.s, "reversal_depth", 0.9985)) if self.s else "0.9985"
                    yield Input(placeholder="0.9985", value=val, id="pos_reversal_depth", classes="pos_inp")
            
            with Horizontal(id="dialog_pos_buttons"):
                yield Button("Reset", id="btn_pos_reset", variant="warning")
                yield Button("Apply & Save", id="btn_pos_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_pos")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "magenta")
        d.styles.padding = (0, 1)
        d.styles.width = 44
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_pos_title").styles.text_align = "center"
        self.query_one("#dialog_pos_title").styles.color = "magenta"
        self.query_one("#dialog_pos_title").styles.text_style = "bold"
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 1, 0)
        
        form = self.query_one("#pos_form_area")
        form.styles.width = "100%"
        form.styles.height = "auto"
        form.styles.layout = "vertical"
        form.styles.align = ("center", "top")
        
        for row in self.query(".pos_row"):
            row.styles.height = 1
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 0)
            row.styles.padding = (0, 0, 0, 0)
            
        for lbl in self.query(".pos_lbl"):
            lbl.styles.width = "3fr"
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".pos_inp"):
            inp.styles.width = 10
            inp.styles.height = 1
            inp.styles.margin = (0, 0, 0, 0)
            inp.styles.padding = (0, 0, 0, 0)
            
        row = self.query_one("#dialog_pos_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (1, 0, 0, 0)
        row.styles.height = 1

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_pos_reset")
    def _reset_settings(self):
        self.query_one("#pos_min_pump_pct").value = "0.003"
        self.query_one("#pos_reversal_depth").value = "0.9985"

    @on(Button.Pressed, "#btn_pos_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.min_pump_pct = float(self.query_one("#pos_min_pump_pct").value)
                self.s.reversal_depth = float(self.query_one("#pos_reversal_depth").value)
                
            if self.main_app:
                # Save into app dict so it persists
                self.main_app.pos_settings = {
                    "min_pump_pct": getattr(self.s, "min_pump_pct", 0.003),
                    "reversal_depth": getattr(self.s, "reversal_depth", 0.9985),
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ POS Config Updated", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving POS: {e}", level="ERROR")
            
        self.dismiss()


class STESettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app, scanner_obj):
        super().__init__()
        self.main_app = main_app
        self.s = scanner_obj
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_ste"):
            yield Label("StepClimber Configuration", id="dialog_ste_title")
            yield Label("Tune gradual climb logic.", classes="dialog_subtitle")
            
            with Vertical(id="ste_form_area"):
                with Horizontal(classes="ste_row"):
                    yield Label("Tick Count:", classes="ste_lbl")
                    val = str(getattr(self.s, "tick_count", 15)) if self.s else "15"
                    yield Input(placeholder="15", value=val, id="ste_tick_count", classes="ste_inp")
                with Horizontal(classes="ste_row"):
                    yield Label("Climb Pct:", classes="ste_lbl")
                    val = str(getattr(self.s, "climb_pct", 1.001)) if self.s else "1.001"
                    yield Input(placeholder="1.001", value=val, id="ste_climb_pct", classes="ste_inp")
            
            with Horizontal(id="dialog_ste_buttons"):
                yield Button("Reset", id="btn_ste_reset", variant="warning")
                yield Button("Apply & Save", id="btn_ste_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_ste")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "magenta")
        d.styles.padding = (0, 1)
        d.styles.width = 44
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_ste_title").styles.text_align = "center"
        self.query_one("#dialog_ste_title").styles.color = "magenta"
        self.query_one("#dialog_ste_title").styles.text_style = "bold"
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 1, 0)
        
        form = self.query_one("#ste_form_area")
        form.styles.width = "100%"
        form.styles.height = "auto"
        form.styles.layout = "vertical"
        form.styles.align = ("center", "top")
        
        for row in self.query(".ste_row"):
            row.styles.height = 1
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 0)
            row.styles.padding = (0, 0, 0, 0)
            
        for lbl in self.query(".ste_lbl"):
            lbl.styles.width = "3fr"
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".ste_inp"):
            inp.styles.width = 10
            inp.styles.height = 1
            inp.styles.margin = (0, 0, 0, 0)
            inp.styles.padding = (0, 0, 0, 0)
            
        row = self.query_one("#dialog_ste_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (1, 0, 0, 0)
        row.styles.height = 1

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_ste_reset")
    def _reset_settings(self):
        self.query_one("#ste_tick_count").value = "15"
        self.query_one("#ste_climb_pct").value = "1.001"

    @on(Button.Pressed, "#btn_ste_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.tick_count = int(self.query_one("#ste_tick_count").value)
                self.s.climb_pct = float(self.query_one("#ste_climb_pct").value)
                
            if self.main_app:
                # Save into app dict so it persists
                self.main_app.ste_settings = {
                    "tick_count": getattr(self.s, "tick_count", 15),
                    "climb_pct": getattr(self.s, "climb_pct", 1.001),
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ STE Config Updated", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving STE: {e}", level="ERROR")
            
        self.dismiss()


class SLISettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app, scanner_obj):
        super().__init__()
        self.main_app = main_app
        self.s = scanner_obj
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_sli"):
            yield Label("Slingshot Configuration", id="dialog_sli_title")
            yield Label("Tune moving average slingshot.", classes="dialog_subtitle")
            
            with Vertical(id="sli_form_area"):
                with Horizontal(classes="sli_row"):
                    yield Label("MA Period:", classes="sli_lbl")
                    val = str(getattr(self.s, "ma_period", 15)) if self.s else "15"
                    yield Input(placeholder="15", value=val, id="sli_ma_period", classes="sli_inp")
            
            with Horizontal(id="dialog_sli_buttons"):
                yield Button("Reset", id="btn_sli_reset", variant="warning")
                yield Button("Apply & Save", id="btn_sli_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_sli")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "magenta")
        d.styles.padding = (0, 1)
        d.styles.width = 44
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_sli_title").styles.text_align = "center"
        self.query_one("#dialog_sli_title").styles.color = "magenta"
        self.query_one("#dialog_sli_title").styles.text_style = "bold"
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 1, 0)
        
        form = self.query_one("#sli_form_area")
        form.styles.width = "100%"
        form.styles.height = "auto"
        form.styles.layout = "vertical"
        form.styles.align = ("center", "top")
        
        for row in self.query(".sli_row"):
            row.styles.height = 1
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 0)
            row.styles.padding = (0, 0, 0, 0)
            
        for lbl in self.query(".sli_lbl"):
            lbl.styles.width = "3fr"
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".sli_inp"):
            inp.styles.width = 10
            inp.styles.height = 1
            inp.styles.margin = (0, 0, 0, 0)
            inp.styles.padding = (0, 0, 0, 0)
            
        row = self.query_one("#dialog_sli_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (1, 0, 0, 0)
        row.styles.height = 1

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_sli_reset")
    def _reset_settings(self):
        self.query_one("#sli_ma_period").value = "15"

    @on(Button.Pressed, "#btn_sli_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.ma_period = int(self.query_one("#sli_ma_period").value)
                
            if self.main_app:
                # Save into app dict so it persists
                self.main_app.sli_settings = {
                    "ma_period": getattr(self.s, "ma_period", 15),
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ SLI Config Updated", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving SLI: {e}", level="ERROR")
            
        self.dismiss()


class MINSettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app, scanner_obj):
        super().__init__()
        self.main_app = main_app
        self.s = scanner_obj
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_min"):
            yield Label("MinOne Configuration", id="dialog_min_title")
            yield Label("Tune Liar's Wick thresholds.", classes="dialog_subtitle")
            
            with Vertical(id="min_form_area"):
                with Horizontal(classes="min_row"):
                    yield Label("Wick Mult:", classes="min_lbl")
                    val = str(getattr(self.s, "wick_multiplier", 1.5)) if self.s else "1.5"
                    yield Input(placeholder="1.5", value=val, id="min_wick_multiplier", classes="min_inp")
            
            with Horizontal(id="dialog_min_buttons"):
                yield Button("Reset", id="btn_min_reset", variant="warning")
                yield Button("Apply & Save", id="btn_min_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_min")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "magenta")
        d.styles.padding = (0, 1)
        d.styles.width = 44
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_min_title").styles.text_align = "center"
        self.query_one("#dialog_min_title").styles.color = "magenta"
        self.query_one("#dialog_min_title").styles.text_style = "bold"
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 1, 0)
        
        form = self.query_one("#min_form_area")
        form.styles.width = "100%"
        form.styles.height = "auto"
        form.styles.layout = "vertical"
        form.styles.align = ("center", "top")
        
        for row in self.query(".min_row"):
            row.styles.height = 1
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 0)
            row.styles.padding = (0, 0, 0, 0)
            
        for lbl in self.query(".min_lbl"):
            lbl.styles.width = "3fr"
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".min_inp"):
            inp.styles.width = 10
            inp.styles.height = 1
            inp.styles.margin = (0, 0, 0, 0)
            inp.styles.padding = (0, 0, 0, 0)
            
        row = self.query_one("#dialog_min_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (1, 0, 0, 0)
        row.styles.height = 1

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_min_reset")
    def _reset_settings(self):
        self.query_one("#min_wick_multiplier").value = "1.5"

    @on(Button.Pressed, "#btn_min_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.wick_multiplier = float(self.query_one("#min_wick_multiplier").value)
                
            if self.main_app:
                # Save into app dict so it persists
                self.main_app.min_settings = {
                    "wick_multiplier": getattr(self.s, "wick_multiplier", 1.5),
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ MIN Config Updated", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving MIN: {e}", level="ERROR")
            
        self.dismiss()


class LIQSettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app, scanner_obj):
        super().__init__()
        self.main_app = main_app
        self.s = scanner_obj
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_liq"):
            yield Label("LiquidityVacuum Configuration", id="dialog_liq_title")
            yield Label("Tune liquidity sweep breaks.", classes="dialog_subtitle")
            
            with Vertical(id="liq_form_area"):
                with Horizontal(classes="liq_row"):
                    yield Label("Brk Strct Pct:", classes="liq_lbl")
                    val = str(getattr(self.s, "break_structure_pct", 1.0001)) if self.s else "1.0001"
                    yield Input(placeholder="1.0001", value=val, id="liq_break_structure_pct", classes="liq_inp")
            
            with Horizontal(id="dialog_liq_buttons"):
                yield Button("Reset", id="btn_liq_reset", variant="warning")
                yield Button("Apply & Save", id="btn_liq_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_liq")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "magenta")
        d.styles.padding = (0, 1)
        d.styles.width = 44
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_liq_title").styles.text_align = "center"
        self.query_one("#dialog_liq_title").styles.color = "magenta"
        self.query_one("#dialog_liq_title").styles.text_style = "bold"
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 1, 0)
        
        form = self.query_one("#liq_form_area")
        form.styles.width = "100%"
        form.styles.height = "auto"
        form.styles.layout = "vertical"
        form.styles.align = ("center", "top")
        
        for row in self.query(".liq_row"):
            row.styles.height = 1
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 0)
            row.styles.padding = (0, 0, 0, 0)
            
        for lbl in self.query(".liq_lbl"):
            lbl.styles.width = "3fr"
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".liq_inp"):
            inp.styles.width = 10
            inp.styles.height = 1
            inp.styles.margin = (0, 0, 0, 0)
            inp.styles.padding = (0, 0, 0, 0)
            
        row = self.query_one("#dialog_liq_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (1, 0, 0, 0)
        row.styles.height = 1

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_liq_reset")
    def _reset_settings(self):
        self.query_one("#liq_break_structure_pct").value = "1.0001"

    @on(Button.Pressed, "#btn_liq_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.break_structure_pct = float(self.query_one("#liq_break_structure_pct").value)
                
            if self.main_app:
                # Save into app dict so it persists
                self.main_app.liq_settings = {
                    "break_structure_pct": getattr(self.s, "break_structure_pct", 1.0001),
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ LIQ Config Updated", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving LIQ: {e}", level="ERROR")
            
        self.dismiss()


class COBSettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app, scanner_obj):
        super().__init__()
        self.main_app = main_app
        self.s = scanner_obj
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_cob"):
            yield Label("Cobra Configuration", id="dialog_cob_title")
            yield Label("Tune explosive breakout devs.", classes="dialog_subtitle")
            
            with Vertical(id="cob_form_area"):
                with Horizontal(classes="cob_row"):
                    yield Label("MA Period:", classes="cob_lbl")
                    val = str(getattr(self.s, "ma_period", 15)) if self.s else "15"
                    yield Input(placeholder="15", value=val, id="cob_ma_period", classes="cob_inp")
                with Horizontal(classes="cob_row"):
                    yield Label("Std Dev Mult:", classes="cob_lbl")
                    val = str(getattr(self.s, "std_dev_mult", 1.5)) if self.s else "1.5"
                    yield Input(placeholder="1.5", value=val, id="cob_std_dev_mult", classes="cob_inp")
            
            with Horizontal(id="dialog_cob_buttons"):
                yield Button("Reset", id="btn_cob_reset", variant="warning")
                yield Button("Apply & Save", id="btn_cob_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_cob")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "magenta")
        d.styles.padding = (0, 1)
        d.styles.width = 44
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_cob_title").styles.text_align = "center"
        self.query_one("#dialog_cob_title").styles.color = "magenta"
        self.query_one("#dialog_cob_title").styles.text_style = "bold"
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 1, 0)
        
        form = self.query_one("#cob_form_area")
        form.styles.width = "100%"
        form.styles.height = "auto"
        form.styles.layout = "vertical"
        form.styles.align = ("center", "top")
        
        for row in self.query(".cob_row"):
            row.styles.height = 1
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 0)
            row.styles.padding = (0, 0, 0, 0)
            
        for lbl in self.query(".cob_lbl"):
            lbl.styles.width = "3fr"
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".cob_inp"):
            inp.styles.width = 10
            inp.styles.height = 1
            inp.styles.margin = (0, 0, 0, 0)
            inp.styles.padding = (0, 0, 0, 0)
            
        row = self.query_one("#dialog_cob_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (1, 0, 0, 0)
        row.styles.height = 1

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_cob_reset")
    def _reset_settings(self):
        self.query_one("#cob_ma_period").value = "15"
        self.query_one("#cob_std_dev_mult").value = "1.5"

    @on(Button.Pressed, "#btn_cob_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.ma_period = int(self.query_one("#cob_ma_period").value)
                self.s.std_dev_mult = float(self.query_one("#cob_std_dev_mult").value)
                
            if self.main_app:
                # Save into app dict so it persists
                self.main_app.cob_settings = {
                    "ma_period": getattr(self.s, "ma_period", 15),
                    "std_dev_mult": getattr(self.s, "std_dev_mult", 1.5),
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ COB Config Updated", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving COB: {e}", level="ERROR")
            
        self.dismiss()


class MESSettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app, scanner_obj):
        super().__init__()
        self.main_app = main_app
        self.s = scanner_obj
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_mes"):
            yield Label("MesaCollapse Configuration", id="dialog_mes_title")
            yield Label("Tune pump and collapse logic.", classes="dialog_subtitle")
            
            with Vertical(id="mes_form_area"):
                with Horizontal(classes="mes_row"):
                    yield Label("Pump Thresh:", classes="mes_lbl")
                    val = str(getattr(self.s, "pump_threshold", 0.001)) if self.s else "0.001"
                    yield Input(placeholder="0.001", value=val, id="mes_pump_threshold", classes="mes_inp")
                with Horizontal(classes="mes_row"):
                    yield Label("Cross Count:", classes="mes_lbl")
                    val = str(getattr(self.s, "cross_count", 2)) if self.s else "2"
                    yield Input(placeholder="2", value=val, id="mes_cross_count", classes="mes_inp")
            
            with Horizontal(id="dialog_mes_buttons"):
                yield Button("Reset", id="btn_mes_reset", variant="warning")
                yield Button("Apply & Save", id="btn_mes_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_mes")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "magenta")
        d.styles.padding = (0, 1)
        d.styles.width = 44
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_mes_title").styles.text_align = "center"
        self.query_one("#dialog_mes_title").styles.color = "magenta"
        self.query_one("#dialog_mes_title").styles.text_style = "bold"
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 1, 0)
        
        form = self.query_one("#mes_form_area")
        form.styles.width = "100%"
        form.styles.height = "auto"
        form.styles.layout = "vertical"
        form.styles.align = ("center", "top")
        
        for row in self.query(".mes_row"):
            row.styles.height = 1
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 0)
            row.styles.padding = (0, 0, 0, 0)
            
        for lbl in self.query(".mes_lbl"):
            lbl.styles.width = "3fr"
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".mes_inp"):
            inp.styles.width = 10
            inp.styles.height = 1
            inp.styles.margin = (0, 0, 0, 0)
            inp.styles.padding = (0, 0, 0, 0)
            
        row = self.query_one("#dialog_mes_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (1, 0, 0, 0)
        row.styles.height = 1

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_mes_reset")
    def _reset_settings(self):
        self.query_one("#mes_pump_threshold").value = "0.001"
        self.query_one("#mes_cross_count").value = "2"

    @on(Button.Pressed, "#btn_mes_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.pump_threshold = float(self.query_one("#mes_pump_threshold").value)
                self.s.cross_count = int(self.query_one("#mes_cross_count").value)
                
            if self.main_app:
                # Save into app dict so it persists
                self.main_app.mes_settings = {
                    "pump_threshold": getattr(self.s, "pump_threshold", 0.001),
                    "cross_count": getattr(self.s, "cross_count", 2),
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ MES Config Updated", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving MES: {e}", level="ERROR")
            
        self.dismiss()


class NPASettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app, scanner_obj):
        super().__init__()
        self.main_app = main_app
        self.s = scanner_obj
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_npa"):
            yield Label("N-Pattern Configuration", id="dialog_npa_title")
            yield Label("Tune impulse and retrace metrics.", classes="dialog_subtitle")
            
            with Vertical(id="npa_form_area"):
                with Horizontal(classes="npa_row"):
                    yield Label("Min Impulse:", classes="npa_lbl")
                    val = str(getattr(self.s, "min_impulse_size", 0.0003)) if self.s else "0.0003"
                    yield Input(placeholder="0.0003", value=val, id="npa_min_impulse_size", classes="npa_inp")
                with Horizontal(classes="npa_row"):
                    yield Label("Max Retrace:", classes="npa_lbl")
                    val = str(getattr(self.s, "max_retrace_depth", 0.85)) if self.s else "0.85"
                    yield Input(placeholder="0.85", value=val, id="npa_max_retrace_depth", classes="npa_inp")
            
            with Horizontal(id="dialog_npa_buttons"):
                yield Button("Reset", id="btn_npa_reset", variant="warning")
                yield Button("Apply & Save", id="btn_npa_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_npa")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "magenta")
        d.styles.padding = (0, 1)
        d.styles.width = 44
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_npa_title").styles.text_align = "center"
        self.query_one("#dialog_npa_title").styles.color = "magenta"
        self.query_one("#dialog_npa_title").styles.text_style = "bold"
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 1, 0)
        
        form = self.query_one("#npa_form_area")
        form.styles.width = "100%"
        form.styles.height = "auto"
        form.styles.layout = "vertical"
        form.styles.align = ("center", "top")
        
        for row in self.query(".npa_row"):
            row.styles.height = 1
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 0)
            row.styles.padding = (0, 0, 0, 0)
            
        for lbl in self.query(".npa_lbl"):
            lbl.styles.width = "3fr"
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".npa_inp"):
            inp.styles.width = 10
            inp.styles.height = 1
            inp.styles.margin = (0, 0, 0, 0)
            inp.styles.padding = (0, 0, 0, 0)
            
        row = self.query_one("#dialog_npa_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (1, 0, 0, 0)
        row.styles.height = 1

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_npa_reset")
    def _reset_settings(self):
        self.query_one("#npa_min_impulse_size").value = "0.0003"
        self.query_one("#npa_max_retrace_depth").value = "0.85"

    @on(Button.Pressed, "#btn_npa_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.min_impulse_size = float(self.query_one("#npa_min_impulse_size").value)
                self.s.max_retrace_depth = float(self.query_one("#npa_max_retrace_depth").value)
                
            if self.main_app:
                # Save into app dict so it persists
                self.main_app.npa_settings = {
                    "min_impulse_size": getattr(self.s, "min_impulse_size", 0.0003),
                    "max_retrace_depth": getattr(self.s, "max_retrace_depth", 0.85),
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ NPA Config Updated", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving NPA: {e}", level="ERROR")
            
        self.dismiss()


class FAKSettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app, scanner_obj):
        super().__init__()
        self.main_app = main_app
        self.s = scanner_obj
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_fak"):
            yield Label("Fakeout Configuration", id="dialog_fak_title")
            yield Label("Tune rejection phase duration.", classes="dialog_subtitle")
            
            with Vertical(id="fak_form_area"):
                with Horizontal(classes="fak_row"):
                    yield Label("Phase 1 (s):", classes="fak_lbl")
                    val = str(getattr(self.s, "phase1_duration", 60)) if self.s else "60"
                    yield Input(placeholder="60", value=val, id="fak_phase1_duration", classes="fak_inp")
            
            with Horizontal(id="dialog_fak_buttons"):
                yield Button("Reset", id="btn_fak_reset", variant="warning")
                yield Button("Apply & Save", id="btn_fak_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_fak")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "magenta")
        d.styles.padding = (0, 1)
        d.styles.width = 44
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_fak_title").styles.text_align = "center"
        self.query_one("#dialog_fak_title").styles.color = "magenta"
        self.query_one("#dialog_fak_title").styles.text_style = "bold"
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 1, 0)
        
        form = self.query_one("#fak_form_area")
        form.styles.width = "100%"
        form.styles.height = "auto"
        form.styles.layout = "vertical"
        form.styles.align = ("center", "top")
        
        for row in self.query(".fak_row"):
            row.styles.height = 1
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 0)
            row.styles.padding = (0, 0, 0, 0)
            
        for lbl in self.query(".fak_lbl"):
            lbl.styles.width = "3fr"
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".fak_inp"):
            inp.styles.width = 10
            inp.styles.height = 1
            inp.styles.margin = (0, 0, 0, 0)
            inp.styles.padding = (0, 0, 0, 0)
            
        row = self.query_one("#dialog_fak_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (1, 0, 0, 0)
        row.styles.height = 1

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_fak_reset")
    def _reset_settings(self):
        self.query_one("#fak_phase1_duration").value = "60"

    @on(Button.Pressed, "#btn_fak_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.phase1_duration = int(self.query_one("#fak_phase1_duration").value)
                
            if self.main_app:
                # Save into app dict so it persists
                self.main_app.fak_settings = {
                    "phase1_duration": getattr(self.s, "phase1_duration", 60),
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ FAK Config Updated", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving FAK: {e}", level="ERROR")
            
        self.dismiss()


class MEASettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app, scanner_obj):
        super().__init__()
        self.main_app = main_app
        self.s = scanner_obj
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_mea"):
            yield Label("MeanReversion Configuration", id="dialog_mea_title")
            yield Label("Tune rejection threshold.", classes="dialog_subtitle")
            
            with Vertical(id="mea_form_area"):
                with Horizontal(classes="mea_row"):
                    yield Label("Rvs Thresh:", classes="mea_lbl")
                    val = str(getattr(self.s, "reversal_threshold", 0.0005)) if self.s else "0.0005"
                    yield Input(placeholder="0.0005", value=val, id="mea_reversal_threshold", classes="mea_inp")
            
            with Horizontal(id="dialog_mea_buttons"):
                yield Button("Reset", id="btn_mea_reset", variant="warning")
                yield Button("Apply & Save", id="btn_mea_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_mea")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "magenta")
        d.styles.padding = (0, 1)
        d.styles.width = 44
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_mea_title").styles.text_align = "center"
        self.query_one("#dialog_mea_title").styles.color = "magenta"
        self.query_one("#dialog_mea_title").styles.text_style = "bold"
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 1, 0)
        
        form = self.query_one("#mea_form_area")
        form.styles.width = "100%"
        form.styles.height = "auto"
        form.styles.layout = "vertical"
        form.styles.align = ("center", "top")
        
        for row in self.query(".mea_row"):
            row.styles.height = 1
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 0)
            row.styles.padding = (0, 0, 0, 0)
            
        for lbl in self.query(".mea_lbl"):
            lbl.styles.width = "3fr"
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".mea_inp"):
            inp.styles.width = 10
            inp.styles.height = 1
            inp.styles.margin = (0, 0, 0, 0)
            inp.styles.padding = (0, 0, 0, 0)
            
        row = self.query_one("#dialog_mea_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (1, 0, 0, 0)
        row.styles.height = 1

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_mea_reset")
    def _reset_settings(self):
        self.query_one("#mea_reversal_threshold").value = "0.0005"

    @on(Button.Pressed, "#btn_mea_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.reversal_threshold = float(self.query_one("#mea_reversal_threshold").value)
                
            if self.main_app:
                # Save into app dict so it persists
                self.main_app.mea_settings = {
                    "reversal_threshold": getattr(self.s, "reversal_threshold", 0.0005),
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ MEA Config Updated", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving MEA: {e}", level="ERROR")
            
        self.dismiss()


class VOLSettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app, scanner_obj):
        super().__init__()
        self.main_app = main_app
        self.s = scanner_obj
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_vol"):
            yield Label("VolCheck Configuration", id="dialog_vol_title")
            yield Label("Tune volatility multiplier.", classes="dialog_subtitle")
            
            with Vertical(id="vol_form_area"):
                with Horizontal(classes="vol_row"):
                    yield Label("Avg3m Mult:", classes="vol_lbl")
                    val = str(getattr(self.s, "avg_3m_multiplier", 1.0)) if self.s else "1.0"
                    yield Input(placeholder="1.0", value=val, id="vol_avg_3m_multiplier", classes="vol_inp")
            
            with Horizontal(id="dialog_vol_buttons"):
                yield Button("Reset", id="btn_vol_reset", variant="warning")
                yield Button("Apply & Save", id="btn_vol_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_vol")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "magenta")
        d.styles.padding = (0, 1)
        d.styles.width = 44
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_vol_title").styles.text_align = "center"
        self.query_one("#dialog_vol_title").styles.color = "magenta"
        self.query_one("#dialog_vol_title").styles.text_style = "bold"
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 1, 0)
        
        form = self.query_one("#vol_form_area")
        form.styles.width = "100%"
        form.styles.height = "auto"
        form.styles.layout = "vertical"
        form.styles.align = ("center", "top")
        
        for row in self.query(".vol_row"):
            row.styles.height = 1
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 0)
            row.styles.padding = (0, 0, 0, 0)
            
        for lbl in self.query(".vol_lbl"):
            lbl.styles.width = "3fr"
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".vol_inp"):
            inp.styles.width = 10
            inp.styles.height = 1
            inp.styles.margin = (0, 0, 0, 0)
            inp.styles.padding = (0, 0, 0, 0)
            
        row = self.query_one("#dialog_vol_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (1, 0, 0, 0)
        row.styles.height = 1

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_vol_reset")
    def _reset_settings(self):
        self.query_one("#vol_avg_3m_multiplier").value = "1.0"

    @on(Button.Pressed, "#btn_vol_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.avg_3m_multiplier = float(self.query_one("#vol_avg_3m_multiplier").value)
                
            if self.main_app:
                # Save into app dict so it persists
                self.main_app.vol_settings = {
                    "avg_3m_multiplier": getattr(self.s, "avg_3m_multiplier", 1.0),
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ VOL Config Updated", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving VOL: {e}", level="ERROR")
            
        self.dismiss()


class MOSSettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app, scanner_obj):
        super().__init__()
        self.main_app = main_app
        self.s = scanner_obj
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_mos"):
            yield Label("Moshe Sniper Config", id="dialog_mos_title")
            yield Label("Tune time/diff curve and threshold.", classes="dialog_subtitle")
            
            with Vertical(id="mos_form_area"):
                with Horizontal(classes="mos_row"):
                    yield Label("Moshe Thresh:", classes="mos_lbl")
                    val = str(getattr(self.s, "moshe_threshold", 0.86)) if self.s else "0.86"
                    yield Input(placeholder="0.86", value=val, id="mos_moshe_threshold", classes="mos_inp")
                with Horizontal(classes="mos_row"):
                    yield Label("T1 (Time):", classes="mos_lbl")
                    val = str(getattr(self.s, "t1", 290)) if self.s else "290"
                    yield Input(placeholder="290", value=val, id="mos_t1", classes="mos_inp")
                with Horizontal(classes="mos_row"):
                    yield Label("D1 (Diff):", classes="mos_lbl")
                    val = str(getattr(self.s, "d1", 2000.0)) if self.s else "2000.0"
                    yield Input(placeholder="2000.0", value=val, id="mos_d1", classes="mos_inp")
                with Horizontal(classes="mos_row"):
                    yield Label("T2 (Time):", classes="mos_lbl")
                    val = str(getattr(self.s, "t2", 80)) if self.s else "80"
                    yield Input(placeholder="80", value=val, id="mos_t2", classes="mos_inp")
                with Horizontal(classes="mos_row"):
                    yield Label("D2 (Diff):", classes="mos_lbl")
                    val = str(getattr(self.s, "d2", 80.0)) if self.s else "80.0"
                    yield Input(placeholder="80.0", value=val, id="mos_d2", classes="mos_inp")
                with Horizontal(classes="mos_row"):
                    yield Label("T3 (Time):", classes="mos_lbl")
                    val = str(getattr(self.s, "t3", 15)) if self.s else "15"
                    yield Input(placeholder="15", value=val, id="mos_t3", classes="mos_inp")
                with Horizontal(classes="mos_row"):
                    yield Label("D3 (Diff):", classes="mos_lbl")
                    val = str(getattr(self.s, "d3", 25.0)) if self.s else "25.0"
                    yield Input(placeholder="25.0", value=val, id="mos_d3", classes="mos_inp")
            
            with Horizontal(id="dialog_mos_buttons"):
                yield Button("Reset", id="btn_mos_reset", variant="warning")
                yield Button("Apply & Save", id="btn_mos_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_mos")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "magenta")
        d.styles.padding = (0, 1)
        d.styles.width = 44
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_mos_title").styles.text_align = "center"
        self.query_one("#dialog_mos_title").styles.color = "magenta"
        self.query_one("#dialog_mos_title").styles.text_style = "bold"
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 1, 0)
        
        form = self.query_one("#mos_form_area")
        form.styles.width = "100%"
        form.styles.height = "auto"
        form.styles.layout = "vertical"
        form.styles.align = ("center", "top")
        
        for row in self.query(".mos_row"):
            row.styles.height = 1
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 0)
            row.styles.padding = (0, 0, 0, 0)
            
        for lbl in self.query(".mos_lbl"):
            lbl.styles.width = "3fr"
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".mos_inp"):
            inp.styles.width = 10
            inp.styles.height = 1
            inp.styles.margin = (0, 0, 0, 0)
            inp.styles.padding = (0, 0, 0, 0)
            
        row = self.query_one("#dialog_mos_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (1, 0, 0, 0)
        row.styles.height = 1

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_mos_reset")
    def _reset_settings(self):
        self.query_one("#mos_moshe_threshold").value = "0.86"
        self.query_one("#mos_t1").value = "290"
        self.query_one("#mos_d1").value = "2000.0"
        self.query_one("#mos_t2").value = "80"
        self.query_one("#mos_d2").value = "80.0"
        self.query_one("#mos_t3").value = "15"
        self.query_one("#mos_d3").value = "25.0"

    @on(Button.Pressed, "#btn_mos_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.moshe_threshold = float(self.query_one("#mos_moshe_threshold").value)
                self.s.t1 = int(self.query_one("#mos_t1").value)
                self.s.d1 = float(self.query_one("#mos_d1").value)
                self.s.t2 = int(self.query_one("#mos_t2").value)
                self.s.d2 = float(self.query_one("#mos_d2").value)
                self.s.t3 = int(self.query_one("#mos_t3").value)
                self.s.d3 = float(self.query_one("#mos_d3").value)
                
            if self.main_app:
                # Save into app dict so it persists
                self.main_app.mos_settings = {
                    "moshe_threshold": getattr(self.s, "moshe_threshold", 0.86),
                    "t1": getattr(self.s, "t1", 290),
                    "d1": getattr(self.s, "d1", 2000.0),
                    "t2": getattr(self.s, "t2", 80),
                    "d2": getattr(self.s, "d2", 80.0),
                    "t3": getattr(self.s, "t3", 15),
                    "d3": getattr(self.s, "d3", 25.0),
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ MOS Config Updated", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving MOS: {e}", level="ERROR")
            
        self.dismiss()


class ZSCSettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app, scanner_obj):
        super().__init__()
        self.main_app = main_app
        self.s = scanner_obj
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_zsc"):
            yield Label("Z-Score Configuration", id="dialog_zsc_title")
            yield Label("Tune statistical breakout devs.", classes="dialog_subtitle")
            
            with Vertical(id="zsc_form_area"):
                with Horizontal(classes="zsc_row"):
                    yield Label("Z-Threshold:", classes="zsc_lbl")
                    val = str(getattr(self.s, "z_threshold", 3.5)) if self.s else "3.5"
                    yield Input(placeholder="3.5", value=val, id="zsc_z_threshold", classes="zsc_inp")
                with Horizontal(classes="zsc_row"):
                    yield Label("Coil Thresh:", classes="zsc_lbl")
                    val = str(getattr(self.s, "coil_threshold", 0.001)) if self.s else "0.001"
                    yield Input(placeholder="0.001", value=val, id="zsc_coil_threshold", classes="zsc_inp")
            
            with Horizontal(id="dialog_zsc_buttons"):
                yield Button("Reset", id="btn_zsc_reset", variant="warning")
                yield Button("Apply & Save", id="btn_zsc_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_zsc")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "magenta")
        d.styles.padding = (0, 1)
        d.styles.width = 44
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_zsc_title").styles.text_align = "center"
        self.query_one("#dialog_zsc_title").styles.color = "magenta"
        self.query_one("#dialog_zsc_title").styles.text_style = "bold"
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 1, 0)
        
        form = self.query_one("#zsc_form_area")
        form.styles.width = "100%"
        form.styles.height = "auto"
        form.styles.layout = "vertical"
        form.styles.align = ("center", "top")
        
        for row in self.query(".zsc_row"):
            row.styles.height = 1
            row.styles.align = ("left", "middle")
            row.styles.margin = (0, 0, 0, 0)
            row.styles.padding = (0, 0, 0, 0)
            
        for lbl in self.query(".zsc_lbl"):
            lbl.styles.width = "3fr"
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".zsc_inp"):
            inp.styles.width = 10
            inp.styles.height = 1
            inp.styles.margin = (0, 0, 0, 0)
            inp.styles.padding = (0, 0, 0, 0)
            
        row = self.query_one("#dialog_zsc_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (1, 0, 0, 0)
        row.styles.height = 1

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_zsc_reset")
    def _reset_settings(self):
        self.query_one("#zsc_z_threshold").value = "3.5"
        self.query_one("#zsc_coil_threshold").value = "0.001"

    @on(Button.Pressed, "#btn_zsc_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.z_threshold = float(self.query_one("#zsc_z_threshold").value)
                self.s.coil_threshold = float(self.query_one("#zsc_coil_threshold").value)
                
            if self.main_app:
                # Save into app dict so it persists
                self.main_app.zsc_settings = {
                    "z_threshold": getattr(self.s, "z_threshold", 3.5),
                    "coil_threshold": getattr(self.s, "coil_threshold", 0.001),
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ ZSC Config Updated", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving ZSC: {e}", level="ERROR")
            
        self.dismiss()


class BRISettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app, scanner_obj):
        super().__init__()
        self.main_app = main_app
        self.s = scanner_obj
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_bri"):
            yield Label("Briefing Algorithm Config", id="dialog_bri_title")
            yield Label("Tune start-of-window scoring factors.", classes="dialog_subtitle")
            
            with Vertical(id="bri_form_area"):
                with Horizontal(classes="bri_row"):
                    yield Label("RSI Low/High:", classes="bri_lbl")
                    l_rsi = str(getattr(self.s, "rsi_low", 30))
                    h_rsi = str(getattr(self.s, "rsi_high", 70))
                    yield Input(placeholder="30", value=l_rsi, id="bri_rsi_low", classes="bri_inp_sm")
                    yield Input(placeholder="70", value=h_rsi, id="bri_rsi_high", classes="bri_inp_sm")
                
                with Horizontal(classes="bri_row"):
                    yield Label("Odds Thresh (¢):", classes="bri_lbl")
                    val = str(getattr(self.s, "odds_thresh", 5.0))
                    yield Input(placeholder="5.0", value=val, id="bri_odds_thresh", classes="bri_inp")
                
                with Horizontal(classes="bri_row"):
                    yield Label("Imb Thresh (¢):", classes="bri_lbl")
                    val = str(getattr(self.s, "imb_thresh", 2.0))
                    yield Input(placeholder="2.0", value=val, id="bri_imb_thresh", classes="bri_inp")

                with Horizontal(classes="bri_row"):
                    yield Label("Signal Thresh:", classes="bri_lbl")
                    val = str(getattr(self.s, "signal_thresh", 2))
                    yield Input(placeholder="2", value=val, id="bri_signal_thresh", classes="bri_inp")

                yield Label("Algo Weight (Bet Multiplier):", id="bri_weight_title")
                with RadioSet(id="rs_bri_weight"):
                    yield RadioButton("1.0x", id="rb_bri_10")
                    yield RadioButton("1.2x", id="rb_bri_12")
                    yield RadioButton("1.5x", id="rb_bri_15")
                    yield RadioButton("1.8x", id="rb_bri_18")
                    yield RadioButton("2.0x", id="rb_bri_20")
            
            with Horizontal(id="dialog_bri_buttons"):
                yield Button("Reset", id="btn_bri_reset", variant="warning")
                yield Button("Apply & Save", id="btn_bri_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_bri")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("round", "cyan")
        d.styles.padding = (1, 2)
        d.styles.width = 50
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_bri_title").styles.text_align = "center"
        self.query_one("#dialog_bri_title").styles.color = "cyan"
        self.query_one("#dialog_bri_title").styles.text_style = "bold"
        self.query_one("#dialog_bri_title").styles.margin = (0, 0, 1, 0)
        
        sub = self.query_one(".dialog_subtitle")
        sub.styles.text_align = "center"
        sub.styles.color = "#888"
        sub.styles.margin = (0, 0, 2, 0)
        
        self.query_one("#bri_weight_title").styles.margin = (1, 0, 0, 0)
        self.query_one("#bri_weight_title").styles.color = "#aaa"
        
        rs = self.query_one("#rs_bri_weight")
        rs.styles.layout = "horizontal"
        rs.styles.height = 3
        rs.styles.border = "none"
        rs.styles.background = "transparent"

        # Set initial radio value
        if self.main_app:
            w = self.main_app.scanner_weights.get("BRI", 1.0)
            if w <= 1.0: self.query_one("#rb_bri_10").value = True
            elif w <= 1.2: self.query_one("#rb_bri_12").value = True
            elif w <= 1.5: self.query_one("#rb_bri_15").value = True
            elif w <= 1.8: self.query_one("#rb_bri_18").value = True
            else: self.query_one("#rb_bri_20").value = True

        for row in self.query(".bri_row"):
            row.styles.height = 3
            row.styles.align = ("left", "middle")
            
        for lbl in self.query(".bri_lbl"):
            lbl.styles.width = 18
            lbl.styles.content_align = ("right", "middle")
            lbl.styles.margin = (0, 1, 0, 0)
            
        for inp in self.query(".bri_inp"):
            inp.styles.width = 10
        for inp in self.query(".bri_inp_sm"):
            inp.styles.width = 8
            inp.styles.margin = (0, 1, 0, 0)
            
        row = self.query_one("#dialog_bri_buttons")
        row.styles.align = ("center", "middle")
        row.styles.margin = (2, 0, 0, 0)
        row.styles.height = 3

    def action_dismiss(self):
        self.save_and_close()

    @on(Button.Pressed, "#btn_bri_reset")
    def _reset_settings(self):
        self.query_one("#bri_rsi_low").value = "30"
        self.query_one("#bri_rsi_high").value = "70"
        self.query_one("#bri_odds_thresh").value = "5.0"
        self.query_one("#bri_imb_thresh").value = "2.0"
        self.query_one("#bri_signal_thresh").value = "2"
        self.query_one("#rb_bri_10").value = True

    @on(Button.Pressed, "#btn_bri_save")
    def save_and_close(self):
        try:
            if self.s:
                self.s.rsi_low = int(self.query_one("#bri_rsi_low").value)
                self.s.rsi_high = int(self.query_one("#bri_rsi_high").value)
                self.s.odds_thresh = float(self.query_one("#bri_odds_thresh").value)
                self.s.imb_thresh = float(self.query_one("#bri_imb_thresh").value)
                self.s.signal_thresh = int(self.query_one("#bri_signal_thresh").value)
                
            if self.main_app:
                # Determine weight from RadioSet
                rb = self.query_one("#rs_bri_weight").pressed_button
                w = 1.0
                if rb:
                    if rb.id == "rb_bri_12": w = 1.2
                    elif rb.id == "rb_bri_15": w = 1.5
                    elif rb.id == "rb_bri_18": w = 1.8
                    elif rb.id == "rb_bri_20": w = 2.0
                
                self.main_app.scanner_weights["BRI"] = w
                
                # Save into app dict so it persists
                self.main_app.bri_settings = {
                    "rsi_low": self.s.rsi_low if self.s else 30,
                    "rsi_high": self.s.rsi_high if self.s else 70,
                    "odds_thresh": self.s.odds_thresh if self.s else 5.0,
                    "imb_thresh": self.s.imb_thresh if self.s else 2.0,
                    "signal_thresh": self.s.signal_thresh if self.s else 2,
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ BRIEF Config Updated (Weight: {w}x)", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving BRIEF: {e}", level="ERROR")
            
        self.dismiss()

class TrendEfficiencyModal(ModalScreen):
    """Dashboard to configure efficiency settings per market trend."""
    BINDINGS = [("escape", "dismiss", "Dismiss")]
    
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.trends = ["M-UP", "S-UP", "W-UP", "NEUTRAL", "W-DOWN", "S-DOWN", "M-DOWN"]

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield Static("[bold #ffaa00]Trend Efficiency Dashboard[/]", id="modal_title")
            yield Static("Optimize risk and safety per trend regime.", id="modal_subtitle")
            
            with Vertical(id="efficiency_grid"):
                # Header
                with Horizontal(classes="eff_header_row"):
                    yield Label("Trend", classes="eff_col_trend")
                    yield Label("Size Mult", classes="eff_col_mult")
                    yield Label("Safety Mode", classes="eff_col_lock")
                    yield Label("Cool-X", classes="eff_col_cool")
                
                for t in self.trends:
                    with Horizontal(id=f"row_{t}", classes="eff_data_row"):
                        yield Label(t, classes="eff_col_trend")
                        yield Input(id=f"mult_{t}", placeholder="1.0", classes="eff_input")
                        yield Select([
                            ("Global", "global_lock"),
                            ("Side", "side_lock"),
                            ("Cap", "risk_cap"),
                            ("Unrest", "unrestricted")
                        ], id=f"lock_{t}", value="side_lock", classes="eff_select")
                        yield Input(id=f"cool_{t}", placeholder="1.0", classes="eff_input")

            with Horizontal(id="modal_footer"):
                yield Button("SAVE & CLOSE", id="btn_eff_save", variant="primary")

    def on_mount(self):
        self.styles.align = ("center", "middle")
        c = self.query_one("#modal_container")
        c.styles.background = "#1a1a1a"
        c.styles.border = ("thick", "#ffaa00")
        c.styles.padding = (1, 2)
        c.styles.width = 75
        c.styles.height = "auto"
        c.styles.max_height = "90vh"
        c.styles.align = ("center", "middle")
        
        self.query_one("#modal_title").styles.text_align = "center"
        self.query_one("#modal_title").styles.width = "100%"
        self.query_one("#modal_subtitle").styles.text_align = "center"
        self.query_one("#modal_subtitle").styles.width = "100%"
        self.query_one("#modal_subtitle").styles.color = "#666666"
        self.query_one("#modal_subtitle").styles.margin = (0, 0, 1, 0)

        grid = self.query_one("#efficiency_grid")
        grid.styles.border = ("ascii", "#333333")
        grid.styles.height = "auto"

        for row in self.query(".eff_header_row, .eff_data_row"):
            row.styles.height = 3
            row.styles.align = ("center", "middle")

        for lbl in self.query(".eff_col_trend"):
            lbl.styles.width = 10
            lbl.styles.text_style = "bold"
            lbl.styles.color = "cyan"

        for inp in self.query(".eff_input"):
            inp.styles.width = 10
            inp.styles.margin = (0, 1)

        for sel in self.query(".eff_select"):
            sel.styles.width = 18
            sel.styles.margin = (0, 1)

        # Load values
        if self.main_app:
            for t in self.trends:
                cfg = self.main_app.trend_efficiency.get(t, {"mult": 1.0, "lock": "side_lock", "cool": 1.0})
                self.query_one(f"#mult_{t}").value = str(cfg["mult"])
                self.query_one(f"#lock_{t}").value = cfg["lock"]
                self.query_one(f"#cool_{t}").value = str(cfg["cool"])

        footer = self.query_one("#modal_footer")
        footer.styles.align = ("center", "middle")
        footer.styles.width = "100%"
        footer.styles.margin = (1, 0, 0, 0)

    @on(Button.Pressed, "#btn_eff_save")
    def save_and_close(self):
        if self.main_app:
            new_cfg = {}
            for t in self.trends:
                try:
                    m = float(self.query_one(f"#mult_{t}").value)
                    l = self.query_one(f"#lock_{t}").value
                    c = float(self.query_one(f"#cool_{t}").value)
                    new_cfg[t] = {"mult": m, "lock": l, "cool": c}
                except:
                    pass
            self.main_app.trend_efficiency.update(new_cfg)
            self.main_app.save_settings()
            self.main_app.log_msg("⚙️ Trend Efficiency Updated", level="ADMIN")
        self.dismiss()


class ConvictionScalingModal(ModalScreen):
    """A modal to configure bet scaling based on market odds conviction."""
    BINDINGS = [("escape", "dismiss", "Dismiss")]
    def __init__(self, main_app=None):
        super().__init__()
        self.main_app = main_app

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield Static("[bold #00ff00]Market Conviction Scaling[/]", id="modal_title")
            yield Static("Scale bets based on market odds strength (odds_score).", id="modal_subtitle")
            
            with Vertical(classes="settings_group"):
                with Horizontal(classes="setting_row"):
                    yield Label("Enable Conviction Scaling:", classes="setting_label")
                    yield Checkbox(id="cb_conviction_enabled")
                
            with Vertical(classes="settings_group"):
                yield Static("[dim]1. Alpha Thresholds (¢)[/]", classes="group_title")
                with Horizontal(classes="setting_row"):
                    yield Label("Strong Threshold (¢):", classes="setting_label")
                    yield Input(id="inp_conv_high", placeholder="10.0", classes="setting_input")
                with Horizontal(classes="setting_row"):
                    yield Label("Decisive Threshold (¢):", classes="setting_label")
                    yield Input(id="inp_conv_extreme", placeholder="20.0", classes="setting_input")
            
            with Vertical(classes="settings_group"):
                yield Static("[dim]2. Position Multipliers (x)[/]", classes="group_title")
                with Horizontal(classes="setting_row"):
                    yield Label("Strong Multiplier:", classes="setting_label")
                    yield Input(id="inp_conv_mult_strong", placeholder="1.25", classes="setting_input")
                with Horizontal(classes="setting_row"):
                    yield Label("Decisive Multiplier:", classes="setting_label")
                    yield Input(id="inp_conv_mult_decisive", placeholder="1.50", classes="setting_input")
                with Horizontal(classes="setting_row"):
                    yield Label("Weak Odds Penalty:", classes="setting_label")
                    yield Input(id="inp_conv_penalty", placeholder="0.50", classes="setting_input")
                
            yield Static("[dim]Penalty applies when odds < 3¢. Multipliers apply when scanner matches sentiment.[/]", classes="conv_hint")
            
            with Horizontal(id="modal_footer"):
                yield Button("SAVE & CLOSE", id="btn_conv_save", variant="primary")

    def on_mount(self):
        self.styles.align = ("center", "middle")
        c = self.query_one("#modal_container")
        c.styles.background = "#1a1a1a"
        c.styles.border = ("thick", "#00ff00")
        c.styles.padding = (1, 2)
        c.styles.width = 54
        c.styles.height = "auto"
        c.styles.align = ("center", "middle")
        
        self.query_one("#modal_title").styles.text_align = "center"
        self.query_one("#modal_title").styles.width = "100%"
        self.query_one("#modal_subtitle").styles.text_align = "center"
        self.query_one("#modal_subtitle").styles.width = "100%"
        self.query_one("#modal_subtitle").styles.color = "#666666"
        self.query_one("#modal_subtitle").styles.margin = (0, 0, 1, 0)

        for group in self.query(".settings_group"):
            group.styles.border = ("solid", "#333333")
            group.styles.margin = (0, 0, 1, 0)
            group.styles.padding = (1, 0)

        for title in self.query(".group_title"):
            title.styles.margin = (0, 0, 0, 1)
            title.styles.text_style = "bold italic"
            title.styles.color = "#00ff00"

        for row in self.query(".setting_row"):
            row.styles.height = 3
            row.styles.align = ("left", "middle")
        
        for lbl in self.query(".setting_label"):
            lbl.styles.width = 24
            lbl.styles.margin = (1, 1, 0, 1)
        
        for inp in self.query(".setting_input"):
            inp.styles.width = 10
        
        hint = self.query_one(".conv_hint")
        hint.styles.text_align = "center"
        hint.styles.width = "100%"
        hint.styles.margin = (1, 0)
        hint.styles.color = "#888"

        # Load current values
        if self.main_app:
            s = getattr(self.main_app, "conviction_scaling", {})
            self.query_one("#cb_conviction_enabled").value = s.get("enabled", False)
            self.query_one("#inp_conv_high").value = str(s.get("high_thresh", 10.0))
            self.query_one("#inp_conv_extreme").value = str(s.get("extreme_thresh", 20.0))
            self.query_one("#inp_conv_mult_strong").value = str(s.get("mult_strong", 1.25))
            self.query_one("#inp_conv_mult_decisive").value = str(s.get("mult_decisive", 1.50))
            self.query_one("#inp_conv_penalty").value = str(s.get("penalty", 0.50))

        footer = self.query_one("#modal_footer")
        footer.styles.align = ("center", "middle")
        footer.styles.width = "100%"
        footer.styles.margin = (1, 0, 0, 0)

    @on(Button.Pressed, "#btn_conv_save")
    def save_and_close(self):
        if self.main_app:
            try:
                new_s = {
                    "enabled": self.query_one("#cb_conviction_enabled").value,
                    "high_thresh": float(self.query_one("#inp_conv_high").value),
                    "extreme_thresh": float(self.query_one("#inp_conv_extreme").value),
                    "mult_strong": float(self.query_one("#inp_conv_mult_strong").value),
                    "mult_decisive": float(self.query_one("#inp_conv_mult_decisive").value),
                    "penalty": float(self.query_one("#inp_conv_penalty").value)
                }
                self.main_app.conviction_scaling = new_s
                self.main_app.save_settings()
                self.main_app.log_msg("⚙️ Market Conviction Scaling Updated", level="ADMIN")
            except Exception as e:
                self.main_app.log_msg(f"[red]Error saving conviction settings: {e}[/]")
        self.dismiss()

class SSCSettingsModal(ModalScreen):
    """Shallow Symmetrical Continuation Scanner Settings"""
    
    def __init__(self, main_app=None):
        super().__init__()
        self.main_app = main_app
    
    def compose(self) -> ComposeResult:
        with Container(id="ssc_modal"):
            yield Static("🌊 SHALLOW SYMMETRICAL CONTINUATION SETTINGS", classes="modal_title")
            yield Static("Detects shallow trends with pullback and symmetrical recovery patterns.", classes="modal_subtitle")
            
            with Vertical(id="ssc_settings_grid", classes="settings_grid"):
                # Trend Detection Settings
                yield Static("📈 TREND DETECTION", classes="section_title")
                with Horizontal(classes="setting_row"):
                    yield Label("Max Shallow Slope:")
                    yield Input(placeholder="0.05", id="inp_ssc_max_slope", value="0.05")
                with Horizontal(classes="setting_row"):
                    yield Label("Min Shallow Slope:")
                    yield Input(placeholder="0.01", id="inp_ssc_min_slope", value="0.01")
                with Horizontal(classes="setting_row"):
                    yield Label("Max Angle Variance:")
                    yield Input(placeholder="0.005", id="inp_ssc_angle_variance", value="0.005")
                
                # Pullback Settings
                yield Static("🔄 PULLBACK SETTINGS", classes="section_title")
                with Horizontal(classes="setting_row"):
                    yield Label("Max Pullback Periods:")
                    yield Input(placeholder="5", id="inp_ssc_pullback_periods", value="5")
                
                # Recovery Settings
                yield Static("✅ RECOVERY SETTINGS", classes="section_title")
                with Horizontal(classes="setting_row"):
                    yield Label("Recovery Tolerance:")
                    yield Input(placeholder="0.002", id="inp_ssc_recovery_tolerance", value="0.002")
                
                # Help Text
                yield Static(
                    "📋 HELP:\n"
                    "• Max/Min Shallow Slope: Range for acceptable shallow trend angles\n"
                    "• Max Angle Variance: Allowed deviation between initial and continuation slopes\n"
                    "• Max Pullback Periods: Maximum time allowed for pullback phase\n"
                    "• Recovery Tolerance: Price tolerance for trendline recovery detection",
                    classes="help_text"
                )
            
            with Horizontal(classes="button_row"):
                yield Button("💾 Save", id="btn_ssc_save", variant="primary")
                yield Button("❌ Cancel", id="btn_ssc_cancel")

    def on_mount(self) -> None:
        self._apply_styles()
        self.call_after_refresh(self._load_values)
    
    def _apply_styles(self):
        title = self.query_one(".modal_title")
        title.styles.text_align = "center"
        title.styles.margin = (0, 0, 1, 0)
        title.styles.color = "#00ffff"
        
        subtitle = self.query_one(".modal_subtitle")
        subtitle.styles.text_align = "center"
        subtitle.styles.margin = (0, 0, 2, 0)
        subtitle.styles.color = "#888"
        subtitle.styles.width = "80%"
        subtitle.styles.text_align = "center"
        
        modal = self.query_one("#ssc_modal")
        modal.styles.width = "60%"
        modal.styles.height = "auto"
        modal.styles.padding = 2
        modal.styles.border = ("thick", "#00ffff")
        modal.styles.background = "#0a0a0a"
        
        for section in self.query(".section_title"):
            section.styles.margin = (1, 0, 0, 0)
            section.styles.color = "#00ff88"
            section.styles.bold = True
        
        for row in self.query(".setting_row"):
            row.styles.justify_content = "space-between"
            row.styles.margin = (0, 0, 1, 0)
        
        for label in self.query("Label"):
            label.styles.width = 25
        
        for inp in self.query("Input"):
            inp.styles.width = 15
        
        help_text = self.query_one(".help_text")
        help_text.styles.margin = (2, 0, 0, 0)
        help_text.styles.padding = 1
        help_text.styles.background = "rgba(0,255,255,0.1)"
        help_text.styles.border = ("solid", "#00ffff")
        help_text.styles.border_radius = 4
        help_text.styles.color = "#ccc"
        help_text.styles.width = "100%"
        
        button_row = self.query_one(".button_row")
        button_row.styles.justify_content = "center"
        button_row.styles.margin = (2, 0, 0, 0)
        button_row.styles.gap = 1
    
    def _load_values(self):
        if self.main_app:
            scanner = self.main_app.scanners.get("SSC")
            if scanner:
                self.query_one("#inp_ssc_max_slope").value = str(scanner.max_shallow_slope)
                self.query_one("#inp_ssc_min_slope").value = str(scanner.min_shallow_slope)
                self.query_one("#inp_ssc_angle_variance").value = str(scanner.max_angle_variance)
                self.query_one("#inp_ssc_pullback_periods").value = str(scanner.max_pullback_periods)
                self.query_one("#inp_ssc_recovery_tolerance").value = str(scanner.recovery_tolerance)
    
    @on(Button.Pressed, "#btn_ssc_save")
    def save_and_close(self):
        if self.main_app:
            try:
                scanner = self.main_app.scanners.get("SSC")
                if scanner:
                    scanner.max_shallow_slope = float(self.query_one("#inp_ssc_max_slope").value)
                    scanner.min_shallow_slope = float(self.query_one("#inp_ssc_min_slope").value)
                    scanner.max_angle_variance = float(self.query_one("#inp_ssc_angle_variance").value)
                    scanner.max_pullback_periods = int(self.query_one("#inp_ssc_pullback_periods").value)
                    scanner.recovery_tolerance = float(self.query_one("#inp_ssc_recovery_tolerance").value)
                    
                    self.main_app.save_settings()
                    self.main_app.log_msg("⚙️ SSC Settings Updated", level="ADMIN")
            except Exception as e:
                self.main_app.log_msg(f"[red]Error saving SSC settings: {e}[/]")
        self.dismiss()
    
    @on(Button.Pressed, "#btn_ssc_cancel")
    def cancel_and_close(self):
        self.dismiss()


class DarwinSettingsModal(ModalScreen):
    """A dedicated status and control modal for the DARWIN AI agent."""
    BINDINGS = [("escape", "dismiss", "Dismiss")]

    def __init__(self, main_app=None):
        super().__init__()
        self.main_app = main_app
        self.darwin = getattr(main_app, "darwin", None)

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="modal_container"):
            with Horizontal(id="modal_header"):
                yield Static("[bold #00ffff]🧬 DARWIN AI STATUS & REASONING[/]", id="modal_title")
                yield Button("TEST CONNECTION", id="btn_darwin_test", variant="primary")

            if not self.darwin:
                yield Label("[red]Error: DarwinAgent instance not found in PulseApp.[/]")
            else:
                # 1. Performance Overview
                with Collapsible(title="📈 VIRTUAL PERFORMANCE (Experimenter Mode)", id="gp_perf", classes="settings_group"):
                    wr = (self.darwin.virtual_wins / self.darwin.virtual_trades * 100) if self.darwin.virtual_trades > 0 else 0
                    pnl_color = "#00ff00" if self.darwin.virtual_pnl >= 0 else "#ff0000"
                    
                    with Horizontal(classes="setting_row"):
                        yield Label("Current Mode:", classes="setting_label")
                        yield Label(f"[cyan]{self.darwin.mode}[/]", classes="setting_value")
                    with Horizontal(classes="setting_row"):
                        yield Label("Virtual P&L:", classes="setting_label")
                        yield Label(f"[{pnl_color}]${self.darwin.virtual_pnl:.2f}[/]", classes="setting_value")
                    with Horizontal(classes="setting_row"):
                        yield Label("Win Rate:", classes="setting_label")
                        yield Label(f"{wr:.1f}% ({self.darwin.virtual_wins}/{self.darwin.virtual_trades} trades)", classes="setting_value")

                # 2. Latest Insights (Observations.md)
                with Collapsible(title="🧠 LATEST INSIGHTS & HYPOTHESES", id="gp_insights", classes="settings_group"):
                    obs_text = ""
                    if DARWIN_OBSERVATIONS.exists():
                        try:
                            obs_text = DARWIN_OBSERVATIONS.read_text(encoding="utf-8")
                        except: obs_text = "Error reading observations.md"
                    
                    if not obs_text:
                        yield Label("[dim italic]No observations recorded yet.[/]")
                    else:
                        yield Markdown(obs_text, id="darwin_insights_md")

                # 3. Reasoning Log (Experiment Log)
                with Collapsible(title="📜 REASONING & EXPERIMENT LOG", id="gp_log", classes="settings_group"):
                    log_data = []
                    if DARWIN_EXPERIMENT_LOG.exists():
                        try:
                            log_data = json.loads(DARWIN_EXPERIMENT_LOG.read_text(encoding="utf-8"))
                        except: pass
                    
                    if not log_data:
                        yield Label("[dim italic]No experiment logs found.[/]")
                    else:
                        # Show last 5 experiments in reverse order
                        for entry in reversed(log_data[-5:]):
                            timestamp = entry.get("timestamp", "N/A")
                            hyp = entry.get("hypothesis", "...")
                            obs = entry.get("observation", "")
                            script = entry.get("script_run", "No action")
                            yield Static(f"[bold #aaaaaa]{timestamp}[/]\n[cyan]Hypothesis:[/] {hyp}\n[dim]{obs}[/]\n[bold #00ff00]Action:[/] {script}\n", classes="log_entry")

                # 4. Active Algorithm Code
                with Collapsible(title="💻 ACTIVE ALGORITHM CODE", id="gp_code", classes="settings_group"):
                    code_text = ""
                    if DARWIN_CURRENT_ALGO.exists():
                        try:
                            code_text = DARWIN_CURRENT_ALGO.read_text(encoding="utf-8")
                        except: code_text = "Error reading current_algo.py"
                    
                    if not code_text:
                        yield Label("[dim italic]No algorithm code discovered yet (V2 only).[/]")
                    else:
                        from textual.widgets import TextArea
                        yield TextArea(code_text, language="python", read_only=True, id="darwin_code_viewer")

                # 5. Darwin Chat (Playful Interaction)
                with Collapsible(title="💬 CHAT WITH DARWIN", id="gp_chat", classes="settings_group"):
                    yield Static("[dim italic]Ask Darwin about its hypothesis or current strategy.[/]", id="lbl_chat_hint")
                    with Vertical(id="chat_display_area"):
                        yield RichLog(id="darwin_chat_log", wrap=True, highlight=True, markup=True)
                    with Horizontal(id="chat_input_row"):
                        yield Input(placeholder="Type message to Darwin...", id="inp_darwin_chat")
                        yield Button("SEND", id="btn_darwin_chat_send", variant="primary")

            with Horizontal(id="modal_footer"):
                yield Button("CLOSE", id="btn_darwin_close", variant="error")

    @on(Button.Pressed, "#btn_darwin_test")
    def test_darwin_connection(self):
        """Handler for the 'TEST CONNECTION' button."""
        if self.darwin:
            btn = self.query_one("#btn_darwin_test")
            btn.label = "TESTING..."
            btn.disabled = True
            
            # Diagnostic call
            result = self.darwin.test_connection()
            self.main_app.notify(result, title="DARWIN Connection Test", severity="info" if "Success" in result else "error")
            
            btn.label = "TEST CONNECTION"
            btn.disabled = False

    @on(Button.Pressed, "#btn_darwin_close")
    def action_close_button(self):
        self.dismiss()

    @on(Button.Pressed, "#btn_darwin_chat_send")
    @on(Input.Submitted, "#inp_darwin_chat")
    def on_chat_submit(self):
        inp = self.query_one("#inp_darwin_chat")
        msg = inp.value.strip()
        if not msg or not self.darwin:
            return

        chat_log = self.query_one("#darwin_chat_log")
        chat_log.write(f"[bold #00ffff]YOU:[/] {msg}")
        chat_log.write(f"[italic #888888]Darwin is thinking...[/]")
        inp.value = ""
        
        async def run_chat():
            # Run in thread pool to avoid blocking the main loop
            try:
                sys_ctx = self.main_app._assemble_darwin_system_config() if self.main_app else None
                
                def get_response():
                    try:
                        return self.darwin.on_chat_submit(msg, system_context=sys_ctx)
                    except Exception as e:
                        return f"Error: {e}"

                # Using a worker for better Textual integration
                response = await self.run_worker(get_response, thread=True).wait()
                
                if response:
                    # Parse for JSON actions in the response
                    import re
                    json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
                    actions = []
                    clean_text = response
                    
                    if json_match:
                        try:
                            action_data = json.loads(json_match.group(1))
                            actions = action_data.get("actions", [])
                            # Strip the JSON block from the text shown to user to keep it clean
                            clean_text = response.replace(json_match.group(0), "").strip()
                        except: pass
                    
                    chat_log.write(f"[bold #ff00ff]DARWIN:[/] {clean_text}\n")
                    
                    if actions and self.main_app:
                        self.main_app._apply_darwin_system_actions(actions)
                        chat_log.write(f"[dim grey italic]🧬 System actions applied successfully.[/]\n")
                else:
                    chat_log.write(f"[red]Darwin remained silent.[/]\n")
            except Exception as e:
                chat_log.write(f"[red]Chat System Error: {e}[/]\n")
            
        self.run_worker(run_chat())

    def on_mount(self):
        self.styles.align = ("center", "middle")
        container = self.query_one("#modal_container")
        container.styles.background = "#1a1a1a"
        container.styles.border = ("thick", "#ff00ff")
        container.styles.padding = (1, 2)
        container.styles.width = 100
        container.styles.height = "80%"
        
        self.query_one("#modal_title").styles.text_align = "left"
        self.query_one("#modal_title").styles.width = "1fr"
        self.query_one("#modal_title").styles.margin = (0, 0, 1, 0)
        
        # Test Button Styling
        try:
            mt = self.query_one("#modal_header")
            mt.styles.height = 3
            mt.styles.align = ("left", "middle")
            
            test_btn = self.query_one("#btn_darwin_test")
            test_btn.styles.min_width = 20
            test_btn.styles.height = 1
            test_btn.styles.border = "none"
            test_btn.styles.margin = (0, 0, 0, 2)
        except: pass
        
        if self.darwin:
            # Insights Markdown Styling
            try:
                md = self.query_one("#darwin_insights_md")
                md.styles.height = 12
                md.styles.border = ("solid", "#333333")
                md.styles.background = "#222222"
                md.styles.padding = (0, 1)
            except: pass

            # Code Viewer Styling
            try:
                cv = self.query_one("#darwin_code_viewer")
                cv.styles.height = 15
                cv.styles.border = ("solid", "#333333")
                cv.styles.margin = (1, 0)
            except: pass
            
            # Chat Styling
            try:
                chat_area = self.query_one("#chat_display_area")
                chat_area.styles.height = 10
                chat_area.styles.border = ("solid", "#333333")
                chat_area.styles.background = "#0d0d0d"
                chat_area.styles.margin = (0, 0, 1, 0)
                
                chat_log = self.query_one("#darwin_chat_log")
                chat_log.styles.width = "100%"
                chat_log.styles.height = "1fr"
                chat_log.styles.scrollbar_gutter = "stable"
                chat_log.styles.scrollbar_size = 1             # Thinner scrollbars
                chat_log.styles.overflow_x = "hidden"         # Prevent horizontal scrollbars from covering text
                chat_log.styles.padding = (0, 3, 1, 1)       # Top Right Bottom Left (Increased right padding)
                
                input_row = self.query_one("#chat_input_row")
                input_row.styles.height = 3
                input_row.styles.align = ("center", "middle")
                
                inp = self.query_one("#inp_darwin_chat")
                inp.styles.width = "1fr"
                
                btn = self.query_one("#btn_darwin_chat_send")
                btn.styles.width = 10
                btn.styles.margin_left = 1
            except: pass

    @on(Button.Pressed, "#btn_modal_close")
    def action_close(self):
        self.dismiss()


class ADTSettingsModal(ModalScreen):
    """Asymmetric Double Test Scanner Settings"""
    
    def __init__(self, main_app=None):
        super().__init__()
        self.main_app = main_app
    
    def compose(self) -> ComposeResult:
        with Container(id="adt_modal"):
            yield Static("⚖️ ASYMMETRIC DOUBLE TEST SETTINGS", classes="modal_title")
            yield Static("Identifies baseline moves with asymmetric double dips/rallies requiring full recovery.", classes="modal_subtitle")
            
            with Vertical(id="adt_settings_grid", classes="settings_grid"):
                # Baseline Settings
                yield Static("📊 BASELINE SETTINGS", classes="section_title")
                with Horizontal(classes="setting_row"):
                    yield Label("Baseline Tolerance:")
                    yield Input(placeholder="0.0015", id="inp_adt_baseline_tolerance", value="0.0015")
                
                # Asymmetry Settings
                yield Static("🔀 ASYMMETRY SETTINGS", classes="section_title")
                with Horizontal(classes="setting_row"):
                    yield Label("Asymmetry Ratio:")
                    yield Input(placeholder="1.25", id="inp_adt_asymmetry_ratio", value="1.25")
                with Horizontal(classes="setting_row"):
                    yield Label("Min Move Distance:")
                    yield Input(placeholder="0.005", id="inp_adt_min_move", value="0.005")
                
                # Help Text
                yield Static(
                    "📋 HELP:\n"
                    "• Baseline Tolerance: Maximum deviation to register return to baseline\n"
                    "• Asymmetry Ratio: Secondary move must be at least this ratio larger than first move\n"
                    "• Min Move Distance: Minimum price movement to filter out market noise\n"
                    "• Example: Ratio 1.25 means second dip must be 25% deeper than first dip",
                    classes="help_text"
                )
            
            with Horizontal(classes="button_row"):
                yield Button("💾 Save", id="btn_adt_save", variant="primary")
                yield Button("❌ Cancel", id="btn_adt_cancel")

    def on_mount(self) -> None:
        self._apply_styles()
        self.call_after_refresh(self._load_values)
    
    def _apply_styles(self):
        title = self.query_one(".modal_title")
        title.styles.text_align = "center"
        title.styles.margin = (0, 0, 1, 0)
        title.styles.color = "#ff00ff"
        
        subtitle = self.query_one(".modal_subtitle")
        subtitle.styles.text_align = "center"
        subtitle.styles.margin = (0, 0, 2, 0)
        subtitle.styles.color = "#888"
        subtitle.styles.width = "80%"
        subtitle.styles.text_align = "center"
        
        modal = self.query_one("#adt_modal")
        modal.styles.width = "60%"
        modal.styles.height = "auto"
        modal.styles.padding = 2
        modal.styles.border = ("thick", "#ff00ff")
        modal.styles.background = "#0a0a0a"
        
        for section in self.query(".section_title"):
            section.styles.margin = (1, 0, 0, 0)
            section.styles.color = "#ff88ff"
            section.styles.bold = True
        
        for row in self.query(".setting_row"):
            row.styles.justify_content = "space-between"
            row.styles.margin = (0, 0, 1, 0)
        
        for label in self.query("Label"):
            label.styles.width = 25
        
        for inp in self.query("Input"):
            inp.styles.width = 15
        
        help_text = self.query_one(".help_text")
        help_text.styles.margin = (2, 0, 0, 0)
        help_text.styles.padding = 1
        help_text.styles.background = "rgba(255,0,255,0.1)"
        help_text.styles.border = ("solid", "#ff00ff")
        help_text.styles.border_radius = 4
        help_text.styles.color = "#ccc"
        help_text.styles.width = "100%"
        
        button_row = self.query_one(".button_row")
        button_row.styles.justify_content = "center"
        button_row.styles.margin = (2, 0, 0, 0)
        button_row.styles.gap = 1
    
    def _load_values(self):
        if self.main_app:
            scanner = self.main_app.scanners.get("ADT")
            if scanner:
                self.query_one("#inp_adt_baseline_tolerance").value = str(scanner.baseline_tolerance)
                self.query_one("#inp_adt_asymmetry_ratio").value = str(scanner.asymmetry_ratio)
                self.query_one("#inp_adt_min_move").value = str(scanner.min_move_distance)
    
    @on(Button.Pressed, "#btn_adt_save")
    def save_and_close(self):
        if self.main_app:
            try:
                scanner = self.main_app.scanners.get("ADT")
                if scanner:
                    scanner.baseline_tolerance = float(self.query_one("#inp_adt_baseline_tolerance").value)
                    scanner.asymmetry_ratio = float(self.query_one("#inp_adt_asymmetry_ratio").value)
                    scanner.min_move_distance = float(self.query_one("#inp_adt_min_move").value)
                    
                    self.main_app.save_settings()
                    self.main_app.log_msg("⚙️ ADT Settings Updated", level="ADMIN")
            except Exception as e:
                self.main_app.log_msg(f"[red]Error saving ADT settings: {e}[/]")
        self.dismiss()
    
    @on(Button.Pressed, "#btn_adt_cancel")
    def cancel_and_close(self):
        self.dismiss()


class MM2SettingsModal(ModalScreen):
    """
    Redesigned, premium configuration modal for MM2 (Momentum-2).
    Uses a structured layout with sub-modal links for advanced options.
    """
    BINDINGS = [("escape", "dismiss", "Dismiss")]

    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.scanner = self.main_app.scanners.get("MM2")
        self.algo_id = "MM2"

    def compose(self) -> ComposeResult:
        # Default fallback values for composition
        try:
            cur_w = str(self.main_app.scanner_weights.get("MM2", 1.0))
            cur_t = str(int(getattr(self.scanner, "threshold", 0.6) * 100))
            cur_d = str(getattr(self.scanner, "duration", 10))
            cur_m = getattr(self.scanner, "mode", "VECTOR")
        except:
            cur_w, cur_t, cur_d, cur_m = "1.0", "60", "10", "VECTOR"

        with Vertical(id="mm2_modal_container"):
            yield Static("Momentum-2 Intelligence", id="mm2_title")
            yield Static("Unified Scoring & Time-Aware Dynamics", id="mm2_subtitle")

            with Vertical(id="mm2_scroll_area"):
                # 1. Core Config Section
                with Vertical(classes="mm2_section"):
                    yield Static("[bold #00ffff]1. ALPHA PARAMETERS[/]", classes="mm2_sec_title")
                    with Horizontal(classes="mm2_row"):
                        yield Label("Weight (x):", classes="mm2_lbl")
                        yield Input(value=cur_w, placeholder="1.0", id="inp_mm2_weight")
                        yield Label("Threshold (¢):", classes="mm2_lbl")
                        yield Input(value=cur_t, placeholder="60", id="inp_mm2_threshold")
                    with Horizontal(classes="mm2_row"):
                        yield Label("Duration (s):", classes="mm2_lbl")
                        yield Input(value=cur_d, placeholder="10", id="inp_mm2_duration")
                        yield Label("Logic Mode:", classes="mm2_lbl")
                        yield Select([
                            ("VECTOR (Scored)", "VECTOR"),
                            ("TIME (Leader)", "TIME"),
                            ("PRICE (Immediate)", "PRICE"),
                            ("DURATION (Hold)", "DURATION")
                        ], id="sel_mm2_mode", value=cur_m)

                # 2. Buy Mode Selection
                with Vertical(classes="mm2_section"):
                    yield Static("[bold #00ff88]2. EXECUTION REGIME[/]", classes="mm2_sec_title")
                    with Horizontal(classes="mm2_radio_row"):
                        yield RadioSet(
                            RadioButton("Standard (STN)", id="rb_mm2_stn"),
                            RadioButton("Pre-Buy (PBN)", id="rb_mm2_pre"),
                            RadioButton("Hybrid (HYB)", id="rb_mm2_hyb"),
                            RadioButton("Advanced (ADV)", id="rb_mm2_adv"),
                            id="rs_mm2_buy_mode"
                        )
                    yield Static("Selects how buy signals are triggered (Predictive vs Reactive).", classes="mm2_help_text")

                # 3. Advanced Intelligence Hub
                with Vertical(classes="mm2_section"):
                    yield Static("[bold #ffaa00]3. INTELLIGENCE HUB[/]", classes="mm2_sec_title")
                    with Horizontal(classes="mm2_btn_row"):
                        yield Button("⚙️ VOLATILITY / ATR EXPERT", id="btn_mm2_expert", variant="warning")
                    with Horizontal(classes="mm2_btn_row"):
                        yield Button("📊 SENTIMENT / TREND SCALE", id="btn_mm2_scaling", variant="primary")
                    yield Static("Configure ATR tiers, Whale Shield, and conviction scaling.", classes="mm2_help_text")

                # 4. Diagnostics
                with Vertical(classes="mm2_section"):
                    yield Static("[bold #ff0000]4. DIAGNOSTICS[/]", classes="mm2_sec_title")
                    with Horizontal(classes="mm2_btn_row"):
                        yield Button("🚀 RUN REAL-TIME PBN TEST", id="btn_mm2_test", variant="error")

            with Horizontal(id="mm2_footer"):
                yield Button("CLOSE & PERSIST", id="btn_mm2_save", variant="primary")

    def on_mount(self):
        self._apply_styles()
        self._load_values()

    def _apply_styles(self):
        self.styles.align = ("center", "middle")
        self.styles.background = "rgba(0,0,0,0.8)"

        container = self.query_one("#mm2_modal_container")
        container.styles.width = 70
        container.styles.height = "auto"
        container.styles.max_height = "90vh"
        container.styles.background = "#0a0a0a"
        container.styles.border = ("thick", "#00ffff")
        container.styles.padding = (1, 2)

        self.query_one("#mm2_title").styles.text_align = "center"
        self.query_one("#mm2_title").styles.color = "#00ffff"
        self.query_one("#mm2_title").styles.text_style = "bold"
        self.query_one("#mm2_title").styles.width = "100%"

        self.query_one("#mm2_subtitle").styles.text_align = "center"
        self.query_one("#mm2_subtitle").styles.color = "#666666"
        self.query_one("#mm2_subtitle").styles.italic = True
        self.query_one("#mm2_subtitle").styles.width = "100%"
        self.query_one("#mm2_subtitle").styles.margin = (0, 0, 1, 0)

        scroll = self.query_one("#mm2_scroll_area")
        scroll.styles.height = "1fr"
        scroll.styles.width = "100%"
        scroll.styles.overflow_y = "auto"

        for sec in self.query(".mm2_section"):
            sec.styles.margin = (0, 0, 1, 0)
            sec.styles.padding = (0, 1)
            sec.styles.background = "#141414"
            sec.styles.border = ("ascii", "#333333")
            sec.styles.height = "auto"
            sec.styles.width = "100%"

        for title in self.query(".mm2_sec_title"):
            title.styles.margin = (0, 0, 1, 0)
            title.styles.width = "100%"

        for row in self.query(".mm2_row"):
            row.styles.height = "auto"
            row.styles.min_height = 3
            row.styles.align = ("center", "middle")
            row.styles.width = "100%"

        for lbl in self.query(".mm2_lbl"):
            lbl.styles.width = 15
            lbl.styles.color = "#888888"

        for inp in self.query("Input"):
            inp.styles.width = 10
            inp.styles.margin_right = 1

        self.query_one("#sel_mm2_mode").styles.width = 24

        radio_row = self.query_one(".mm2_radio_row")
        radio_row.styles.height = "auto"
        radio_row.styles.min_height = 3
        radio_row.styles.align = ("center", "middle")
        radio_row.styles.width = "100%"
        
        rs = self.query_one("#rs_mm2_buy_mode")
        rs.styles.layout = "horizontal"
        rs.styles.height = "auto"
        rs.styles.border = "none"
        rs.styles.background = "transparent"

        for rb in rs.query(RadioButton):
            rb.styles.width = "auto"
            rb.styles.margin = (0, 1)

        for h in self.query(".mm2_help_text"):
            h.styles.color = "#444444"
            h.styles.italic = True
            h.styles.margin = (1, 0)
            h.styles.text_align = "center"
            h.styles.width = "100%"

        for brow in self.query(".mm2_btn_row"):
            brow.styles.height = "auto"
            brow.styles.min_height = 3
            brow.styles.margin = (0, 0, 1, 0)
            brow.styles.align = ("center", "middle")
            brow.styles.width = "100%"
            for btn in brow.query(Button):
                btn.styles.width = 45

        footer = self.query_one("#mm2_footer")
        footer.styles.margin_top = 1
        footer.styles.align = ("center", "middle")
        footer.styles.width = "100%"
        self.query_one("#btn_mm2_save").styles.width = 40

    def _load_values(self):
        if not self.main_app: return
        try:
            # Load Weights
            w = self.main_app.scanner_weights.get("MM2", 1.0)
            self.query_one("#inp_mm2_weight").value = str(w)

            # Load Core Scanner Params
            if self.scanner:
                self.query_one("#inp_mm2_threshold").value = str(int(getattr(self.scanner, "threshold", 0.6) * 100))
                self.query_one("#inp_mm2_duration").value = str(getattr(self.scanner, "duration", 10))
                self.query_one("#sel_mm2_mode").value = getattr(self.scanner, "mode", "VECTOR")

            # Load Buy Mode
            bm = getattr(self.main_app, "mom_buy_mode", "STD")
            rs = self.query_one("#rs_mm2_buy_mode")
            if bm == "STD": rs.query_one("#rb_mm2_stn").value = True
            elif bm == "PRE": rs.query_one("#rb_mm2_pre").value = True
            elif bm == "HYBRID": rs.query_one("#rb_mm2_hyb").value = True
            elif bm == "ADV": rs.query_one("#rb_mm2_adv").value = True
        except Exception as e:
            if self.main_app:
                self.main_app.log_msg(f"Error loading MM2 values: {e}")

    @on(Button.Pressed, "#btn_mm2_expert")
    def open_expert(self):
        self.main_app.push_screen(MOMExpertModal(self.main_app, algo_id="MM2"))

    @on(Button.Pressed, "#btn_mm2_scaling")
    def open_scaling(self):
        # Using existing conviction scaling modal if available
        self.main_app.push_screen(ConvictionScalingModal(self.main_app))

    @on(Button.Pressed, "#btn_mm2_test")
    def run_test(self):
        # Redirect to a diagnostic bridge or run inline (similar to MOMExpertModal test)
        self.main_app.log_msg("🧪 MM2 Diagnostic Test initiated...", level="ADMIN")
        # For now, we can just push the MOMExpertModal which has the test button, 
        # or implement a specific one here.
        self.open_expert() # Expert modal has the mature test logic

    @on(Button.Pressed, "#btn_mm2_save")
    def save_and_close(self):
        if not self.main_app: 
            self.dismiss()
            return
            
        changes = []
        try:
            # Save Weight
            old_w = self.main_app.scanner_weights.get("MM2", 1.0)
            new_w = float(self.query_one("#inp_mm2_weight").value)
            if old_w != new_w:
                self.main_app.scanner_weights["MM2"] = new_w
                changes.append(f"Weight: {new_w}x")

            # Save Threshold
            old_t = int(getattr(self.scanner, "threshold", 0.6) * 100)
            new_t = int(self.query_one("#inp_mm2_threshold").value)
            if old_t != new_t:
                self.scanner.threshold = new_t / 100.0
                self.scanner.base_threshold = new_t / 100.0
                changes.append(f"Thresh: {new_t}¢")

            # Save Duration
            old_d = getattr(self.scanner, "duration", 10)
            new_d = int(self.query_one("#inp_mm2_duration").value)
            if old_d != new_d:
                self.scanner.duration = new_d
                changes.append(f"Dur: {new_d}s")

            # Save Mode
            old_m = getattr(self.scanner, "mode", "VECTOR")
            new_m = self.query_one("#sel_mm2_mode").value
            if old_m != new_m:
                self.scanner.mode = new_m
                changes.append(f"Mode: {new_m}")

            # Save Buy Mode
            old_bm = self.main_app.mom_buy_mode
            rs = self.query_one("#rs_mm2_buy_mode")
            if rs.query_one("#rb_mm2_stn").value: new_bm = "STD"
            elif rs.query_one("#rb_mm2_pre").value: new_bm = "PRE"
            elif rs.query_one("#rb_mm2_hyb").value: new_bm = "HYBRID"
            elif rs.query_one("#rb_mm2_adv").value: new_bm = "ADV"
            else: new_bm = "STD"

            if old_bm != new_bm:
                self.main_app.mom_buy_mode = new_bm
                changes.append(f"Regime: {new_bm}")

            if changes:
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ MM2 Intelligence Updated: {', '.join(changes)}", level="ADMIN")
                
                # Internal summary dump (matches MOM logic)
                self.main_app.log_msg(f"[bold cyan]📋 MM2 Active Profile:[/]", level="ADMIN")
                self.main_app.log_msg(f"  • Mode: {new_m} | Regime: {new_bm}", level="ADMIN")
                self.main_app.log_msg(f"  • Threshold: {new_t}¢ | Duration: {new_d}s", level="ADMIN")

        except Exception as e:
            self.main_app.log_msg(f"[red]Error saving MM2 settings: {e}[/]")

        self.dismiss()


class VolatilityScalingModal(ModalScreen):
    """
    [NEW] v5.9.15: High-Density Volatility scaling UI
    """
    BINDINGS = [("escape", "dismiss", "Dismiss")]
    def __init__(self, main_app=None):
        super().__init__()
        self.main_app = main_app

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield Static("[bold #ff00ff]Volatility (ATR) Scaling[/]", id="modal_title")
            
            with Vertical(classes="vol_settings_box"):
                with Horizontal(classes="vol_row"):
                    yield Label("Enable Scaling:", classes="vol_label")
                    yield Checkbox(id="cb_vol_enabled")
                
                with Horizontal(classes="vol_row"):
                    yield Label("Scaling Range:", classes="vol_label")
                    yield Input(placeholder="15", id="inp_vol_floor", classes="vol_input_sm")
                    yield Label("to", classes="vol_unit")
                    yield Input(placeholder="40", id="inp_vol_ceiling", classes="vol_input_sm")
                    yield Label("ATR", classes="vol_unit")
                yield Static("[dim italic]Enter 0% size at Floor, 100% at Plateau[/]", classes="vol_hint")

            yield Static("[dim]Note: Sizes scale linearly between levels.[/]", classes="vol_info")

            with Horizontal(id="modal_footer"):
                yield Button("SAVE & CLOSE", id="btn_vol_save", variant="primary")

    def on_mount(self):
        self.styles.align = ("center", "middle")
        c = self.query_one("#modal_container")
        c.styles.background = "#0c0c0c"; c.styles.border = ("thick", "#ff00ff")
        c.styles.padding = (0, 1); c.styles.width = 48; c.styles.height = "auto"
        
        self.query_one("#modal_title").styles.text_align = "center"
        self.query_one("#modal_title").styles.margin = (0, 0)

        box = self.query_one(".vol_settings_box")
        box.styles.border = ("solid", "#222")
        box.styles.padding = (0, 1)
        box.styles.margin = (0, 0)
        box.styles.background = "#141414"

        for row in self.query(".vol_row"):
            row.styles.height = 3; row.styles.align = ("left", "middle"); row.styles.width = "100%"
        
        for lb in self.query(".vol_label"):
            lb.styles.width = 16; lb.styles.color = "#ff00ff"
        
        for inp in self.query(".vol_input_sm"):
            inp.styles.width = 7; inp.styles.height = 1

        for unit in self.query(".vol_unit"):
            unit.styles.margin = (0, 1); unit.styles.color = "#666"

        for hint in self.query(".vol_hint"):
            hint.styles.margin = (-1, 0, 1, 16); hint.styles.color = "#444"; hint.styles.text_style = "italic"

        self.query_one(".vol_info").styles.text_align = "center"; self.query_one(".vol_info").styles.margin = (0, 0)
        
        if self.main_app:
            vs = self.main_app.volatility_scaling
            self.query_one("#cb_vol_enabled").value = vs.get("enabled", False)
            self.query_one("#inp_vol_floor").value = str(vs.get("floor", 15.0))
            self.query_one("#inp_vol_ceiling").value = str(vs.get("ceiling", 40.0))

    @on(Button.Pressed, "#btn_vol_save")
    def save_settings(self):
        if self.main_app:
            try:
                vs = self.main_app.volatility_scaling
                vs["enabled"] = self.query_one("#cb_vol_enabled").value
                vs["floor"] = float(self.query_one("#inp_vol_floor").value)
                vs["ceiling"] = float(self.query_one("#inp_vol_ceiling").value)
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ Volatility Scaling Updated.", level="ADMIN")
            except Exception as e:
                self.main_app.log_msg(f"[red]Error saving Volatility settings: {e}[/]")
        self.dismiss()


class ValueReentryModal(ModalScreen):
    """
    [NEW] v5.9.15: Value Re-entry (Round 2) Logic
    Allows a second entry if price retraces to neutral and then re-confirms.
    """
    BINDINGS = [("escape", "dismiss", "Dismiss")]
    def __init__(self, main_app=None):
        super().__init__()
        self.main_app = main_app

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield Static("[bold #ff00ff]Value Re-entry (Round 2)[/]", id="modal_title")
            
            with Vertical(classes="re_settings_box"):
                with Horizontal(classes="re_row"):
                    yield Label("Enable Strategy:", classes="re_label")
                    yield Checkbox(id="cb_re_enabled")
                
                with Horizontal(classes="re_row"):
                    yield Label("Reset Level (¢):", classes="re_label")
                    yield Input(placeholder="52", id="inp_re_reset", classes="re_input")
                yield Static("[dim italic]Enter after retrace to neutral (0.50)[/]", classes="re_hint")
                
                with Horizontal(classes="re_row"):
                    yield Label("Snap-Back Speed:", classes="re_label")
                    yield Input(placeholder="2.0", id="inp_re_move", classes="re_input_sm")
                    yield Label("¢ in", classes="re_unit")
                    yield Input(placeholder="10", id="inp_re_time", classes="re_input_sm")
                    yield Label("sec", classes="re_unit")
                yield Static("[dim italic]Min move amount and max time allowed[/]", classes="re_hint")

                with Horizontal(classes="re_row"):
                    yield Label("Decay Sizing (%):", classes="re_label")
                    yield Input(placeholder="30", id="inp_re_size", classes="re_input")
                    yield Label("Min Gap (¢):", classes="re_label_sm")
                    yield Input(placeholder="5.0", id="inp_re_gap", classes="re_input_sm")
                yield Static("[dim italic]Size mult and req. distance from 1st entry[/]", classes="re_hint")

            yield Static("[dim]Note: Fires only after a neutral retrace and snap-back.[/]", classes="re_info")

            with Horizontal(id="modal_footer"):
                yield Button("SAVE & CLOSE", id="btn_re_save", variant="primary")

    def on_mount(self):
        self.styles.align = ("center", "middle")
        c = self.query_one("#modal_container")
        c.styles.background = "#0c0c0c"; c.styles.border = ("thick", "#ff00ff")
        c.styles.padding = (0, 1); c.styles.width = 48; c.styles.height = "auto"
        
        self.query_one("#modal_title").styles.text_align = "center"
        self.query_one("#modal_title").styles.margin = (0, 0)

        box = self.query_one(".re_settings_box")
        box.styles.border = ("solid", "#222")
        box.styles.padding = (0, 1)
        box.styles.margin = (0, 0)
        box.styles.background = "#141414"

        for row in self.query(".re_row"):
            row.styles.height = 2; row.styles.align = ("left", "middle"); row.styles.width = "100%"
        
        for lb in self.query(".re_label"):
            lb.styles.width = 16; lb.styles.color = "#ff00ff"
        
        for lbs in self.query(".re_label_sm"):
            lbs.styles.width = 8; lbs.styles.margin_left = 1; lbs.styles.color = "#ff00ff"

        for inp in self.query(".re_input"):
            inp.styles.width = 8; inp.styles.height = 1
        
        for inps in self.query(".re_input_sm"):
            inps.styles.width = 5; inps.styles.height = 1

        for unit in self.query(".re_unit"):
            unit.styles.margin = (0, 1); unit.styles.color = "#666"

        for hint in self.query(".re_hint"):
            hint.styles.margin = (0, 0, 1, 16); hint.styles.color = "#444"; hint.styles.text_style = "italic"

        self.query_one(".re_info").styles.text_align = "center"; self.query_one(".re_info").styles.margin = (0, 0)
        
        if self.main_app:
            re = self.main_app.value_reentry
            self.query_one("#cb_re_enabled").value = re.get("enabled", False)
            self.query_one("#inp_re_reset").value = str(int(re.get("reset_lvl", 0.52) * 100))
            self.query_one("#inp_re_move").value = str(float(re.get("reconfirm_move", 0.02) * 100))
            self.query_one("#inp_re_time").value = str(re.get("reconfirm_time", 10))
            self.query_one("#inp_re_size").value = str(int(re.get("size_mult", 0.3) * 100))
            self.query_one("#inp_re_gap").value = str(float(re.get("gap", 0.05) * 100))

    @on(Button.Pressed, "#btn_re_save")
    def save_settings(self):
        if self.main_app:
            try:
                re = self.main_app.value_reentry
                re["enabled"] = self.query_one("#cb_re_enabled").value
                re["reset_lvl"] = float(self.query_one("#inp_re_reset").value) / 100.0
                re["reconfirm_move"] = float(self.query_one("#inp_re_move").value) / 100.0
                re["reconfirm_time"] = int(self.query_one("#inp_re_time").value)
                re["size_mult"] = float(self.query_one("#inp_re_size").value) / 100.0
                re["gap"] = float(self.query_one("#inp_re_gap").value) / 100.0
                
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ Value Re-entry (RD2) Updated.", level="ADMIN")
            except Exception as e:
                self.main_app.log_msg(f"[red]Error saving Re-entry settings: {e}[/]")
        self.dismiss()


class LogFilterModal(ModalScreen):
    """A modal for managing console log categories and filtering modes."""
    BINDINGS = [("escape", "dismiss", "Dismiss")]
    def __init__(self, main_app=None):
        super().__init__()
        self.main_app = main_app
        self.tags = ["SYS", "SCAN", "EXEC", "RSLT", "ERR", "INF", "MARKET", "VOLAT", "BIAS", "STATS"]

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield Static("[bold #00ffff]Console Log Filters[/]", id="modal_title")
            
            with Vertical(classes="settings_group", id="log_mode_group"):
                yield Label("[bold]Filtering Mode:[/]")
                with RadioSet(id="rs_log_mode"):
                    yield RadioButton("Show All (No Filter)", id="rb_log_all", value=(self.main_app.log_display_mode == "ALL"))
                    yield RadioButton("Hide Selected Tags", id="rb_log_hide", value=(self.main_app.log_display_mode == "HIDE"))
                    yield RadioButton("Only Show Selected Tags", id="rb_log_only", value=(self.main_app.log_display_mode == "ONLY"))

            yield Label("[bold]Select Categories:[/]")
            with Container(id="log_tag_grid"):
                for tag in self.tags:
                    is_checked = tag in self.main_app.log_display_filter
                    yield Checkbox(tag, id=f"cb_log_{tag.lower()}", value=is_checked)

            with Horizontal(id="modal_buttons"):
                yield Button("Apply", id="btn_save_logs", variant="primary")
                yield Button("Cancel", id="btn_cancel_logs")

    def on_mount(self) -> None:
        self.styles.align = ("center", "middle")
        
        container = self.query_one("#modal_container")
        container.styles.background = "#1a1a1a"
        container.styles.border = ("thick", "#00ffff")
        container.styles.padding = (1, 2)
        container.styles.width = 50
        container.styles.height = "auto"
        container.styles.align = ("center", "middle")
        
        title = self.query_one("#modal_title")
        title.styles.text_align = "center"
        title.styles.width = "100%"
        title.styles.margin = (0, 0, 1, 0)
        
        mode_group = self.query_one("#log_mode_group")
        mode_group.styles.margin = (0, 0, 1, 0)
        mode_group.styles.border = ("solid", "#333333")
        mode_group.styles.padding = 1
        
        tag_grid = self.query_one("#log_tag_grid")
        tag_grid.styles.height = "auto"
        tag_grid.styles.border = ("solid", "#333333")
        tag_grid.styles.padding = 1
        
        buttons = self.query_one("#modal_buttons")
        buttons.styles.margin = (1, 0, 0, 0)
        buttons.styles.align = ("center", "middle")
        buttons.styles.width = "100%"

    @on(Button.Pressed, "#btn_save_logs")
    def action_save(self) -> None:
        try:
            # Update Mode
            rs = self.query_one("#rs_log_mode")
            if rs.pressed_button:
                if rs.pressed_button.id == "rb_log_all": self.main_app.log_display_mode = "ALL"
                elif rs.pressed_button.id == "rb_log_hide": self.main_app.log_display_mode = "HIDE"
                elif rs.pressed_button.id == "rb_log_only": self.main_app.log_display_mode = "ONLY"

            # Update Filter Set
            new_filter = set()
            for tag in self.tags:
                if self.query_one(f"#cb_log_{tag.lower()}").value:
                    new_filter.add(tag)
            
            self.main_app.log_display_filter = new_filter
            self.main_app.save_settings()
            
            # Trigger retroactive filtering
            self.main_app.rebuild_rich_log()
            
            mode_str = self.main_app.log_display_mode
            count = len(new_filter)
            self.main_app.log_msg(f"[bold cyan]LOG FILTERS APPLIED[/]: Mode={mode_str}, Tags={count}", level="SYS")
            self.dismiss(True)
        except Exception as e:
            self.main_app.log_msg(f"[red]Filter Save Error: {e}[/]")

    @on(Button.Pressed, "#btn_cancel_logs")
    def action_cancel(self) -> None:
        self.dismiss(False)


class DatabaseExplorerModal(ModalScreen):
    """A modal to explore the SQLite database tables."""
    BINDINGS = [("escape", "dismiss", "Dismiss")]

    def __init__(self, main_app=None):
        super().__init__()
        self.main_app = main_app
        self.db_path = DB_PATH
        self.current_table = "windows"

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield Static("[bold #00ffff]🗄 Database Explorer[/]", id="modal_title")
            
            with Horizontal(classes="setting_row"):
                yield Label("Table:", classes="setting_label")
                yield Select([
                    ("Windows (Main)", "windows"),
                    ("Variant Results", "variant_results"),
                    ("Darwin Experiments", "darwin_experiments"),
                    ("Ticks (Last 100)", "ticks"),
                    ("Market Context", "market_context")
                ], id="sel_db_table", value=self.current_table, classes="setting_select")
            
            yield DataTable(id="db_table_view")
            
            with Horizontal(id="modal_footer"):
                yield Button("REFRESH", id="btn_db_refresh", variant="primary")
                yield Button("CLOSE", id="btn_modal_close")

    def on_mount(self):
        self.styles.align = ("center", "middle")
        container = self.query_one("#modal_container")
        container.styles.background = "#1a1a1a"
        container.styles.border = ("thick", "#00ffff")
        container.styles.padding = (1, 1)
        container.styles.width = "90%"
        container.styles.height = "90%"
        
        table = self.query_one("#db_table_view")
        table.styles.height = "1fr"
        table.styles.border = ("solid", "#333333")
        table.styles.margin = (1, 0)
        
        self.refresh_data()

    def refresh_data(self):
        table = self.query_one("#db_table_view")
        table.clear(columns=True)
        
        if not os.path.exists(self.db_path):
            self.main_app.log_msg(f"[red]DB Explorer:[/] Database file not found at {self.db_path}")
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = f"SELECT * FROM {self.current_table}"
            if self.current_table == "ticks":
                query += " ORDER BY id DESC LIMIT 100"
            else:
                query += " ORDER BY rowid DESC LIMIT 100"
                
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # Get column names
            cursor.execute(f"PRAGMA table_info({self.current_table})")
            cols = [col[1] for col in cursor.fetchall()]
            
            table.add_columns(*cols)
            table.add_rows(rows)
            
            conn.close()
        except Exception as e:
            self.main_app.log_msg(f"[red]DB Explorer Error:[/] {e}")

    @on(Select.Changed, "#sel_db_table")
    def on_table_change(self, event: Select.Changed):
        self.current_table = event.value
        self.refresh_data()

    @on(Button.Pressed, "#btn_db_refresh")
    def on_refresh_click(self):
        self.refresh_data()

    @on(Button.Pressed, "#btn_modal_close")
    def action_dismiss(self):
        self.dismiss()


class SlopeSelectorWidget(Static):
    """
    A graphical widget to select a slope value via drag-and-drop.
    """
    def __init__(self, initial_slope=0.0001, **kwargs):
        super().__init__(**kwargs)
        self.can_focus = True
        self.slope = initial_slope
        self.is_dragging = False
        self.display_width = 40
        self.display_height = 10
        self.max_slope = 0.01
        self._update_coords_from_slope()

    def _update_coords_from_slope(self):
        # Origin is at (2, height-2)
        # We'll fix end_x to the right side of the axis
        self.end_x = self.display_width - 5
        # slope = dy / dx => dy = slope * dx
        # Normalized: slope max_slope should reach height-2
        # Max dy achievable visual is display_height - 3
        max_dy = self.display_height - 3
        self.end_y = (self.slope / self.max_slope) * max_dy
        self.end_y = max(0, min(max_dy, self.end_y))

    def _calculate_slope_from_mouse(self, x, y):
        # Origin is (2, display_height-2)
        dx = x - 2
        dy = (self.display_height - 2) - y
        if dx <= 0: return 0.0
        
        # We need the ratio. Max visual ratio is (height-3)/(width-5)
        max_visual_ratio = (self.display_height - 3) / (self.display_width - 5)
        raw_ratio = dy / dx
        
        # Scale to max_slope
        calculated = (raw_ratio / max_visual_ratio) * self.max_slope
        return max(0.0, min(self.max_slope, calculated))

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self.is_dragging = True
        self._handle_mouse(event.x, event.y)
        self.capture_mouse()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self.is_dragging:
            self._handle_mouse(event.x, event.y)

    def on_mouse_up(self, event: events.MouseUp) -> None:
        self.is_dragging = False
        self.release_mouse()

    def _handle_mouse(self, x, y):
        self.slope = self._calculate_slope_from_mouse(x, y)
        self._update_coords_from_slope()
        self.refresh()
        self.post_message(self.Changed(self, self.slope))

    class Changed(events.Message):
        def __init__(self, sender, value):
            super().__init__()
            self.sender = sender
            self.value = value

    def render(self) -> str:
        # Buffer for drawing
        grid = [[" " for _ in range(self.display_width)] for _ in range(self.display_height)]
        
        # Draw axes
        for x in range(2, self.display_width - 2):
            grid[self.display_height - 2][x] = "─"
        for y in range(1, self.display_height - 2):
            grid[y][2] = "│"
        grid[self.display_height - 2][2] = "└"
        
        # Draw line (Bresenham)
        x0, y0 = 2, self.display_height - 2
        x1, y1 = int(x0 + (self.display_width - 7)), int(y0 - self.end_y) # Use fixed X for display
        
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        
        cx, cy = x0, y0
        while True:
            if 0 <= cx < self.display_width and 0 <= cy < self.display_height:
                if grid[cy][cx] in [" ", "─", "│"]:
                    grid[cy][cx] = "•"
            if cx == x1 and cy == y1: break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                cx += sx
            if e2 <= dx:
                err += dx
                cy += sy
        
        return "\n".join(["".join(row) for row in grid])


class PTPSettingsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.s = main_app.scanners.get("PeakToPeak")
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_ptp"):
            yield Label("Peak-To-Peak Configuration", id="dialog_ptp_title")
            yield Label("Drag the line to adjust minimum trigger slope.", classes="dialog_subtitle")
            
            with Vertical(id="ptp_form_area"):
                with Vertical(id="ptp_graph_box"):
                    yield Label("MIN SLOPE SELECTOR", id="ptp_graph_title")
                    initial_slope = getattr(self.s, "min_slope", 0.0001) if self.s else 0.0001
                    yield SlopeSelectorWidget(initial_slope=initial_slope, id="ptp_slope_selector")
                    yield Label(f"Current Value: {initial_slope:.6f}", id="ptp_slope_display")
                
                with Horizontal(classes="ptp_row"):
                    yield Label("Prominence (¢):", classes="ptp_lbl")
                    val = str(getattr(self.s, "prominence", 2.0)) if self.s else "2.0"
                    yield Input(placeholder="2.0", value=val, id="ptp_prominence", classes="ptp_inp")
                with Horizontal(classes="ptp_row"):
                    yield Label("Eval Window (%):", classes="ptp_lbl")
                    val = str(int(getattr(self.s, "t_mid_pct", 0.5) * 100)) if self.s else "50"
                    yield Input(placeholder="50", value=val, id="ptp_t_mid_pct", classes="ptp_inp")
                with Horizontal(classes="ptp_row"):
                    yield Label("Breakdown (¢):", classes="ptp_lbl")
                    val = str(getattr(self.s, "breakdown_tolerance", 5.0)) if self.s else "5.0"
                    yield Input(placeholder="5.0", value=val, id="ptp_breakdown", classes="ptp_inp")
            
            with Horizontal(id="dialog_ptp_buttons"):
                yield Button("Reset", id="btn_ptp_reset", variant="warning")
                yield Button("Apply & Save", id="btn_ptp_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_ptp")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("thick", "cyan")
        d.styles.padding = (1, 2)
        d.styles.width = 64
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#ptp_graph_title").styles.text_align = "center"
        self.query_one("#ptp_graph_title").styles.color = "cyan"
        self.query_one("#ptp_graph_title").styles.text_style = "bold"
        
        self.query_one("#ptp_slope_display").styles.text_align = "center"
        self.query_one("#ptp_slope_display").styles.color = "#ffaa00"
        self.query_one("#ptp_slope_display").styles.margin = (0, 0, 1, 0)
        
        sel = self.query_one("#ptp_slope_selector")
        sel.styles.width = 40
        sel.styles.height = 10
        sel.styles.border = ("solid", "#333")
        sel.styles.background = "#000"
        sel.styles.margin = (1, 10) # Center the 40-width widget in 64-width modal
        
        for row in self.query(".ptp_row"):
            row.styles.height = 3
            row.styles.align = ("left", "middle")
            
        for lbl in self.query(".ptp_lbl"):
            lbl.styles.width = 24
            lbl.styles.content_align = ("right", "middle")
            
        for inp in self.query(".ptp_inp"):
            inp.styles.width = 12
            
        btn_row = self.query_one("#dialog_ptp_buttons")
        btn_row.styles.align = ("center", "middle")
        btn_row.styles.margin = (1, 0, 0, 0)
        btn_row.styles.height = 3

    def on_slope_selector_changed(self, message: SlopeSelectorWidget.Changed):
        self.query_one("#ptp_slope_display").update(f"Current Value: {message.value:.6f}")

    @on(Button.Pressed, "#btn_ptp_reset")
    def _reset_settings(self):
        sel = self.query_one("#ptp_slope_selector")
        sel.slope = 0.0001
        sel._update_coords_from_slope()
        sel.refresh()
        self.query_one("#ptp_slope_display").update("Current Value: 0.000100")
        self.query_one("#ptp_prominence").value = "2.0"
        self.query_one("#ptp_t_mid_pct").value = "50"
        self.query_one("#ptp_breakdown").value = "5.0"

    @on(Button.Pressed, "#btn_ptp_save")
    def save_and_close(self):
        try:
            slope = self.query_one("#ptp_slope_selector").slope
            if self.s:
                self.s.min_slope = slope
                self.s.prominence = float(self.query_one("#ptp_prominence").value)
                self.s.t_mid_pct = float(self.query_one("#ptp_t_mid_pct").value) / 100.0
                self.s.breakdown_tolerance = float(self.query_one("#ptp_breakdown").value)
                
            if self.main_app:
                self.main_app.ptp_settings = {
                    "min_slope": slope,
                    "prominence": float(self.query_one("#ptp_prominence").value),
                    "t_mid_pct": float(self.query_one("#ptp_t_mid_pct").value) / 100.0,
                    "breakdown_tolerance": float(self.query_one("#ptp_breakdown").value),
                }
                self.main_app.save_settings()
                self.main_app.log_msg(f"⚙️ PTP Config Updated", level="ADMIN")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving PTP: {e}", level="ERROR")
        self.dismiss()

class SonificationSettingsModal(ModalScreen):
    """Configuration suite for audio pings."""
    BINDINGS = [("escape", "dismiss", "Close Modal")]
    
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.sets = main_app.sonification_settings
        
    def compose(self) -> ComposeResult:
        with Container(id="dialog_audio"):
            yield Label("Audio Synth Configuration", id="dialog_audio_title")
            yield Label("Tune the pitch and rhythm of market ticks.", classes="dialog_subtitle")
            
            with Vertical(id="audio_form_area"):
                with Horizontal(classes="audio_row"):
                    yield Label("Base Freq (Hz):", classes="audio_lbl")
                    yield Input(placeholder="800", value=str(self.sets.get("base_freq", 800)), id="audio_base_freq", classes="audio_inp")
                
                with Horizontal(classes="audio_row"):
                    yield Label("Duration (ms):", classes="audio_lbl")
                    yield Input(placeholder="50", value=str(self.sets.get("duration", 50)), id="audio_duration", classes="audio_inp")
                
                with Horizontal(classes="audio_row"):
                    yield Label("Sensitivity (Hz):", classes="audio_lbl")
                    yield Input(placeholder="10.0", value=str(self.sets.get("sensitivity", 10.0)), id="audio_sensitivity", classes="audio_inp")
                    
                with Horizontal(classes="audio_row"):
                    yield Label("Pitch Jump (x):", classes="audio_lbl")
                    yield Input(placeholder="1.5", value=str(self.sets.get("pitch_jump", 1.5)), id="audio_pitch_jump", classes="audio_inp")
                
                with Horizontal(classes="audio_row"):
                    yield Label("Chirp Style:", classes="audio_lbl")
                    yield Select([("Single Note", "single"), ("Double Chirp", "double"), ("Creative Arpeggio", "arpeggio")], 
                               value=self.sets.get("style", "double"), id="audio_style", classes="audio_sel")
                
                with Horizontal(classes="audio_row"):
                    yield Label("Sonic Glide (Ticks):", classes="audio_lbl")
                    yield Input(placeholder="0", value=str(self.sets.get("recap_freq", 0)), id="audio_recap_freq", classes="audio_inp")

                with Horizontal(classes="audio_row"):
                    yield Label("Archive Win Glide:", classes="audio_lbl")
                    yield Checkbox(value=self.sets.get("save_window_glide", False), id="audio_save_window", classes="audio_chk")

                with Horizontal(id="audio_test_buttons"):
                    yield Button("TEST UP (Major)", id="btn_test_up", variant="success")
                    yield Button("TEST DN (Minor)", id="btn_test_dn", variant="error")
            
            with Horizontal(id="dialog_audio_buttons"):
                yield Button("SAVE & CLOSE", id="btn_audio_save", variant="primary")

    def on_mount(self):
        d = self.query_one("#dialog_audio")
        d.styles.background = "#1B1B1D"
        d.styles.border = ("thick", "#00ff88")
        d.styles.padding = (1, 2)
        d.styles.width = 60
        d.styles.height = "auto"
        d.styles.align = ("center", "middle")
        
        self.query_one("#dialog_audio_title").styles.text_align = "center"
        self.query_one("#dialog_audio_title").styles.color = "#00ff88"
        self.query_one("#dialog_audio_title").styles.text_style = "bold"
        self.query_one("#dialog_audio_title").styles.margin = (0, 0, 1, 0)

        for row in self.query(".audio_row"):
            row.styles.height = 3
            row.styles.align = ("left", "middle")
            
        for lbl in self.query(".audio_lbl"):
            lbl.styles.width = 24
            lbl.styles.content_align = ("right", "middle")
            
        for inp in self.query(".audio_inp, .audio_sel"):
            inp.styles.width = 16
            
        btn_row = self.query_one("#audio_test_buttons")
        btn_row.styles.align = ("center", "middle")
        btn_row.styles.margin = (1, 0)
        btn_row.styles.height = 3
        self.query_one("#btn_test_up").styles.margin = (0, 1)
        self.query_one("#btn_test_dn").styles.margin = (0, 1)

        save_row = self.query_one("#dialog_audio_buttons")
        save_row.styles.align = ("center", "middle")
        save_row.styles.margin = (1, 0, 0, 0)
        save_row.styles.height = 3

    @on(Button.Pressed, "#btn_test_up")
    def test_up(self):
        self._play_test(0.55, True)

    @on(Button.Pressed, "#btn_test_dn")
    def test_dn(self):
        self._play_test(0.45, False)

    def _play_test(self, price, is_up):
        try:
            bf = int(self.query_one("#audio_base_freq").value)
            dur = int(self.query_one("#audio_duration").value)
            sens = float(self.query_one("#audio_sensitivity").value)
            style = self.query_one("#audio_style").value
            jump = float(self.query_one("#audio_pitch_jump").value)
            
            # Simplified pitch logic for test
            shift = (price - 0.5) * 100 * sens
            root = int(bf + shift)
            root = max(37, min(root, 32767))
            
            style = str(style).lower()
            
            if style == "single":
                winsound.Beep(root, dur)
            elif style == "arpeggio":
                import random
                # Creative sequence (Ascending for Test)
                intervals = [1.0, 1.25, 1.5, 2.0] if is_up else [1.0, 1.2, 1.5]
                for mult in intervals:
                    f = int(root * mult)
                    winsound.Beep(max(37, min(f, 32767)), dur)
            else: # double
                if is_up:
                    winsound.Beep(root, dur)
                    winsound.Beep(int(root * jump), dur)
                else:
                    winsound.Beep(int(root * (jump * 0.8)), dur)
                    winsound.Beep(root, dur)
        except Exception: pass

    @on(Button.Pressed, "#btn_audio_save")
    def save_and_close(self):
        try:
            self.main_app.sonification_settings = {
                "base_freq": int(self.query_one("#audio_base_freq").value),
                "duration": int(self.query_one("#audio_duration").value),
                "sensitivity": float(self.query_one("#audio_sensitivity").value),
                "pitch_jump": float(self.query_one("#audio_pitch_jump").value),
                "style": self.query_one("#audio_style").value,
                "recap_freq": int(self.query_one("#audio_recap_freq").value or 0),
                "save_window_glide": self.query_one("#audio_save_window").value,
                "cooldown": self.sets.get("cooldown", 0.2)
            }
            self.main_app.save_settings()
            self.main_app.log_msg("⚙️ Audio Configuration Saved", level="SYS")
        except Exception as e:
            if self.main_app: self.main_app.log_msg(f"Error saving audio: {e}", level="ERROR")
        self.dismiss()
