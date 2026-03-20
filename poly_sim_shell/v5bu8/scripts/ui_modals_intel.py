from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Label, Input, Button
from textual import on

class BaseExpertModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Dismiss")]
    def __init__(self, main_app, title, subtitle):
        super().__init__()
        self.main_app = main_app
        self.title_text = title
        self.subtitle_text = subtitle

    def compose_header(self):
        yield Static(f"[bold cyan]{self.title_text}[/]", id="modal_title")
        yield Static(self.subtitle_text, id="modal_subtitle")

    def compose_footer(self):
        with Horizontal(id="modal_footer"):
            yield Button("SAVE & CLOSE", id="btn_save", variant="primary")

    def apply_styles(self):
        self.styles.align = ("center", "middle")
        c = self.query_one("#modal_container")
        c.styles.background = "#222222"
        c.styles.border = ("thick", "cyan")
        c.styles.padding = (1, 2)
        c.styles.width = 50
        c.styles.height = "auto"
        c.styles.align = ("center", "middle")
        
        self.query_one("#modal_title").styles.text_align = "center"
        self.query_one("#modal_title").styles.width = "100%"
        self.query_one("#modal_subtitle").styles.text_align = "center"
        self.query_one("#modal_subtitle").styles.width = "100%"
        self.query_one("#modal_subtitle").styles.color = "#888888"
        self.query_one("#modal_subtitle").styles.margin = (0, 0, 1, 0)
        
        footer = self.query_one("#modal_footer")
        footer.styles.align = ("center", "middle")
        footer.styles.width = "100%"
        footer.styles.margin = (1, 0, 0, 0)

    @on(Button.Pressed, "#btn_save")
    def on_save(self):
        self.save_logic()
        self.dismiss()

    def save_logic(self):
        pass

class WCPSettingsModal(BaseExpertModal):
    def __init__(self, main_app):
        super().__init__(main_app, "WCP: Window Candle Profiler", "Tune reversal pattern sensitivity.")

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield from self.compose_header()
            
            # Weight section
            with Vertical(classes="setting_section"):
                yield Static("[bold #00ff88]Algorithm Weight[/]", classes="section_title")
                yield Static("Multiplier applied to bet size when WCP triggers signals. Default: 1.0x", classes="help_text")
                with Horizontal():
                    yield Label("Weight Multiplier (x):")
                    yield Input(placeholder="1.0", id="inp_wcp_weight")
            
            # Pattern recognition settings
            with Vertical(classes="setting_section"):
                yield Static("[bold #ffff00]Pattern Recognition[/]", classes="section_title")
                yield Static("WCP analyzes candlestick patterns to identify potential reversals based on body and shadow ratios.", classes="help_text")
                with Horizontal(classes="modal_row"):
                    yield Label("Body Ratio Threshold:")
                    yield Input(id="inp_body_ratio", placeholder="0.30")
                    yield Static("(30% minimum body size)", classes="field_note")
                with Horizontal(classes="modal_row"):
                    yield Label("Shadow Ratio Threshold:")
                    yield Input(id="inp_shadow_ratio", placeholder="2.0")
                    yield Static("(2.0x shadow vs body)", classes="field_note")
            
            yield from self.compose_footer()

    def on_mount(self):
        self.apply_styles()
        sc = self.main_app.scanners.get("WCP")
        if sc:
            self.query_one("#inp_body_ratio").value = str(getattr(sc, "body_ratio_thresh", 0.30))
            self.query_one("#inp_shadow_ratio").value = str(getattr(sc, "shadow_ratio_thresh", 2.0))
            # Load weight setting
            weight = self.main_app.scanner_weights.get("WCP", 1.0)
            self.query_one("#inp_wcp_weight").value = str(weight)

    def save_logic(self):
        sc = self.main_app.scanners.get("WCP")
        if sc:
            try:
                # Save pattern settings
                sc.body_ratio_thresh = float(self.query_one("#inp_body_ratio").value)
                sc.shadow_ratio_thresh = float(self.query_one("#inp_shadow_ratio").value)
                
                # Save weight setting
                weight = float(self.query_one("#inp_wcp_weight").value)
                self.main_app.scanner_weights["WCP"] = weight
                self.main_app.save_settings()
                
                self.main_app.log_msg("⚙️ WCP Settings Updated", level="ADMIN")
            except: pass

class VPOCSettingsModal(BaseExpertModal):
    def __init__(self, main_app):
        super().__init__(main_app, "VPOC: Volume POC Analyzer", "Identify price 'thinness' relative to value.")

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield from self.compose_header()
            
            # Weight section
            with Vertical(classes="setting_section"):
                yield Static("[bold #00ff88]Algorithm Weight[/]", classes="section_title")
                yield Static("Multiplier applied to bet size when VPOC triggers signals. Default: 1.0x", classes="help_text")
                with Horizontal():
                    yield Label("Weight Multiplier (x):")
                    yield Input(placeholder="1.0", id="inp_vpoc_weight")
            
            # Volume analysis settings
            with Vertical(classes="setting_section"):
                yield Static("[bold #ffff00]Volume Analysis[/]", classes="section_title")
                yield Static("VPOC identifies when price moves away from established value areas, indicating potential reversals.", classes="help_text")
                with Horizontal(classes="modal_row"):
                    yield Label("Deviation Threshold (%):")
                    yield Input(id="inp_vpo_dev", placeholder="0.05")
                    yield Static("(0.05% = 0.0005 decimal)", classes="field_note")
            
            yield from self.compose_footer()

    def on_mount(self):
        self.apply_styles()
        sc = self.main_app.scanners.get("VPOC")
        if sc:
            self.query_one("#inp_vpo_dev").value = str(getattr(sc, "dev_threshold", 0.0005) * 100)
            # Load weight setting
            weight = self.main_app.scanner_weights.get("VPOC", 1.0)
            self.query_one("#inp_vpoc_weight").value = str(weight)

    def save_logic(self):
        sc = self.main_app.scanners.get("VPOC")
        if sc:
            try:
                # Save volume settings
                sc.dev_threshold = float(self.query_one("#inp_vpo_dev").value) / 100.0
                
                # Save weight setting
                weight = float(self.query_one("#inp_vpoc_weight").value)
                self.main_app.scanner_weights["VPOC"] = weight
                self.main_app.save_settings()
                
                self.main_app.log_msg("⚙️ VPOC Settings Updated", level="ADMIN")
            except: pass

class SDPSettingsModal(BaseExpertModal):
    def __init__(self, main_app):
        super().__init__(main_app, "SDP: Settlement Drift Predictor", "Detect basis gap anomalies at rollover.")

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield from self.compose_header()
            
            # Weight section
            with Vertical(classes="setting_section"):
                yield Static("[bold #00ff88]Algorithm Weight[/]", classes="section_title")
                yield Static("Multiplier applied to bet size when SDP triggers signals. Default: 1.0x", classes="help_text")
                with Horizontal():
                    yield Label("Weight Multiplier (x):")
                    yield Input(placeholder="1.0", id="inp_sdp_weight")
            
            # Drift detection settings
            with Vertical(classes="setting_section"):
                yield Static("[bold #ffff00]Drift Detection[/]", classes="section_title")
                yield Static("SDP monitors basis gaps between windows to detect settlement anomalies and price reversals.", classes="help_text")
                with Horizontal(classes="modal_row"):
                    yield Label("Drift Threshold (¢):")
                    yield Input(id="inp_sdp_drift", placeholder="5.0")
                    yield Static("(5 cents minimum drift)", classes="field_note")
            
            yield from self.compose_footer()

    def on_mount(self):
        self.apply_styles()
        sc = self.main_app.scanners.get("SDP")
        if sc:
            self.query_one("#inp_sdp_drift").value = str(getattr(sc, "drift_threshold", 0.05) * 100)
            # Load weight setting
            weight = self.main_app.scanner_weights.get("SDP", 1.0)
            self.query_one("#inp_sdp_weight").value = str(weight)

    def save_logic(self):
        sc = self.main_app.scanners.get("SDP")
        if sc:
            try:
                # Save drift settings
                sc.drift_threshold = float(self.query_one("#inp_sdp_drift").value) / 100.0
                
                # Save weight setting
                weight = float(self.query_one("#inp_sdp_weight").value)
                self.main_app.scanner_weights["SDP"] = weight
                self.main_app.save_settings()
                
                self.main_app.log_msg("⚙️ SDP Settings Updated", level="ADMIN")
            except: pass

class DIVSettingsModal(BaseExpertModal):
    def __init__(self, main_app):
        super().__init__(main_app, "DIV: Sentiment Divergence", "Spot human sentiment bubbles vs BTC move.")

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield from self.compose_header()
            
            # Weight section
            with Vertical(classes="setting_section"):
                yield Static("[bold #00ff88]Algorithm Weight[/]", classes="section_title")
                yield Static("Multiplier applied to bet size when DIV triggers signals. Default: 1.0x", classes="help_text")
                with Horizontal():
                    yield Label("Weight Multiplier (x):")
                    yield Input(placeholder="1.0", id="inp_div_weight")
            
            # Sentiment analysis settings
            with Vertical(classes="setting_section"):
                yield Static("[bold #ffff00]Sentiment Analysis[/]", classes="section_title")
                yield Static("DIV identifies when human sentiment diverges from actual BTC price movement, indicating potential reversals.", classes="help_text")
                with Horizontal(classes="modal_row"):
                    yield Label("Divergence Intensity:")
                    yield Input(id="inp_div_thresh", placeholder="5.0")
                    yield Static("(5.0 minimum intensity)", classes="field_note")
            
            yield from self.compose_footer()

    def on_mount(self):
        self.apply_styles()
        sc = self.main_app.scanners.get("DIV")
        if sc:
            self.query_one("#inp_div_thresh").value = str(getattr(sc, "div_threshold", 5.0))
            # Load weight setting
            weight = self.main_app.scanner_weights.get("DIV", 1.0)
            self.query_one("#inp_div_weight").value = str(weight)

    def save_logic(self):
        sc = self.main_app.scanners.get("DIV")
        if sc:
            try:
                # Save sentiment settings
                sc.div_threshold = float(self.query_one("#inp_div_thresh").value)
                
                # Save weight setting
                weight = float(self.query_one("#inp_div_weight").value)
                self.main_app.scanner_weights["DIV"] = weight
                self.main_app.save_settings()
                
                self.main_app.log_msg("⚙️ DIV Settings Updated", level="ADMIN")
            except: pass

class SSISettingsModal(BaseExpertModal):
    def __init__(self, main_app):
        super().__init__(main_app, "SSI: Strategy Inversion", "Anti-regime protection via signal flipping.")

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield from self.compose_header()
            
            # Weight section
            with Vertical(classes="setting_section"):
                yield Static("[bold #00ff88]Algorithm Weight[/]", classes="section_title")
                yield Static("Multiplier applied to bet size when SSI triggers signals. Default: 1.0x", classes="help_text")
                with Horizontal():
                    yield Label("Weight Multiplier (x):")
                    yield Input(placeholder="1.0", id="inp_ssi_weight")
            
            # Strategy inversion settings
            with Vertical(classes="setting_section"):
                yield Static("[bold #ffff00]Strategy Inversion[/]", classes="section_title")
                yield Static("SSI automatically flips trading signals during losing streaks to protect against adverse market regimes.", classes="help_text")
                with Horizontal(classes="modal_row"):
                    yield Label("Loss Streak Trigger:")
                    yield Input(id="inp_ssi_streak", placeholder="3")
                    yield Static("(3 consecutive losses)", classes="field_note")
            
            yield from self.compose_footer()

    def on_mount(self):
        self.apply_styles()
        sc = self.main_app.scanners.get("SSI")
        if sc:
            self.query_one("#inp_ssi_streak").value = str(getattr(sc, "loss_streak_threshold", 3))
            # Load weight setting
            weight = self.main_app.scanner_weights.get("SSI", 1.0)
            self.query_one("#inp_ssi_weight").value = str(weight)

    def save_logic(self):
        sc = self.main_app.scanners.get("SSI")
        if sc:
            try:
                # Save inversion settings
                sc.loss_streak_threshold = int(self.query_one("#inp_ssi_streak").value)
                
                # Save weight setting
                weight = float(self.query_one("#inp_ssi_weight").value)
                self.main_app.scanner_weights["SSI"] = weight
                self.main_app.save_settings()
                
                self.main_app.log_msg("⚙️ SSI Settings Updated", level="ADMIN")
            except: pass
