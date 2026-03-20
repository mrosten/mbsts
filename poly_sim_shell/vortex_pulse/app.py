import time
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

import asyncio
import json
import os
import csv
from datetime import datetime, timezone
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Button, RichLog, Label, Checkbox, RadioButton, RadioSet, Static, Collapsible
from textual import work, on, events
from rich.text import Text

# Handle imports for both package and direct execution
try:
    from .config import TradingConfig, POLYGON_RPC_LIST, CHAINLINK_BTC_FEED, CHAINLINK_ABI
    from .market import MarketDataManager, calculate_rsi, calculate_bb, calculate_atr
    from .risk import RiskManager, AlgorithmPortfolio
    from .broker import TradeExecutor
    from .scanners import ALGO_INFO
    from .scanners import (
        NPatternScanner, FakeoutScanner, MomentumScanner, RsiScanner, TrapCandleScanner,
        MidGameScanner, LateReversalScanner, StaircaseBreakoutScanner, PostPumpScanner,
        StepClimberScanner, SlingshotScanner, MinOneScanner, LiquidityVacuumScanner,
        CobraScanner, NitroScanner, BullFlagScanner, HdoScanner, Momentum2Scanner,
        BriefingScanner, CoiledCobraScanner, MesaCollapseScanner, MeanReversionScanner,
        GrindSnapScanner, VolCheckScanner, MosheSpecializedScanner, ZScoreBreakoutScanner,
        VolSnapScanner, ShallowSymmetricalContinuationScanner, AsymmetricDoubleTestScanner
    )
    from .darwin_agent import DarwinAgent
    from .ui_modals import (
        GlobalSettingsModal, AlgoInfoModal, BullFlagSettingsModal,
        BankrollExhaustedModal, MOMExpertModal, ResearchLogger, CCOExpertModal,
        ManualFreezeModal, CommandHelpModal, GRISettingsModal,
        RSISettingsModal, TRASettingsModal, MIDSettingsModal,
        LATSettingsModal, POSSettingsModal, STESettingsModal,
        SLISettingsModal, MINSettingsModal, LIQSettingsModal,
        COBSettingsModal, MESSettingsModal, NPASettingsModal,
        FAKSettingsModal, MEASettingsModal, VOLSettingsModal,
        TrendEfficiencyModal, ConvictionScalingModal,
        BRISettingsModal, ZSCSettingsModal, SSCSettingsModal, ADTSettingsModal,
        MM2SettingsModal, DarwinSettingsModal
    )
    from .ui_modals_intel import (
        WCPSettingsModal, VPOCSettingsModal, SDPSettingsModal,
        DIVSettingsModal, SSISettingsModal
    )
    from .trade_engine import TradeEngineMixin
    from .intel_scanners import (
        WindowCandleProfiler, VPOCAnalyzer, SettlementDriftPredictor,
        SentimentDivergenceScanner, StrategyInversionScanner
    )
    from .ftp_manager import FTPManager
except ImportError:
    # Running directly from vortex_pulse directory
    from config import TradingConfig, POLYGON_RPC_LIST, CHAINLINK_BTC_FEED, CHAINLINK_ABI
    from market import MarketDataManager, calculate_rsi, calculate_bb, calculate_atr
    from risk import RiskManager, AlgorithmPortfolio
    from broker import TradeExecutor
    from scanners import ALGO_INFO
    from scanners import (
        NPatternScanner, FakeoutScanner, MomentumScanner, RsiScanner, TrapCandleScanner,
        MidGameScanner, LateReversalScanner, StaircaseBreakoutScanner, PostPumpScanner,
        StepClimberScanner, SlingshotScanner, MinOneScanner, LiquidityVacuumScanner,
        CobraScanner, NitroScanner, BullFlagScanner, HdoScanner, Momentum2Scanner,
        BriefingScanner, CoiledCobraScanner, MesaCollapseScanner, MeanReversionScanner,
        GrindSnapScanner, VolCheckScanner, MosheSpecializedScanner, ZScoreBreakoutScanner,
        VolSnapScanner, ShallowSymmetricalContinuationScanner, AsymmetricDoubleTestScanner
    )
    from darwin_agent import DarwinAgent
    from ui_modals import (
        GlobalSettingsModal, AlgoInfoModal, BullFlagSettingsModal,
        BankrollExhaustedModal, MOMExpertModal, ResearchLogger, CCOExpertModal,
        ManualFreezeModal, CommandHelpModal, GRISettingsModal,
        RSISettingsModal, TRASettingsModal, MIDSettingsModal,
        LATSettingsModal, POSSettingsModal, STESettingsModal,
        SLISettingsModal, MINSettingsModal, LIQSettingsModal,
        COBSettingsModal, MESSettingsModal, NPASettingsModal,
        FAKSettingsModal, MEASettingsModal, VOLSettingsModal,
        TrendEfficiencyModal, ConvictionScalingModal,
        BRISettingsModal, ZSCSettingsModal, SSCSettingsModal, ADTSettingsModal,
        MM2SettingsModal, DarwinSettingsModal
    )
    from ui_modals_intel import (
        WCPSettingsModal, VPOCSettingsModal, SDPSettingsModal,
        DIVSettingsModal, SSISettingsModal
    )
    from trade_engine import TradeEngineMixin
    from intel_scanners import (
        WindowCandleProfiler, VPOCAnalyzer, SettlementDriftPredictor,
        SentimentDivergenceScanner, StrategyInversionScanner
    )
    from ftp_manager import FTPManager


class PulseLeanChart(Static):
    """
    High-resolution market leaning chart using Braille characters.
    Tracks UP price (0-100) as a single line.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.history = []
        self.trigger_events = [] # [(elapsed, value, side, scanner_name)]
        self.tilt_events = []    # [(elapsed, direction, magnitude)] — 52/48 tilt markers
        self.duration = 300 # Default to 5m

    def push_value(self, elapsed, value):
        # elapsed: seconds into current window
        # value: 0.0 - 1.0 (UP Price)
        self.history.append((elapsed, value))
        self.refresh()

    def push_trigger(self, elapsed, value, side, scanner_name):
        self.trigger_events.append((elapsed, value, side, scanner_name))
        self.refresh()

    def push_tilt(self, elapsed, direction, magnitude):
        """Record a 52/48+ market tilt at the given elapsed time.
        direction: 'UP' or 'DOWN'
        magnitude: the dominant side's price in cents (e.g. 53)
        """
        self.tilt_events.append((elapsed, direction, magnitude))
        self.refresh()

    def reset(self):
        self.history = []
        self.trigger_events = []
        self.tilt_events = []
        self.refresh()

    def render(self):
        if not self.history:
            return Text("Lean Chart: Syncing...", style="dim yellow")
        
        w = self.size.width
        h = self.size.height
        if w <= 0 or h <= 0: return ""
        
        pixel_w = w * 2
        pixel_h = h * 4
        
        grid = [[(0, 0) for _ in range(w)] for _ in range(h)]
        dot_bit_map = [[0, 3], [1, 4], [2, 5], [6, 7]]

        # 1. Plot Dotted Center Line (50c)
        mid_py = pixel_h // 2
        mid_cy, mid_dr = mid_py // 4, mid_py % 4
        for x in range(pixel_w):
            if x % 4 == 0:
                cx, dc = x // 2, x % 2
                c_bits, p_bits = grid[mid_cy][cx]
                grid[mid_cy][cx] = (c_bits | (1 << dot_bit_map[mid_dr][dc]), p_bits)

        # 2. Plot Price History (Left-to-Right mapping)
        duration = getattr(self.app.config, "WINDOW_SECONDS", self.duration)
        points = self.history
        if points and points[0][0] > 0:
            points = [(0, points[0][1])] + points

        prev_px, prev_py = None, None
        for elapsed, val in points:
            px = int((elapsed / duration) * (pixel_w - 1))
            px = max(0, min(px, pixel_w - 1))
            py = int((1.0 - val) * (pixel_h - 1))
            py = max(0, min(py, pixel_h - 1))
            
            if prev_px is not None:
                dx, dy = px - prev_px, py - prev_py
                steps = max(abs(dx), abs(dy))
                for s in range(steps + 1):
                    interp_x = prev_px + int(s * dx / steps) if steps > 0 else px
                    interp_y = prev_py + int(s * dy / steps) if steps > 0 else py
                    cy, dr = interp_y // 4, interp_y % 4
                    cx, dc = interp_x // 2, interp_x % 2
                    if 0 <= cy < h and 0 <= cx < w:
                        c_bits, p_bits = grid[cy][cx]
                        grid[cy][cx] = (c_bits, p_bits | (1 << dot_bit_map[dr][dc]))
            else:
                cy, dr = py // 4, py % 4
                cx, dc = px // 2, px % 2
                if 0 <= cy < h and 0 <= cx < w:
                    c_bits, p_bits = grid[cy][cx]
                    grid[cy][cx] = (c_bits, p_bits | (1 << dot_bit_map[dr][dc]))
            prev_px, prev_py = px, py

        # 3. Mark Trigger Pips for Console (v5.9.13)
        # Store (x, y, style) for each trigger to overlay after the braille grid is built
        console_triggers = {}
        for elapsed, val, side, scanner in self.trigger_events:
            cx = int((elapsed / duration) * (w - 1))
            cy = int((1.0 - val) * (h - 1))
            cx = max(0, min(cx, w - 1))
            cy = max(0, min(cy, h - 1))
            style = "bold #00ff00" if "UP" in side else "bold #ff0000"
            console_triggers[(cx, cy)] = ("●", style)

        # 3b. Mark Tilt Indicators — vertical stripe of arrows at tilt time
        tilt_cols = {}  # cx -> (char, style)
        for elapsed, direction, magnitude in self.tilt_events:
            cx = int((elapsed / duration) * (w - 1))
            cx = max(0, min(cx, w - 1))
            char = "▲" if direction == "UP" else "▼"
            style = "bold #00ffff" if direction == "UP" else "bold #ff00ff"
            tilt_cols[cx] = (char, style)

        # 4. Build Rich Text output
        output = Text()
        for y in range(h):
            for x in range(w):
                if (x, y) in console_triggers:
                    char, style = console_triggers[(x, y)]
                    output.append(char, style=style)
                    continue
                # Tilt column: draw on every row
                if x in tilt_cols:
                    char, style = tilt_cols[x]
                    output.append(char, style=style)
                    continue

                c_bits, p_bits = grid[y][x]
                if p_bits > 0:
                    char = chr(0x2800 + (c_bits | p_bits))
                    output.append(char, style="bold #ffff00")
                elif c_bits > 0:
                    char = chr(0x2800 + c_bits)
                    output.append(char, style="#444444")
                else:
                    output.append(" ")
            if y < h - 1:
                output.append("\n")
                
        return output

    def save_graph_svg(self, path):
        """Generates a high-quality SVG with Hover Tooltips (v5.9.13)."""
        try:
            img_w, img_h = 300, 150
            pad = 20
            duration = getattr(self.app.config, "WINDOW_SECONDS", 300)
            
            svg = [f'<svg width="{img_w + pad*2}" height="{img_h + pad*2}" xmlns="http://www.w3.org/2000/svg" style="overflow:visible">']
            # Inline CSS for hover tooltips on trade dots
            svg.append('<style>.trade-dot:hover .dot-tip { opacity: 1 !important; } .trade-dot { cursor: crosshair; }</style>')
            # Background
            svg.append(f'<rect width="{img_w + pad*2}" height="{img_h + pad*2}" fill="#121212" />')
            
            # Grid Lines
            for i in [2, 4, 5, 6, 8]:
                y_val = i / 10.0
                y_px = pad + int((1.0 - y_val) * (img_h - 1))
                color = "#3C3C3C" if i == 5 else "#232323"
                svg.append(f'<line x1="{pad}" y1="{y_px}" x2="{img_w + pad}" y2="{y_px}" stroke="{color}" stroke-width="1" />')
            
            mid_px = pad + int(0.5 * (img_w - 1))
            svg.append(f'<line x1="{mid_px}" y1="{pad}" x2="{mid_px}" y2="{img_h + pad}" stroke="#232323" stroke-width="1" />')

            # Price Line
            points = self.history
            if points:
                if points[0][0] > 0: points = [(0, points[0][1])] + points
                polyline_pts = []
                for elapsed, val in points:
                    x = pad + int((elapsed / duration) * (img_w - 1))
                    y = pad + int((1.0 - val) * (img_h - 1))
                    polyline_pts.append(f"{x},{y}")
                svg.append(f'<polyline points="{" ".join(polyline_pts)}" fill="none" stroke="#FFFF00" stroke-width="2" stroke-linejoin="round" />')

            # Tilt Indicators (52/48+) — vertical dashed lines with direction badge
            for elapsed, direction, magnitude in self.tilt_events:
                tx = pad + int((elapsed / duration) * (img_w - 1))
                tilt_color = "#00FFFF" if direction == "UP" else "#FF00FF"
                tilt_char = "▲" if direction == "UP" else "▼"
                tilt_label = f"{tilt_char}{direction} {magnitude}¢"
                svg.append(f'<line x1="{tx}" y1="{pad}" x2="{tx}" y2="{img_h + pad}" stroke="{tilt_color}" stroke-width="1" stroke-dasharray="3,3" opacity="0.8">')
                svg.append(f'  <title>Next window tilt: {tilt_label}</title>')
                svg.append(f'</line>')
                # Small badge at top of line
                badge_x = min(tx + 2, img_w + pad - 50)
                svg.append(f'<rect x="{badge_x - 1}" y="{pad}" width="{len(tilt_label)*6+4}" height="11" rx="2" fill="#000000" fill-opacity="0.8" stroke="{tilt_color}" stroke-width="1"/>')
                svg.append(f'<text x="{badge_x+1}" y="{pad + 9}" font-size="8" fill="{tilt_color}" font-family="monospace" font-weight="bold">{tilt_label}</text>')

            # Trigger Pips (The "Smart Pips")
            for i, (elapsed, val, side, scanner) in enumerate(self.trigger_events):
                x = pad + int((elapsed / duration) * (img_w - 1))
                y = pad + int((1.0 - val) * (img_h - 1))
                color = "#00FF00" if "UP" in side else "#FF0000"
                label = f"{scanner}: {side} @ {int(val*100)}¢"
                # Tooltip box dimensions
                tx = min(x + 6, img_w + pad - 80)  # keep tooltip inside SVG
                ty = max(y - 18, pad)
                tooltip_id = f"tip_{i}"
                # The circle dot — native title for Firefox/basic hover
                svg.append(f'<g class="trade-dot">')
                svg.append(f'  <circle cx="{x}" cy="{y}" r="5" fill="{color}" stroke="#FFFFFF" stroke-width="1">')
                svg.append(f'    <title>{label}</title>')
                svg.append(f'  </circle>')
                # Floating tooltip label shown on group hover
                svg.append(f'  <g class="dot-tip" id="{tooltip_id}" opacity="0" style="pointer-events:none">')
                svg.append(f'    <rect x="{tx-2}" y="{ty-10}" width="{len(label)*6+8}" height="14" rx="3" fill="#000000" fill-opacity="0.85" stroke="{color}" stroke-width="1"/>')
                svg.append(f'    <text x="{tx+2}" y="{ty}" font-size="9" fill="{color}" font-family="monospace">{label}</text>')
                svg.append(f'  </g>')
                svg.append(f'</g>')

            svg.append('</svg>')
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(svg))
            return True
        except Exception as e:
            if hasattr(self, "app"): self.app.log_msg(f"SVG Save Error: {e}", level="ERROR")
            return False

    def save_graph_image(self, path):
        """Rasterizes the internal history into a PNG image using Pillow."""
        try:
            from PIL import Image, ImageDraw
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            # Use low resolution for the output image (160x80)
            img_w, img_h = 160, 80
            # 15 pixel padding for low res
            pad = 15
            
            # Background
            img = Image.new("RGB", (img_w + pad*2, img_h + pad*2), (18, 18, 18))
            draw = ImageDraw.Draw(img)
            
            # Draw Horizontal Grid Lines (every 20c for clarity at small scale)
            for i in [2, 4, 5, 6, 8]: # 20c, 40c, 50c, 60c, 80c
                y_val = i / 10.0
                y_px = pad + int((1.0 - y_val) * (img_h - 1))
                color = (60, 60, 60) if i == 5 else (35, 35, 35)
                draw.line([(pad, y_px), (img_w + pad, y_px)], fill=color, width=1)
            
            # Draw Vertical Grid Lines (every 2.5 minutes / mid-window)
            duration = getattr(self.app.config, "WINDOW_SECONDS", 300)
            mid_px = pad + int((0.5) * (img_w - 1))
            draw.line([(mid_px, pad), (mid_px, img_h + pad)], fill=(35, 35, 35), width=1)
            
            if not self.history:
                img.save(path)
                return True

            points = self.history
            if points and points[0][0] > 0:
                points = [(0, points[0][1])] + points
            
            # Map points to image coordinates
            coords = []
            for elapsed, val in points:
                x = pad + int((elapsed / duration) * (img_w - 1))
                y = pad + int((1.0 - val) * (img_h - 1))
                coords.append((x, y))
            
            # Draw the price line
            if len(coords) > 1:
                # Use width=2 for better visibility at 160px
                draw.line(coords, fill=(255, 255, 0), width=2, joint="curve")
                # Highlight last point
                lx, ly = coords[-1]
                draw.ellipse([lx-2, ly-2, lx+2, ly+2], fill=(255, 255, 0))
            elif len(coords) == 1:
                draw.ellipse([coords[0][0]-2, coords[0][1]-2, coords[0][0]+2, coords[0][1]+2], fill=(255, 255, 0))
            
            img.save(path)
            return True
        except Exception as e:
            if hasattr(self, "app") and hasattr(self.app, "log_msg"):
                self.app.log_msg(f"[red]Graph Save Error: {e}[/]")
            return False

class PulseApp(TradeEngineMixin, App):
    CSS = """
    Screen { align: center top; layers: base; }
    #top_bar { dock: top; height: 1; background: $panel; color: $text; content-align: center middle; }
    #btn_settings { dock: right; border: none; background: transparent; color: #aaaaaa; min-width: 14; height: 1; padding: 0 1; }
    #btn_settings:hover { color: #ffffff; text-style: bold; }
    #header_stats { width: auto; margin-right: 2; }
    .timer_text { text-style: bold; color: $warning; }
    .run_time { color: #00ffff; margin-left: 2; }
    .live_mode { color: #ff0000; text-style: bold; background: #330000; }
    
    #exposure_mini_box { width: 100%; height: auto; layout: vertical; }
    #exposure_mini_box Label { width: 100%; content-align: center middle; opacity: 0.8; }
    #lbl_owned_up { color: #00ff00; }
    #lbl_owned_dn { color: #ff0000; }
    
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

    #execution_area { height: 11; margin: 0 1; layout: horizontal; align: center middle; }
    Button { height: 1; min-width: 12; margin: 0 1; border: none; }
    #btn_container { width: 30; height: 9; layout: grid; grid-size: 2; align: center middle; margin-top: 1; }
    #pulse_lean_chart { width: 40; height: 9; border: ascii #333; background: #000; margin-left: 4; margin-top: 1; }
    .btn_buy_up { background: #006600; color: #ffffff; }
    .btn_buy_down { background: #660000; color: #ffffff; }
    .btn_sell_up { background: #b38600; color: #ffffff; }
    .btn_sell_down { background: #b34b00; color: #ffffff; }
    .btn_pre { min-width: 5; padding: 0; margin: 0 1; background: #000033; color: #00ffff; height: 1; }

    #lbl_vol_up { color: #00ff00; margin-right: 1; }
    #lbl_vol_dn { color: #ff0000; }
    #vol_container { height: 1; content-align: center middle; }

    #checkbox_container { height: auto; border-bottom: double $primary; margin-bottom: 1; }
    .algo_row { align: center middle; height: 1; layout: horizontal; padding: 0; margin: 0; }
    #prebuy_row { margin-top: 1; }
    .algo_row Button { height: 1; min-width: 8; margin: 0 1; }
    .algo_item { width: 1fr; height: 1; layout: horizontal; align: left middle; padding-left: 2; }
    .algo_item Checkbox { width: auto; margin: 0; padding: 0; border: none; }
    .algo_item Label { width: auto; margin: 0 0 0 1; color: #666666; }
    .algo_item Label:hover { color: cyan; text-style: underline; }
    
    /* Enhanced Modal Styles */
    .setting_section { margin: 1 0; padding: 1; background: #2a2a2a; border-left: solid #00ff88; }
    .section_title { color: #00ff88; text-style: bold; margin-bottom: 1; }
    .subsection_title { color: #ffff00; text-style: bold; margin: 1 0; padding: 1 0; border-bottom: solid #444444; }
    .help_text { color: #888888; text-style: italic; margin-bottom: 1; padding: 0 1; }
    .field_note { color: #666666; text-style: italic; }
    .field_label { color: #cccccc; min-width: 12; margin-right: 1; }
    .info_box { background: #1a1a1a; border: solid #333333; padding: 1; margin: 1 0; }
    .mode_info_box { color: #aaaaaa; padding: 1; }
    
    /* New MOM/MM2 Layout Styles */
    .mode_section { margin: 1 0; padding: 1; background: #1a1a1a; }
    .threshold_section { margin: 1 0; padding: 1; background: #1a1a1a; }
    .buymode_section { margin: 1 0; padding: 1; background: #1a1a1a; }
    .explanation_box { background: #002233; border: solid #004466; padding: 1; margin: 1 0; }
    
    .spaced_row { margin: 1 0; align: left middle; }
    .mode_select { width: 20; margin-right: 2; }
    .threshold_input { width: 8; }
    .time_input { width: 6; }
    
    .buymode_grid { margin: 1 0; }
    .buymode_row { align: left middle; margin: 1 0; padding: 1 0; }
    .mode_checkbox { margin-right: 1; }
    .mode_desc { color: #888888; text-style: italic; margin-left: 1; }
    
    .button_row { margin: 1 0; align: center middle; }
    .adv_button { margin: 1 0; padding: 1 2; }
    
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
    
    #rs_bet_mode { layout: horizontal; background: transparent; border: none; height: 1; width: auto; margin-left: 1; }
    #rs_bet_mode RadioButton { width: auto; padding: 0; margin: 0 1; height: 1; color: #aaaaaa; }
    #rs_bet_mode RadioButton:hover { color: #ffffff; }
    #rs_bet_mode RadioButton.-on { color: #00ff00; text-style: bold; }
    #rs_bet_mode RadioButton > .toggle--button { background: #333333; color: transparent; width: 1; }
    #rs_bet_mode RadioButton.-on > .toggle--button { background: #00ff00; color: #000000; width: 1; }

    RichLog { height: 1fr; min-height: 5; background: #111111; color: #eeeeee; }
    
    .mode_info_box {
        background: #002233;
        border: solid #004466;
        color: #00ddff;
        padding: 1;
        margin: 1 2;
        height: auto;
    }
    
    Collapsible {
        background: transparent;
        border: none;
        margin: 0;
        padding: 0;
    }
    Collapsible > Contents {
        padding: 0 1;
        background: #161616;
        border-bottom: solid #222222;
    }
    Collapsible > .collapsible--header {
        background: #0d0d0d;
        color: #00ffff;
        text-style: bold;
        height: 1;
        border-left: solid #ffaa00;
    }
    Collapsible > .collapsible--header:hover {
        background: #1a1a1a;
        color: #ffa500;
    }
    .input_group { 
        height: auto; 
        align: left middle; 
        layout: vertical; 
        padding-bottom: 1;
        margin-bottom: 0; 
        background: transparent;
    }
    .input_row {
        height: auto;
        layout: horizontal;
        align: left middle;
        margin-bottom: 0;
    }
    .input_title {
        color: #ffaa00;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
        width: 100%;
        text-align: left;
        opacity: 0.8;
        border-bottom: solid #333333;
    }
    .lbl_sm {
        width: 13;
        content-align: left middle;
        color: #999999;
    }
    Input {
        width: 12;
        height: 1;
        border: none;
        background: #333333;
        color: #ffffff;
        padding: 0 1;
        text-align: center;
    }
    Input:focus {
        background: #444444;
        color: #00ffff;
        text-style: bold;
    }

    #scanner_container { height: auto; margin-bottom: 1; border-top: solid #333333; padding-top: 1; }
    .scanner_col { width: 1fr; height: auto; padding: 0 1; }
    .scanner_header { 
        background: #111111; 
        color: #00ffff; 
        text-style: bold; 
        width: 100%; 
        padding: 0 1; 
        margin-bottom: 1; 
        border-bottom: solid #00ffff;
        content-align: center middle;
    }
    .algo_item { width: 100%; height: 1; layout: horizontal; align: left middle; margin-bottom: 0; }
    .algo_item Label { width: 1fr; }
    #btn_dar_info { min-width: 3; width: 3; height: 1; border: none; background: #333333; color: #00ffff; margin: 0; padding: 0; }
    #btn_dar_info:hover { background: #444444; color: #ffffff; }
    """

    @on(Button.Pressed, "#btn_dar_info")
    @on(Button.Pressed, "#btn_darwin_hub")
    def on_dar_info_press(self):
        self.push_screen(DarwinSettingsModal(main_app=self))

    @on(Checkbox.Changed)
    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        cb = event.checkbox
        cb_id = cb.id
        if not cb_id: return
        
        if cb_id and cb_id.startswith("cb_"):
            code = cb_id[3:]
            try:
                lbl = self.query_one(f"#lbl_{code}")
                if event.value:
                    lbl.styles.color = "#00ff00"
                    lbl.styles.text_style = "bold"
                    if not getattr(self, "is_initializing", False):
                        self.log_msg(f"ENABLED {code.upper()}", level="ADMIN")
                else:
                    lbl.styles.color = "#666666"
                    lbl.styles.text_style = "none"
                    if not getattr(self, "is_initializing", False):
                        self.log_msg(f"DISABLED {code.upper()}", level="ADMIN")
            except Exception:
                # Catch NoMatches or KeyErrors from modal checkboxes that bubble up
                pass
            
            # Auto-persist algorithm toggle
            if not getattr(self, "is_initializing", False):
                self.save_settings()
        
        elif cb_id and cb_id.startswith("cb_log_"):
            log_key = cb_id.replace("cb_log_", "")
            # Mapping short ID to settings key
            key_map = {"main": "main_csv", "console": "console_txt", "mom": "momentum_csv", "html": "verification_html"}
            if log_key in key_map:
                settings_key = key_map[log_key]
                self.log_settings[settings_key] = event.value
                self.log_msg(f"LOGGING {'ENABLED' if event.value else 'DISABLED'}: {settings_key.upper()}", level="SYS")
                if not getattr(self, "is_initializing", False):
                    self.save_settings()

    @on(events.Click, "Label")
    def on_label_click(self, event: events.Click) -> None:
        lbl_id = event.control.id
        if lbl_id and lbl_id.startswith("lbl_"):
            code = lbl_id[4:].upper()
            # Specific config modals (Lazy instantiation)
            modal_factory = {
                "STA": lambda: BullFlagSettingsModal(self),
                "CCO": lambda: CCOExpertModal(self),
                "GRI": lambda: GRISettingsModal(self, self.scanners.get("GrindSnap")),
                "RSI": lambda: RSISettingsModal(self, self.scanners.get("RSI")),
                "TRA": lambda: TRASettingsModal(self, self.scanners.get("TrapCandle")),
                "MID": lambda: MIDSettingsModal(self, self.scanners.get("MidGame")),
                "LAT": lambda: LATSettingsModal(self, self.scanners.get("LateReversal")),
                "POS": lambda: POSSettingsModal(self, self.scanners.get("PostPump")),
                "STE": lambda: STESettingsModal(self, self.scanners.get("StepClimber")),
                "SLI": lambda: SLISettingsModal(self, self.scanners.get("Slingshot")),
                "MIN": lambda: MINSettingsModal(self, self.scanners.get("MinOne")),
                "LIQ": lambda: LIQSettingsModal(self, self.scanners.get("LiquidityVacuum")),
                "COB": lambda: COBSettingsModal(self, self.scanners.get("Cobra")),
                "MES": lambda: MESSettingsModal(self, self.scanners.get("Mesa")),
                "NPA": lambda: NPASettingsModal(self, self.scanners.get("NPattern")),
                "FAK": lambda: FAKSettingsModal(self, self.scanners.get("Fakeout")),
                "MEA": lambda: MEASettingsModal(self, self.scanners.get("MeanReversion")),
                "VOL": lambda: VOLSettingsModal(self, self.scanners.get("VolCheck")),
                "MOS": lambda: MOSSettingsModal(self, self.scanners.get("Moshe")),
                "ZSC": lambda: ZSCSettingsModal(self, self.scanners.get("ZScore")),
                "BRI": lambda: BRISettingsModal(self, self.scanners.get("Briefing")),
                "WCP": lambda: WCPSettingsModal(self),
                "VPOC": lambda: VPOCSettingsModal(self),
                "SDP": lambda: SDPSettingsModal(self),
                "DIV": lambda: DIVSettingsModal(self),
                "SSI": lambda: SSISettingsModal(self),
                "SSC": lambda: SSCSettingsModal(self),
                "ADT": lambda: ADTSettingsModal(self),
                "MM2": lambda: MM2SettingsModal(self)
            }

            if code in modal_factory:
                self.push_screen(modal_factory[code]())
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

    def __init__(self, sim_broker, live_broker, start_live_mode=False, session_id=None):
        super().__init__()
        import atexit
        atexit.register(self.finalize_html_log)
        self.is_initializing = True
        self.config = TradingConfig() # Instantiate for dynamic frequency support
        self.sim_broker = sim_broker
        self.sim_broker.app = self  # Set app reference for log toggle checks
        self.live_broker = live_broker
        self.start_live_mode = start_live_mode
        self.market_data_manager = MarketDataManager(config=self.config, logger_func=lambda m, level="INFO": self.safe_call(self.log_msg, m, level=level))
        self.risk_manager = RiskManager(self.config)
        self.trade_executor = TradeExecutor(sim_broker, live_broker, self.risk_manager)
        self.trade_executor.config = self.config # Pass config to executor
        
        # FTP Sync System
        self.ftp_manager = FTPManager(logger_func=lambda m, level="INFO": self.safe_call(self.log_msg, m, level=level))
        if session_id:
            self.ftp_manager.set_session(f"session_{session_id}")
        self.market_data = self.market_data_manager.market_data 
        self.risk_initialized = False 
        self.last_second_exit_triggered = False
        self.next_window_preview_triggered = False
        self.pre_buy_pending = None        # { side, entry, cost } — held outside window_bets across settlement
        self.pre_buy_triggered = False     # latch: only one pre-buy per window
        self.mom_buy_mode = "STD"          # "STD" = standard signal | "PRE" = pre-buy next window
        self.window_realized_revenue = 0.0 # cumulative revenue added this window (TP/SL/manual sells)
        self.lw_lockout = 20               # Late-Window Lockout (seconds)
        self.sentiment_guard = 15.0        # Sentiment Guard (Odds Score threshold)
        self.halted = False                # True = bankroll exhausted, all scanning stopped
        self.sl_plus_mode = True
        self.grow_riskbankroll = False     # Toggle for bankroll compounding
        self.committed_tp = 0.95  # Default TP 95% — only updated on Enter
        self.committed_sl = 0.40  # Default SL 40% — only updated on Enter
        self.bounce_mode = False           # Bounce Entry: wait for dip+recovery before executing
        self.bounce_dip_cents = 0.5        # Minimum dip depth in ¢ to count as a valid retest
        self.bounce_pending = {}           # { name: { side, target_level, dip_depth, has_dipped, signal, bs } }
        self.auto_sync_risk = False        # mode to dynamically sync risk bankroll with total balance
        self.hdo_fired_in_window = False   # Latch: True if a hedge was triggered this window
        self.exposure_up = {"cost": 0.0, "payout": 0.0}
        self.exposure_dn = {"cost": 0.0, "payout": 0.0}
        self.last_window_ts = 0             # Track for gap detection (v5.9.9)
        
        # Log Toggles
        self.log_settings = {
            "main_csv": True,
            "console_txt": True,
            "momentum_csv": True,
            "verification_html": True
        }
        self.log_display_filter = set()
        self.log_display_mode = "ALL"  # Modes: ALL, HIDE, ONLY
        
        # [REFACTORED LOG SETUP] - Moved to end of __init__ to handle session subfolders correctly.
        pass
        # Initialization continues...
        
        self.scanners = {
            "NPattern": NPatternScanner(self.config),
            "Fakeout": FakeoutScanner(self.config),
            "Momentum": MomentumScanner(self.config),
            "MM2": Momentum2Scanner(self.config),
            "RSI": RsiScanner(self.config),
            "TrapCandle": TrapCandleScanner(self.config),
            "MidGame": MidGameScanner(self.config),
            "LateReversal": LateReversalScanner(self.config),
            "BullFlag": StaircaseBreakoutScanner(self.config),
            "CoiledCobra": CoiledCobraScanner(self.config),
            "PostPump": PostPumpScanner(self.config),
            "StepClimber": StepClimberScanner(self.config),
            "Slingshot": SlingshotScanner(self.config),
            "MinOne": MinOneScanner(self.config),
            "Liquidity": LiquidityVacuumScanner(self.config),
            "Cobra": CobraScanner(self.config),
            "Mesa": MesaCollapseScanner(self.config),
            "MeanReversion": MeanReversionScanner(self.config),
            "GrindSnap": GrindSnapScanner(self.config),
            "VolCheck": VolCheckScanner(self.config),
            "Moshe": MosheSpecializedScanner(self.config),
            "ZScore": ZScoreBreakoutScanner(self.config),
            "Nitro": NitroScanner(self.config),
            "VolSnap": VolSnapScanner(self.config),
            "HDO": HdoScanner(self.config),
            "Briefing": BriefingScanner(self.config),
            "WCP": WindowCandleProfiler(self.config),
            "VPOC": VPOCAnalyzer(self.config),
            "SDP": SettlementDriftPredictor(self.config),
            "DIV": SentimentDivergenceScanner(self.config),
            "SSI": StrategyInversionScanner(self.config),
            "SSC": ShallowSymmetricalContinuationScanner(self.config),
            "ADT": AsymmetricDoubleTestScanner(self.config)
        }
        
        # Initialize DARWIN AI Agent (v5.9.16)
        self.darwin = DarwinAgent(mode=self.config.DARWIN_MODE, log_fn=self.log_msg)
        self.scanners["Darwin"] = self.darwin

        self.portfolios = {name: AlgorithmPortfolio(name, 100.0, self.config) for name in self.scanners}
        self.logged_trend_wid = None # Latch for trend log deduplication
        self.window_bets = {} 
        self.pending_bets = {}
        self.last_second_exit_triggered = False 
        self.window_settled = False
        self.mid_window_lockout = False
        self.saved_sim_bankroll = None
        self.app_start_time = time.time()
        
        # Initialize DARWIN AI Agent (v5.9.16)
        self.darwin = DarwinAgent(mode=self.config.DARWIN_MODE, log_fn=self.log_msg)
        self.scanners["Darwin"] = self.darwin
        
        # Next-Strike Audit State
        self.audit_pending_info = None
        self.prev_window_expected_p2b = None
        self.awaiting_next_strike = False
        self.session_win_count = 0 
        self.session_total_trades = 0
        self.session_windows_settled = 0
        self.session_pnl = 0.0
        self.time_rem_str = "00:00"
        self.blink_state = False
        self.skipped_logs = set()
        self.session_date_logged = False
        self.last_sl_event_time = 0
        self.last_execution_time = 0
        self.exec_safety_mode = "global_lock"
        self.total_risk_cap = 30.0
        self.trend_efficiency = {
            "M-UP":    {"mult": 1.0, "lock": "side_lock", "cool": 1.0},
            "S-UP":    {"mult": 1.0, "lock": "side_lock", "cool": 1.0},
            "W-UP":    {"mult": 1.0, "lock": "side_lock", "cool": 1.0},
            "NEUTRAL": {"mult": 0.5, "lock": "global_lock", "cool": 2.0},
            "W-DOWN":  {"mult": 0.7, "lock": "global_lock", "cool": 1.5},
            "S-DOWN":  {"mult": 1.1, "lock": "side_lock", "cool": 1.0},
            "M-DOWN":  {"mult": 1.2, "lock": "risk_cap", "cool": 1.0},
        }
        
        # Adjustable global settings
        self.csv_log_freq = 15
        self.last_log_dump = 0
        
        # Persistent algorithm weights
        # Momentum Advanced Settings (v5.9)
        self.mom_adv_settings = {
            "atr_low": 20, "atr_high": 40,
            "stable_offset": -5, "chaos_offset": 10,
            "auto_stn_chaos": True, "auto_pbn_stable": False,
            "shield_time": 45, "shield_reach": 5,
            "atr_floor": 25.0, "trend_penalty": 0.02, "decisive_diff": 0.02,
            "pbn_odds_enabled": False, "pbn_odds_thresh": 2.0
        }
        self.mm2_adv_settings = self.mom_adv_settings.copy()
        self.nit_settings = {
            "time_cutoff": 120,
            "atr_multiplier": 1.0
        }
        self.vsn_settings = {
            "time_cutoff": 60,
            "diff_threshold": 50.0
        }
        self.rsi_settings = {"rsi_threshold": 20, "time_remaining_min": 80}
        self.tra_settings = {"start_move_pct": 0.002, "retrace_ratio": 0.35}
        self.mid_settings = {"min_elapsed": 90, "max_green_ticks": 25}
        self.lat_settings = {"min_elapsed": 200, "surge_pct": 1.0003}
        self.pos_settings = {"min_pump_pct": 0.003, "reversal_depth": 0.9985}
        self.ste_settings = {"tick_count": 15, "climb_pct": 1.001}
        self.sli_settings = {"ma_period": 15}
        self.min_settings = {"wick_multiplier": 1.5}
        self.liq_settings = {"break_structure_pct": 1.0001}
        self.cob_settings = {"ma_period": 15, "std_dev_mult": 1.5}
        self.mes_settings = {"pump_threshold": 0.001, "cross_count": 2}
        self.npa_settings = {"min_impulse_size": 0.0003, "max_retrace_depth": 0.85}
        self.fak_settings = {"phase1_duration": 60}
        self.mea_settings = {"reversal_threshold": 0.0005}
        self.vol_settings = {"avg_3m_multiplier": 1.0}
        self.mos_settings = {"moshe_threshold": 0.86, "t1": 290, "d1": 2000.0, "t2": 80, "d2": 80.0, "t3": 15, "d3": 25.0}
        self.zsc_settings = {"z_threshold": 3.5, "coil_threshold": 0.001}
        self.gri_settings = {"grind_duration": 100, "snap_duration": 20, "min_slope_pct": 0.1, "reversal_ratio": 0.60}
        self.bri_settings = {"rsi_low": 30, "rsi_high": 70, "odds_thresh": 5.0, "imb_thresh": 2.0, "signal_thresh": 2}
        self.wcp_settings = {"body_ratio_thresh": 0.30, "shadow_ratio_thresh": 2.0}
        self.vpoc_settings = {"dev_threshold": 0.0005}
        self.sdp_settings = {"drift_threshold": 0.05}
        self.div_settings = {"div_threshold": 5.0}
        self.ssi_settings = {"loss_streak_threshold": 3}
        
        self.conviction_scaling = {
            "enabled": False,
            "high_thresh": 10.0,
            "extreme_thresh": 20.0,
            "mult_strong": 1.25,
            "mult_decisive": 1.50,
            "penalty": 0.50
        }
        
        # [NEW] Volatility-Based Sizing Scaling (v5.9.13)
        self.volatility_scaling = {
            "enabled": False,
            "floor": 15.0,     # Below this, size is 0% (Hard Cutoff)
            "ceiling": 40.0    # Above this, size is 100% (Plateau)
        }
        self.window_vol_mult = 1.0
        self.window_vol_halt = False
        
        # [NEW] Value Re-entry (Round 2) Settings (v5.9.15)
        self.value_reentry = {
            "enabled": False,
            "reset_lvl": 0.52,          # Max price (for UP) to count as "Neutral Reset"
            "reconfirm_move": 0.02,     # Min bounce in ¢ to re-trigger
            "reconfirm_time": 10,       # Window in seconds for the bounce move
            "size_mult": 0.30,          # Reduced size for the second entry (30% default)
            "gap": 0.05                 # Min ¢ difference from first entry
        }
        
        # Global Skepticism Premium Settings
        self.global_skeptic_odds = 0.05
        self.global_skeptic_guess = 0.03
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.settings_file = os.path.join(script_dir, "pulse_settings.json")
        
        # Base 1.0 weight with 1.67x (20% / 12%) modifier for historically "Strong" scanners
        self.scanner_weights = {k: 1.0 for k in ALGO_INFO.keys()}
        self.scanner_weights["COB"] = 1.67
        self.scanner_weights["CCO"] = 1.67
        self.scanner_weights["LIQ"] = 1.67
        self.scanner_weights["LAT"] = 1.67
        
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r") as f:
                    saved = json.load(f)
                    if "scanner_weights" in saved:
                        for sk, sv in saved["scanner_weights"].items():
                            if sk in self.scanner_weights:
                                self.scanner_weights[sk] = float(sv)
                    if "nit_settings" in saved:
                        self.nit_settings.update(saved["nit_settings"])
                        # Sync to scanner instance
                        sc = self.scanners.get("Nitro")
                        if sc:
                            sc.time_cutoff = self.nit_settings["time_cutoff"]
                            sc.atr_multiplier = self.nit_settings["atr_multiplier"]
                    if "vsn_settings" in saved:
                        self.vsn_settings.update(saved["vsn_settings"])
                        sc = self.scanners.get("VolSnap")
                        if sc:
                            sc.time_cutoff = self.vsn_settings["time_cutoff"]
                            sc.diff_threshold = self.vsn_settings["diff_threshold"]
                    
                    # Basic scanner settings mapping
                    for key in ["rsi", "tra", "mid", "lat", "pos", "ste", "sli", "min", "liq", "cob", "mes", "gri", "npa", "fak", "mea", "vol", "mos", "zsc", "bri", "wcp", "vpoc", "sdp", "div", "ssi"]:
                        s_key = f"{key}_settings"
                        if s_key in saved:
                            getattr(self, s_key).update(saved[s_key])
                    
                    # Post-load sync to scanner instances
                    sync_map = {
                        "RSI": "rsi", "TrapCandle": "tra", "MidGame": "mid", "LateReversal": "lat",
                        "PostPump": "pos", "StepClimber": "ste", "Slingshot": "sli", "MinOne": "min",
                        "Liquidity": "liq", "Cobra": "cob", "Mesa": "mes", "GrindSnap": "gri",
                        "NPattern": "npa", "Fakeout": "fak", "MeanReversion": "mea", "VolCheck": "vol",
                        "Moshe": "mos", "ZScore": "zsc", "Briefing": "bri",
                        "WCP": "wcp", "VPOC": "vpoc", "SDP": "sdp", "DIV": "div", "SSI": "ssi"
                    }
                    for scanner_name, attr_prefix in sync_map.items():
                        sc = self.scanners.get(scanner_name)
                        if sc:
                            s_data = getattr(self, f"{attr_prefix}_settings")
                            for k, v in s_data.items():
                                setattr(sc, k, v)

                    if "mom_adv_settings" in saved:
                        self.mom_adv_settings.update(saved["mom_adv_settings"])
                    if "mm2_adv_settings" in saved:
                        self.mm2_adv_settings.update(saved["mm2_adv_settings"])

                    def _safe_update(attr, key):
                        if key in saved:
                            try: getattr(self, attr).update(saved[key])
                            except: pass

                    _safe_update("trend_efficiency", "trend_efficiency")
                    _safe_update("conviction_scaling", "conviction_scaling")
                    _safe_update("volatility_scaling", "volatility_scaling")
                    _safe_update("value_reentry", "value_reentry")
                    _safe_update("log_settings", "log_settings")

                    if "auto_sync_risk" in saved: self.auto_sync_risk = bool(saved["auto_sync_risk"])
                    if "exec_safety_mode" in saved: self.exec_safety_mode = str(saved["exec_safety_mode"])
                    if "total_risk_cap" in saved: self.total_risk_cap = float(saved["total_risk_cap"])
                    if "shield_time" in saved: self.shield_time = int(saved["shield_time"])
                    if "shield_reach" in saved: self.shield_reach = int(saved["shield_reach"])
                    if "market_freq" in saved: self.config.MARKET_FREQ = int(saved["market_freq"])
        except Exception: pass

        # Respect user-specified log directory from SimBroker (which is now session-specific)
        if hasattr(self.sim_broker, "log_file") and self.sim_broker.log_file:
            log_dir = os.path.dirname(self.sim_broker.log_file)
        else:
            log_dir = os.path.join(script_dir, "lg")
            
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # ---------------------------------------------------------
        # [SESSION LOG INITIALIZATION]
        # ---------------------------------------------------------
        csv_base = os.path.basename(self.sim_broker.log_file)
        base_name_only = os.path.splitext(csv_base)[0]
        
        # 1. Console Log
        self.console_log_file = os.path.join(log_dir, base_name_only + "_console.txt")
        if self.log_settings["console_txt"]:
            with open(self.console_log_file, "w", encoding="utf-8") as f:
                f.write("=== POLYMARKET VORTEX PULSE V5 CONSOLE LOG ===\n")
                
        # 2. HTML Log
        self.html_log_file = os.path.join(log_dir, base_name_only + "_verification.html")
        if self.log_settings["verification_html"]:
            # Build the JS snippet that inlines SVGs after page load so <title> tooltips work
            svg_inline_js = """
<script>
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('img.graph-img').forEach(function(img) {
    var src = img.getAttribute('src');
    if (!src || !src.endsWith('.svg')) return;
    fetch(src)
      .then(function(r) { return r.text(); })
      .then(function(svgText) {
        var wrapper = document.createElement('div');
        wrapper.className = 'svg-wrapper';
        wrapper.innerHTML = svgText;
        var svgEl = wrapper.querySelector('svg');
        if (svgEl) {
          svgEl.setAttribute('class', 'graph-svg');
          svgEl.style.cursor = 'pointer';
          svgEl.addEventListener('click', function() { window.open(src); });
          img.parentNode.replaceChild(wrapper, img);
        }
      })
      .catch(function() {}); // Silently ignore fetch errors (e.g. file:// protocol)
  });
});
</script>
"""
            with open(self.html_log_file, "w", encoding="utf-8") as f:
                f.write("<html><head><title>Vortex Pulse Verification Log</title>")
                f.write("<style>body{font-family:sans-serif;background:#111;color:#eee;padding:20px;}")
                f.write("table{width:100%;border-collapse:collapse;margin-top:20px;}")
                f.write("th,td{border:1px solid #444;padding:10px;text-align:left;}")
                f.write("th{background:#222;color:#00ffff;}")
                f.write("tr:nth-child(even){background:#1a1a1a;}")
                f.write("a{color:#00ffff;text-decoration:none;}a:hover{text-decoration:underline;}")
                f.write(".UP{color:#00ff00;font-weight:bold;}.DOWN{color:#ff0000;font-weight:bold;}")
                f.write(".discrepancy{background:#4d0000 !important;}")
                f.write(".graph-img{width:100%;max-width:350px;height:auto;border:1px solid #444;background:#121212;transition:transform 0.2s;}")
                f.write(".graph-img:hover{transform:scale(1.8);z-index:100;position:relative;border-color:#00ffff;}")
                f.write(".no-data{background:#2a2a2a;color:#888;padding:20px;text-align:center;border-radius:8px;margin:20px 0;}")
                f.write(".algorithm-signals{background:#1a1a1a;border-bottom:2px solid #333;}")
                f.write(".algorithm-signals td{padding:8px 10px;font-size:0.9em;color:#bbb;}")
                f.write(".algorithm-signals strong{color:#00ffff;}")
                # SVG inline styles: makes the inlined svg scale and show tooltips properly
                f.write(".svg-wrapper{display:inline-block;max-width:350px;width:100%;transition:transform 0.2s;position:relative;}")
                f.write(".svg-wrapper:hover{transform:scale(1.8);z-index:100;}")
                f.write(".graph-svg{width:100%;height:auto;border:1px solid #444;background:#121212;display:block;}")
                f.write(".graph-svg:hover{border-color:#00ffff;}")
                # Style for SVG circle tooltips so they appear on title hover
                f.write(".graph-svg circle{cursor:crosshair;}")
                f.write("</style>")
                f.write(svg_inline_js)
                f.write("</head><body>")
                f.write("<h1>Vortex Pulse - Manual Verification Log</h1>")
                f.write(f"<p>Session Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>")
                f.write("<table><thead><tr>")
                f.write("<th>Timestamp</th>")
                f.write("<th>Polymarket Window Link</th>")
                f.write("<th>Bot Strike</th>")
                f.write("<th>Poly Strike</th>")
                f.write("<th>Strike Drift</th>")
                f.write("<th>Settlement Price</th>")
                f.write("<th>Resolution</th>")
                f.write("<th>Pulse Result</th>")
                f.write("<th>Sync Status</th>")
                f.write("<th>Action</th>")
                f.write("<th>Result</th>")
                f.write("<th>Profit/Loss</th>")
                f.write("<th>Balance ($)</th>")
                f.write("<th>Graph</th>")
                f.write("</tr></thead>")
                f.write("<tbody>\n")
                
                # Add a placeholder row for early exits - will be replaced if data is added
                f.write("<!-- SESSION_DATA_PLACEHOLDER -->\n")

        # 3. Momentum ADV Log
        self.mom_analytics = self._reset_mom_analytics()
        self.mom_adv_log_file = os.path.join(log_dir, f"momentum_adv_{base_name_only}.csv")
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
            Label(f"{self.config.MARKET_FREQ}-SIM | Bal: ${self.sim_broker.balance:.2f}", id="header_stats"),
            Label(f" | RUN: 00:00:00", id="lbl_runtime", classes="run_time"),
            Label(" | WIN: ", classes="timer_text"),
            Label("00:00", id="lbl_timer_big", classes="timer_text"),
            Label(" | Start: ", classes="timer_text"),
            Label("--:--:--", id="lbl_window_start", classes="timer_text"),
            id="top_bar"
        )
        yield Horizontal(
            Container(
                Label("$0.00", id="p_btc", classes="price_val"),
                Label("Open: $0", id="p_btc_open", classes="price_sub"),
                Label("Diff: $0", id="p_btc_diff", classes="price_sub"),
                Label("Trend 1H: NEUTRAL", id="p_trend", classes="price_sub"),
                Label("ATR 5m: $0.00", id="p_atr", classes="price_sub"),
                Horizontal(
                    Label("V-UP: --", id="lbl_vol_up", classes="price_sub"),
                    Label("V-DN: --", id="lbl_vol_dn", classes="price_sub"),
                    id="vol_container"
                ),
                Vertical(
                    Label("UP OWNED: $0/$0", id="lbl_owned_up"),
                    Label("DN OWNED: $0/$0", id="lbl_owned_dn"),
                    id="exposure_mini_box"
                ),
                Label("🧬 AI: IDLE", id="p_darwin", classes="price_sub"),
                id="card_btc", classes="price_card"
            ),
            Vertical(
                Vertical(Label("UP", classes="price_sub"), Label("0.0¢", id="p_up", classes="price_val"), id="card_up", classes="mini_card"),
                Vertical(Label("DN", classes="price_sub"), Label("0.0¢", id="p_down", classes="price_val"), id="card_down", classes="mini_card"),
                classes="right_col"
            ),
            classes="row_main"
        )
        with Collapsible(title="TRADING CONFIGURATION & RISK", id="settings_collapsible"):
            with Vertical(classes="input_group"):
                yield Label("BANKROLL & POSITIONING", classes="input_title")
                with Horizontal(classes="input_row"):
                    yield Label("Bet Size:", classes="lbl_sm")
                    yield Input(placeholder="Bet $", value="1.00", id="inp_amount")
                    yield RadioSet(
                        RadioButton("Fixed $", id="rb_fixed", value=True),
                        RadioButton("% Bank", id="rb_pct"),
                        id="rs_bet_mode"
                    )
                with Horizontal(classes="input_row"):
                    yield Label("Bankroll:", classes="lbl_sm")
                    yield Input(placeholder="Allocated Funds", id="inp_risk_alloc")
                    yield Label("TP %:", classes="lbl_sm")
                    yield Input(placeholder="TP %", value="95", id="inp_tp")
                    yield Label("SL %:", classes="lbl_sm")
                    yield Input(placeholder="SL %", value="40", id="inp_sl")
            
            with Vertical(classes="input_group"):
                yield Label("PRICING FILTERS & SIMULATION", classes="input_title")
                with Horizontal(classes="input_row"):
                    yield Label("Sim Wallet:", classes="lbl_sm")
                    yield Input(placeholder="Sim Bal", value=f"{self.sim_broker.balance:.2f}", id="inp_sim_bal")
                    yield Label("Min Diff:", classes="lbl_sm")
                    yield Input(placeholder="Diff $", value="0", id="inp_min_diff")
                with Horizontal(classes="input_row"):
                    yield Label("Price Min:", classes="lbl_sm")
                    yield Input(placeholder="Min", value="0.55", id="inp_min_price")
                    yield Label("Price Max:", classes="lbl_sm")
                    yield Input(placeholder="Max", value="0.80", id="inp_max_price")
            
            with Vertical(classes="input_group"):
                yield Label("SKEPTICISM & PENALTIES", classes="input_title")
                with Horizontal(classes="input_row"):
                    yield Label("Odds Skip:", classes="lbl_sm")
                    yield Input(placeholder="Odds", value=f"{self.global_skeptic_odds:.2f}", id="inp_skeptic_odds")
                    yield Label("Guess Skip:", classes="lbl_sm")
                    yield Input(placeholder="Guess", value=f"{self.global_skeptic_guess:.2f}", id="inp_skeptic_guess")
                with Horizontal(classes="input_row"):
                    yield Label("Pen %:", classes="lbl_sm")
                    yield Input(placeholder="Pen%", value=f"{getattr(self, 'penalty_percentage', 0.20)*100:.0f}", id="inp_penalty_pct")
                    yield Label("Whale Secs:", classes="lbl_sm")
                    yield Input(placeholder="Secs", value=f"{getattr(self, 'shield_time', 45)}", id="inp_shield_time")
                    yield Label("Whale Cents:", classes="lbl_sm")
                    yield Input(placeholder="Cents", value=f"{getattr(self, 'shield_reach', 5)}", id="inp_shield_reach")
                with Horizontal(classes="input_row"):
                    yield Label("LWL Secs:", classes="lbl_sm")
                    yield Input(placeholder="Secs", value=f"{self.lw_lockout}", id="inp_lw_lockout")
                    yield Label("Sent. Guard:", classes="lbl_sm")
                    yield Input(placeholder="¢", value=f"{self.sentiment_guard:.1f}", id="inp_sentiment_guard")
            
            with Vertical(classes="input_group"):
                yield Label("LOGGING CONTROL (Persisted)", classes="input_title")
                with Horizontal(classes="input_row"):
                    yield Label("Main CSV:", classes="lbl_sm")
                    yield Checkbox(value=self.log_settings["main_csv"], id="cb_log_main")
                    yield Label("Console TXT:", classes="lbl_sm")
                    yield Checkbox(value=self.log_settings["console_txt"], id="cb_log_console")
                with Horizontal(classes="input_row"):
                    yield Label("Momentum CSV:", classes="lbl_sm")
                    yield Checkbox(value=self.log_settings["momentum_csv"], id="cb_log_mom")
                    yield Label("Verification HTML:", classes="lbl_sm")
                    yield Checkbox(value=self.log_settings["verification_html"], id="cb_log_html")

        yield Horizontal(
            Container(
                Button("BUY UP", id="btn_buy_up", classes="btn_buy_up"), 
                Button("SELL UP", id="btn_sell_up", classes="btn_sell_up"), 
                Button("BUY DN", id="btn_buy_down", classes="btn_buy_down"),
                Button("SELL DN", id="btn_sell_down", classes="btn_sell_down"),
                Button("pbu", id="btn_pre_up", classes="btn_pre"),
                Button("pbd", id="btn_pre_down", classes="btn_pre"),
                id="btn_container"
            ),
            PulseLeanChart(id="pulse_lean_chart"),
            id="execution_area"
        )
        with Collapsible(title="AVAILABLE SCANNERS & FILTERS", id="scanner_collapsible"):
            yield Horizontal(
                Label("Scanners:", classes="lbl_sm"),
                Button("ALL", id="btn_algo_all"),
                Button("NONE", id="btn_algo_none"),
                classes="algo_row"
            )
            with Horizontal(id="scanner_container"):
                with Vertical(classes="scanner_col"):
                    yield Label("CORE / FREQ", classes="scanner_header")
                    yield Horizontal(Checkbox(value=True, id="cb_mom"), Label("MOM", id="lbl_mom"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_mm2"), Label("MM2", id="lbl_mm2"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_nit"), Label("NIT", id="lbl_nit"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_cco"), Label("CCO", id="lbl_cco"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_bri"), Label("BRI", id="lbl_bri"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_hdo"), Label("HDO", id="lbl_hdo"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_mos"), Label("MOS", id="lbl_mos"), classes="algo_item")

                with Vertical(classes="scanner_col"):
                    yield Label("TREND / SURGE", classes="scanner_header")
                    yield Horizontal(Checkbox(value=False, id="cb_sta"), Label("STA", id="lbl_sta"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_lat"), Label("LAT", id="lbl_lat"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_ste"), Label("STE", id="lbl_ste"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_gri"), Label("GRI ⚙", id="lbl_gri", classes="cfg_lbl"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_npa"), Label("NPA", id="lbl_npa"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_fak"), Label("FAK", id="lbl_fak"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_zsc"), Label("ZSC", id="lbl_zsc"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_vsn"), Label("VSN", id="lbl_vsn"), classes="algo_item")

                with Vertical(classes="scanner_col"):
                    yield Label("REVERSAL / OSC", classes="scanner_header")
                    yield Horizontal(Checkbox(value=False, id="cb_mea"), Label("MEA", id="lbl_mea"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_rsi"), Label("RSI", id="lbl_rsi"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_tra"), Label("TRA", id="lbl_tra"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_mes"), Label("MES", id="lbl_mes"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_pos"), Label("POS", id="lbl_pos"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_cob"), Label("COB", id="lbl_cob"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_sli"), Label("SLI", id="lbl_sli"), classes="algo_item")

                with Vertical(classes="scanner_col"):
                    yield Label("DYNAMICS / MISC", classes="scanner_header")
                    yield Horizontal(Checkbox(value=False, id="cb_vol"), Label("VOL", id="lbl_vol"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_liq"), Label("LIQ", id="lbl_liq"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_ssc"), Label("SSC", id="lbl_ssc"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_adt"), Label("ADT", id="lbl_adt"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_mid"), Label("MID ~", id="lbl_mid", classes="deprecated_lbl"), classes="algo_item")
                    yield Horizontal(Checkbox(value=False, id="cb_min"), Label("MIN ~", id="lbl_min", classes="deprecated_lbl"), classes="algo_item")

                with Vertical(classes="scanner_col"):
                    yield Label("INTEL SUITE", classes="scanner_header")
                    with Horizontal(classes="algo_item"):
                        yield Checkbox(value=False, id="cb_wcp")
                        yield Label("WCP", id="lbl_wcp")
                    with Horizontal(classes="algo_item"):
                        yield Checkbox(value=False, id="cb_vpoc")
                        yield Label("VPO", id="lbl_vpoc")
                    with Horizontal(classes="algo_item"):
                        yield Checkbox(value=False, id="cb_sdp")
                        yield Label("SDP", id="lbl_sdp")
                    with Horizontal(classes="algo_item"):
                        yield Checkbox(value=False, id="cb_div")
                        yield Label("DIV", id="lbl_div")
                    with Horizontal(classes="algo_item"):
                        yield Checkbox(value=False, id="cb_ssi")
                        yield Label("SSI", id="lbl_ssi")
                    with Horizontal(classes="algo_item"):
                        yield Checkbox(value=True, id="cb_dar")
                        yield Label("DAR", id="lbl_dar")
                        yield Button("?", id="btn_dar_info", variant="default")
        yield Horizontal(
            Checkbox("TP/SL", value=True, id="cb_tp_active"),
            Checkbox("Tranche Exits", value=False, id="cb_tranche"),
            Checkbox("Strong Only", value=False, id="cb_strong"),
            Checkbox("1 Trade Max", value=False, id="cb_one_trade"), 
            Checkbox("Whale Protect", value=False, id="cb_whale"),
            Checkbox("Bounce Entry", value=False, id="cb_bounce"),
            id="settings_row",
            classes="live_row"
        )
        yield Horizontal(
            Input(placeholder="90c @ 1:30", id="inp_time_tp"),
            Checkbox("Time TP", value=False, id="cb_time_tp"),
            id="time_tp_row",
            classes="live_row"
        )
        yield Horizontal(
            Checkbox("LIVE MODE", value=False, id="cb_live"),
            Input(placeholder="Command: e.g., lo=false", id="inp_cmd"),
            Button("🧬 AI HUB", id="btn_darwin_hub", variant="warning"),
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
            elif cmd == "grow_riskbankroll=true":
                self.grow_riskbankroll = True
                self.log_msg("[bold green]Admin Command:[/] Bankroll Compounding ENABLED (Ceiling can rise).")
                self.save_settings()
            elif cmd == "grow_riskbankroll=false":
                self.grow_riskbankroll = False
                self.log_msg("SETTING: Bankroll Compounding | Status: OFF (Hard Cap Active)", level="SYS")
                self.save_settings()
            elif cmd == "freeze=true":
                self.halted = True
                self.log_msg("SYSTEM: Manual Freeze | Status: ACTIVATED", level="SYS")
                self.push_screen(ManualFreezeModal(self))
            elif cmd == "fetchpre":
                self.log_msg("[bold cyan]Admin Command:[/] Fetching Next Window Prices...")
                def _do_fetch_pre():
                    try:
                        next_ts = self.market_data["start_ts"] + self.config.WINDOW_SECONDS
                        next_slug = f"btc-updown-{self.config.MARKET_FREQ}m-{next_ts}"
                        d = self.market_data_manager.fetch_polymarket(next_slug)
                        up_ask = d.get("up_ask", 0)
                        dn_ask = d.get("down_ask", 0)
                        if up_ask > 0 or dn_ask > 0:
                            self.safe_call(self.log_msg, f"[bold cyan]NEXT WINDOW:[/] UP ask={up_ask*100:.1f}¢ | DN ask={dn_ask*100:.1f}¢")
                        else:
                            self.safe_call(self.log_msg, "[bold red]NEXT WINDOW:[/] Markets not yet active/available.")
                    except Exception as e:
                        self.safe_call(self.log_msg, f"[bold red]NEXT WINDOW ERROR:[/] {e}")
                import threading
                threading.Thread(target=_do_fetch_pre, daemon=True).start()
            elif cmd.startswith("penalty_percentage="):
                try:
                    pct = float(cmd.split("=")[1].strip())
                    if pct < 0 or pct > 100: raise ValueError
                    self.penalty_percentage = pct / 100.0
                    self.log_msg(f"[bold green]Admin Command:[/] Trend Mismatch Penalty set to [cyan]{pct}%[/].")
                    self.save_settings()
                except ValueError:
                    self.log_msg("[bold red]Admin Command Error:[/] Invalid penalty percentage. Example: 'penalty_percentage=50'")
            elif cmd.startswith("hdo_thr="):
                try:
                    val = float(cmd.split("=")[1].strip())
                    if val < 0.50 or val > 0.99: raise ValueError
                    hdo_scanner = self.scanners.get("HDO")
                    if hdo_scanner:
                        hdo_scanner.trigger_threshold = val
                        self.log_msg(f"[bold green]Admin Command:[/] HDO Threshold set to [cyan]{val*100:.1f}¢[/].")
                        self.save_settings()
                    else:
                        self.log_msg("[bold red]Admin Command Error:[/] HDO scanner not found")
                except ValueError:
                    self.log_msg("[bold red]Admin Command Error:[/] Invalid threshold. Minimum logically sound value is 0.50 (50¢). Example: 'hdo_thr=0.65'")
            elif cmd.startswith("mom:"):
                # Format: mom: atr_floor=30 gap_req_base=0.06 auto_stn_chaos=true
                args_str = cmd[4:].strip()
                if not args_str:
                    self.log_msg("[red]Admin Command:[/] Invalid mom command. Format: 'mom: key=value key=value'")
                else:
                    updates = []
                    for pair in args_str.split():
                        if "=" not in pair: continue
                        k, v = pair.split("=", 1)
                        k = k.strip()
                        v = v.strip().lower()
                        
                        if k not in self.mom_adv_settings:
                            self.log_msg(f"[red]Warning:[/] Unknown MOM parameter '{k}'")
                            continue
                            
                        try:
                            if v in ["true", "on", "yes", "t", "y", "1"]:
                                self.mom_adv_settings[k] = True
                                updates.append(f"{k}=[green]True[/]")
                            elif v in ["false", "off", "no", "f", "n", "0"]:
                                self.mom_adv_settings[k] = False
                                updates.append(f"{k}=[red]False[/]")
                            else:
                                self.mom_adv_settings[k] = float(v)
                                updates.append(f"{k}=[cyan]{v}[/]")
                        except ValueError:
                            self.log_msg(f"[red]Error:[/] Invalid value '{v}' for '{k}'. Must be number or boolean.")
                            
                    if updates:
                        self.save_mom_adv_settings()
                        self.log_msg(f"[bold cyan]MOM Settings Updated:[/] " + " | ".join(updates))
                        
            elif cmd == "analyze-pre":
                self.analyze_pre_buy_conditions()
            elif cmd.startswith("darwin:"):
                sub = cmd[7:].strip().lower()
                if sub == "v1":
                    self.darwin.mode = self.darwin.MODE_V1
                    self.log_msg("[bold cyan]🧬 DARWIN:[/] Switched to [green]V1 Observer[/] mode.")
                elif sub == "v2":
                    self.darwin.mode = self.darwin.MODE_V2
                    self.log_msg("[bold cyan]🧬 DARWIN:[/] Switched to [yellow]V2 Experimenter[/] mode.")
                elif sub == "status":
                    wr = (self.darwin.virtual_wins / self.darwin.virtual_trades * 100) if self.darwin.virtual_trades else 0
                    self.log_msg(f"[bold cyan]🧬 DARWIN STATUS:[/]")
                    self.log_msg(f"  • Mode: {self.darwin.mode}")
                    self.log_msg(f"  • V-PnL: {self.darwin.virtual_pnl:+.2f}")
                    self.log_msg(f"  • Win Rate: {wr:.1f}% ({self.darwin.virtual_wins}/{self.darwin.virtual_trades})")
                    if self.darwin.mode == self.darwin.MODE_V2:
                        self.log_msg(f"  • Active Code: {len(self.darwin.current_algo_code)} chars")
                else:
                    self.log_msg("[red]Unknown darwin command. Use darwin:v1, darwin:v2, or darwin:status[/]")
            elif cmd.startswith("/hide ") or cmd.startswith("/only "):
                parts = cmd.split(" ", 1)
                mode = parts[0][1:].upper() # HIDE or ONLY
                # Map common user terms to internal short labels
                mapping = {
                    "ADMIN": "SYS", "SYSTEM": "SYS", "SCANNER": "SCAN", "SCANNERS": "SCAN",
                    "TRADE": "EXEC", "TRADES": "EXEC", "MONEY": "RSLT", "RESULT": "RSLT",
                    "RESULTS": "RSLT", "ERROR": "ERR", "ERRORS": "ERR", "INFO": "INF",
                    "VOL": "VOLAT", "VOLATILITY": "VOLAT", "SKEPTIC": "SYS"
                }
                raw_levels = [l.strip().upper() for l in parts[1].split(",")]
                mapped_levels = [mapping.get(l, l) for l in raw_levels]
                
                self.log_display_filter = set(mapped_levels)
                self.log_display_mode = mode
                self.log_msg(f"LOG FILTER: {mode} mode active for {', '.join(mapped_levels)}", level="SYS")
                
            elif cmd == "/show all" or cmd == "/showall" or cmd == "/unfilter":
                self.log_display_mode = "ALL"
                self.log_display_filter = set()
                self.log_msg("LOG FILTER: Showing ALL logs (Filter Disabled)", level="SYS")
                
            elif cmd == "?":
                self.push_screen(CommandHelpModal())
            elif cmd.startswith("risk_pct="):
                # Format: risk_pct=0.10 (sets 10% of risk bankroll per bet)
                try:
                    pct_str = cmd.split("=", 1)[1].strip()
                    new_pct = float(pct_str)
                    if 0.01 <= new_pct <= 1.0:  # Between 1% and 100%
                        self.risk_manager.bet_percentage = new_pct
                        self.log_msg(f"[bold green]Admin Command:[/] Bet percentage set to {new_pct*100:.1f}% of risk bankroll")
                        self.save_settings()
                    else:
                        self.log_msg(f"[red]Admin Error:[/] Risk percentage must be between 0.01 (1%) and 1.0 (100%)")
                except (ValueError, IndexError):
                    self.log_msg(f"[red]Admin Error:[/] Invalid format. Use: risk_pct=0.10 (for 10%)")
            elif cmd:
                self.log_msg(f"[yellow]Unknown Command:[/] {cmd}")
            event.input.value = ""
            return
            
        # Handle manual SIM Balance override
        if event.input.id == "inp_sim_bal":
            if not self.query_one("#cb_live").value:
                try:
                    new_bal = float(event.input.value)
                    self.sim_broker.balance = new_bal
                    self.log_msg(f"SETTING: Sim Balance | Value: ${new_bal:.2f} | Source: MANUAL", level="SYS")
                    self.update_balance_ui()
                except ValueError: pass
            return
        
        # Determine human-readable names for the logs
        labels = {
            "inp_amount": "Bet Size",
            "inp_risk_alloc": "Risk Bankroll",
            "inp_tp": "Take Profit %",
            "inp_sl": "Stop Loss %",
            "inp_shield_time": "Whale Secs",
            "inp_shield_reach": "Whale Cents",
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
                        self.log_msg(f"SETTING: {name} | Value: ${new_br:.2f} | Status: UPDATED", level="SYS")
                        self.risk_manager.risk_bankroll = new_br
                        self.risk_manager.target_bankroll = new_br
                    
                    # Ensure bankroll change is persisted
                    if not getattr(self, "is_initializing", False):
                        self.save_settings()
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
                        self.log_msg(f"SETTING: {name} | Value: {val}% | Status: COMMITTED", level="SYS")
                    except ValueError: pass
                elif event.input.id == "inp_skeptic_odds":
                    self.global_skeptic_odds = float(val) if val else 0.05
                    self.log_msg(f"SETTING: Odds Skepticism | Value: {self.global_skeptic_odds}c", level="SYS")
                elif event.input.id == "inp_skeptic_guess":
                    self.global_skeptic_guess = float(val) if val else 0.03
                    self.log_msg(f"SETTING: Guess Skepticism | Value: {self.global_skeptic_guess}c", level="SYS")
                elif event.input.id == "inp_penalty_pct":
                    self.penalty_percentage = float(val)/100.0 if val else 0.10
                    self.log_msg(f"SETTING: Bet Penalty | Value: {val}%", level="SYS")
                elif event.input.id == "inp_lw_lockout":
                    self.lw_lockout = int(val) if val else 20
                    self.log_msg(f"SETTING: LW Lockout | Value: {val}s", level="SYS")
                elif event.input.id == "inp_sentiment_guard":
                    self.sentiment_guard = float(val) if val else 15.0
                    self.log_msg(f"SETTING: Sentiment Guard | Value: {val}¢", level="SYS")
                else:
                    self.log_msg(f"SETTING: {name} | Value: {val}", level="SYS")

        # Auto-persist any setting that was just changed
        if not getattr(self, "is_initializing", False):
            if event.input.id in {"inp_amount", "inp_tp", "inp_sl", "inp_min_diff", "inp_min_price", "inp_max_price", "inp_skeptic_odds", "inp_skeptic_guess", "inp_penalty_pct", "inp_shield_time", "inp_shield_reach", "inp_risk_alloc"}:
                self.save_settings()

    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed):
        """Auto-persist settings as the user types (no Enter required)."""
        if getattr(self, "is_initializing", False): return
        
        # [CRITICAL] Unified State-Sync logic: 
        # Update internal logic variables IMMEDIATELY so they are used in next tick
        val = event.input.value
        try:
            if event.input.id == "inp_tp": self.committed_tp = float(val) / 100
            elif event.input.id == "inp_sl": self.committed_sl = float(val) / 100
            elif event.input.id == "inp_skeptic_odds": self.global_skeptic_odds = float(val)
            elif event.input.id == "inp_skeptic_guess": self.global_skeptic_guess = float(val)
            elif event.input.id == "inp_penalty_pct": self.penalty_percentage = float(val) / 100.0
            elif event.input.id == "inp_lw_lockout": self.lw_lockout = int(val)
            elif event.input.id == "inp_sentiment_guard": self.sentiment_guard = float(val)
            elif event.input.id == "inp_shield_time": self.shield_time = int(val)
            elif event.input.id == "inp_shield_reach": self.shield_reach = int(val)
            elif event.input.id == "inp_risk_alloc": self.total_risk_cap = float(val) if val else 30.0
        except: pass

        # We only auto-save specific configuration inputs to avoid disk thrashing
        if event.input.id in {"inp_amount", "inp_tp", "inp_sl", "inp_min_diff", "inp_min_price", "inp_max_price", "inp_skeptic_odds", "inp_skeptic_guess", "inp_penalty_pct", "inp_shield_time", "inp_shield_reach", "inp_risk_alloc", "inp_lw_lockout", "inp_sentiment_guard", "inp_time_tp"}:
            self.save_settings()

    @on(RadioSet.Changed, "#rs_bet_mode")
    def on_bet_mode_changed(self, event: RadioSet.Changed):
        """Auto-persist bet mode toggle."""
        if not getattr(self, "is_initializing", False):
            self.save_settings()
            self.log_msg(f"SETTING: Bet Mode | Value: {event.pressed.label}", level="SYS")

    async def on_mount(self) -> None:
        self.is_initializing = True
        self.app_active = True
        self.init_web3()
        self.init_live_broker()
        # Log the HTML file path once at start
        if self.log_settings["verification_html"]:
            self.log_msg(f"VERIFICATION LOG: {self.html_log_file}", level="ADMIN")
        
        # Display other active log files
        b_log = os.path.basename(self.sim_broker.log_file)
        c_log = os.path.basename(self.console_log_file)
        m_log = os.path.basename(self.mom_adv_log_file)
        
        if self.log_settings.get("main_csv", True): self.log_msg(f"MAIN CSV LOG:     {b_log}", level="ADMIN")
        if self.log_settings.get("console_txt", True): self.log_msg(f"CONSOLE LOG:      {c_log}", level="ADMIN")
        if self.log_settings.get("momentum_csv", True): self.log_msg(f"MOMENTUM LOG:     {m_log}", level="ADMIN")
        
        # self.log_msg(f"Simulation Started. Bal: ${self.sim_broker.balance}")
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

        self.set_interval(1, lambda: self.fetch_market_loop() if getattr(self, "app_active", False) else None)
        self.set_interval(1, lambda: self.update_timer() if getattr(self, "app_active", False) else None)
        self.set_interval(1, lambda: self.check_dump_log() if getattr(self, "app_active", False) else None)
        self.set_interval(0.5, lambda: self.toggle_blinks() if getattr(self, "app_active", False) else None)

        # --- RESTORE PERSISTED SETTINGS ---
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r") as f:
                    s = json.load(f)
                # UI inputs
                sync_map_ui = {
                    "inp_amount": "inp_amount", "inp_tp": "inp_tp", "inp_sl": "inp_sl",
                    "inp_min_diff": "inp_min_diff", "inp_min_price": "inp_min_price",
                    "inp_max_price": "inp_max_price", "inp_skeptic_odds": "inp_skeptic_odds",
                    "inp_skeptic_guess": "inp_skeptic_guess", "inp_penalty_pct": "inp_penalty_pct",
                    "inp_sim_bal": "inp_sim_bal", "inp_time_tp": "inp_time_tp"
                }
                for fid, json_key in sync_map_ui.items():
                    if json_key in s:
                        try: 
                            val = str(s[json_key])
                            self.query_one(f"#{fid}").value = val
                        except Exception as e:
                            self.log_msg(f"[dim]Could not load {fid}: {e}[/]")
                
                # Extended UI Fields (Whale Shield / Risk Cap)
                if "shield_time" in s:
                    self.query_one("#inp_shield_time").value = str(s["shield_time"])
                if "shield_reach" in s:
                    self.query_one("#inp_shield_reach").value = str(s["shield_reach"])
                if "inp_risk_alloc" in s:
                    self.query_one("#inp_risk_alloc").value = str(s["inp_risk_alloc"])
                
                # Separate loading for total_risk_cap (Window Limit)
                self.total_risk_cap = float(s.get("total_risk_cap", 30.0))
                
                if "bet_mode" in s:
                    if s["bet_mode"] == "pct":
                        self.query_one("#rb_pct").value = True
                    else:
                        self.query_one("#rb_fixed").value = True

                # Assign to variables for engine access
                self.global_skeptic_odds = float(s.get("inp_skeptic_odds", 0.05))
                self.global_skeptic_guess = float(s.get("inp_skeptic_guess", 0.03))
                if "volatility_scaling" in s:
                    self.volatility_scaling.update(s["volatility_scaling"])
                self.penalty_percentage = float(s.get("inp_penalty_pct", 10)) / 100.0
                # self.total_risk_cap already handled above
                self.exec_safety_mode = s.get("exec_safety_mode", "global_lock")
                self.sl_plus_mode = bool(s.get("sl_plus_mode", True))
                self.grow_riskbankroll = bool(s.get("grow_riskbankroll", False))
                self.mom_buy_mode = s.get("mom_buy_mode", "STD")  # "STD" or "PRE"
                self.bounce_mode = bool(s.get("bounce_mode", False))
                self.bounce_dip_cents = float(s.get("bounce_dip_cents", 0.5))
                self.lw_lockout = int(s.get("lw_lockout", 20))
                self.sentiment_guard = float(s.get("sentiment_guard", 15.0))

                # Restore committed TP/SL from saved values
                try: self.committed_tp = float(s.get("inp_tp", 95)) / 100
                except: pass
                try: self.committed_sl = float(s.get("inp_sl", 40)) / 100
                except: pass
                
                # Checkboxes
                try: self.query_one("#cb_tp_active").value = bool(s.get("cb_tp_active", False))
                except: pass
                try: self.query_one("#cb_hdo").value = bool(s.get("cb_hdo", False))
                except: pass
                try: self.query_one("#cb_one_trade").value = bool(s.get("cb_one_trade", False))
                except: pass
                try: self.query_one("#cb_time_tp").value = bool(s.get("cb_time_tp", False))
                except: pass
                
                try: self.query_one("#cb_bounce").value = self.bounce_mode
                except: pass

                # Restore log settings
                log_sets = s.get("log_settings", {})
                for k, v in log_sets.items():
                    self.log_settings[k] = v
                
                # Sync log switches
                sync_logs = {
                    "#cb_log_main": "main_csv",
                    "#cb_log_console": "console_txt",
                    "#cb_log_mom": "momentum_csv",
                    "#cb_log_html": "verification_html"
                }
                for qid, k in sync_logs.items():
                    try: self.query_one(qid).value = bool(self.log_settings.get(k, True))
                    except: pass

                # Restore algorithm checkbox states
                algo_states = s.get("algo_enabled", {})
                for code in ALGO_INFO:
                    cid = f"#cb_{code.lower()}"
                    try:
                        if code in algo_states:
                            self.query_one(cid).value = bool(algo_states[code])
                    except: pass
                
                # Restore Coiled Cobra settings
                cco = self.scanners.get("CoiledCobra")
                if cco and "cco_settings" in s:
                    cco_s = s["cco_settings"]
                    cco.coil_threshold_pct = cco_s.get("thresh", 0.25)
                    cco.coil_lookback_history = cco_s.get("history", 60)
                    cco.coil_lookback_recent = cco_s.get("recent", 10)

                # Restore GrindSnap settings
                gri = self.scanners.get("GrindSnap")
                if gri and "gri_settings" in s:
                    gri_s = s["gri_settings"]
                    gri.grind_duration = gri_s.get("grind_duration", 100)
                    gri.snap_duration = gri_s.get("snap_duration", 20)
                    gri.min_slope_pct = gri_s.get("min_slope_pct", 0.1)
                    gri.reversal_ratio = gri_s.get("reversal_ratio", 0.60)

                # Restore HDO threshold
                hdo = self.scanners.get("HDO")
                if hdo and "hdo_threshold" in s:
                    try:
                        hdo.trigger_threshold = float(s["hdo_threshold"])
                    except Exception as e:
                        self.log_msg(f"[dim]Could not load HDO threshold: {e}[/]")

                # Restore MOM Adv Settings
                if "mom_adv_settings" in s:
                    self.mom_adv_settings.update(s["mom_adv_settings"])
                if "mm2_adv_settings" in s:
                    self.mm2_adv_settings.update(s["mm2_adv_settings"])

                # Restore bet mode
                if s.get("bet_mode") == "pct":
                    try: self.query_one("#rb_pct").value = True
                    except: pass
                else:
                    try: self.query_one("#rb_fixed").value = True
                    except: pass

                # self.log_msg("[dim]Settings restored from disk.[/]")
        except Exception as e:
            self.log_msg(f"[yellow]Could not restore settings: {e}[/]")
        # -----------------------------------

        if self.start_live_mode:
            self.query_one("#cb_live").value = True 

        # Delay unsetting the initialization flag to let queued events clear
        # Increased to 3s to handle more persistent async event flushes
        self.set_timer(3.0, self._finalize_startup_logs)

    def on_unmount(self) -> None:
        self.app_active = False
        self.log_msg("[dim]Shutting down...[/]", level="ADMIN")
        
        # Finalize logs immediately before stopping managers
        self.finalize_html_log()
        
        if hasattr(self, "market_data_manager"):
            self.market_data_manager.stop()

        self.save_settings()

        # Mark session as SETTLED on web dash
        try:
            self.ftp_manager.push_session_stats(status="SETTLED")
            self.ftp_manager.force_update_index()  # Force immediate index update for settlement
        except: pass
            
        if hasattr(self, "ftp_manager"):
            # ftp_manager threads are daemon, but we should clear the queue if needed
            # for now, letting them flush naturally is usually fine, but 
            # we want to avoid long hangs.
            pass

    def _finalize_startup_logs(self):
        """Finalizes initialization: logs summary and allows further events to log."""
        try:
            active = [code for code in ALGO_INFO if self.query_one(f"#cb_{code.lower()}").value]
            if active:
                self.log_msg(f"[bold cyan]Active Scanners:[/] {', '.join(active)}", level="ADMIN")
        except Exception as e:
            self.log_msg(f"[dim]Note: Startup scanner summary skipped ({e})[/]", level="ADMIN")
        finally:
            self.is_initializing = False
            self.log_msg("[dim]System initialization complete. Event logging enabled.[/]", level="ADMIN")

    @on(Checkbox.Changed, "#cb_live")
    def on_live_toggle(self, event: Checkbox.Changed):
        if event.value: 
            self.saved_sim_bankroll = self.risk_manager.risk_bankroll
            self.log_msg("[bold red]LIVE MODE ENABLED! All Algos deselected for safety.[/]")
            for code in ALGO_INFO:
                try: self.query_one(f"#cb_{code.lower()}").value = False
                except: pass
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
    @on(Checkbox.Changed, "#cb_hdo")
    @on(Checkbox.Changed, "#cb_tranche")
    @on(Checkbox.Changed, "#cb_strong")
    @on(Checkbox.Changed, "#cb_one_trade")
    @on(Checkbox.Changed, "#cb_whale")
    @on(Checkbox.Changed, "#cb_bounce")
    @on(Checkbox.Changed, "#cb_time_tp")
    def on_settings_checkbox_changed(self, event: Checkbox.Changed):
        """Auto-persist setting checkboxes and log them."""
        cid = event.checkbox.id
        # Update runtime state for bounce toggle
        if cid == "cb_bounce":
            self.bounce_mode = event.value
        
        if not getattr(self, "is_initializing", False):
            self.save_settings()
            
        name = ""
        if cid == "cb_tp_active": name = "TP/SL Monitoring"
        elif cid == "cb_strong": name = "Strong Only Mode"
        elif cid == "cb_one_trade": name = "1 Trade Max Guard"
        elif cid == "cb_whale": name = "Whale Protect"
        elif cid == "cb_bounce": name = "Bounce Entry Mode"
        elif cid == "cb_time_tp": name = "Time-Based TP"
        elif cid == "cb_tranche": name = "Tranche Exits"
        elif cid == "cb_hdo": name = "Hedge Direction Opposite"
        
        if name:
            state = "ON" if event.value else "OFF"
            self.log_msg(f"SETTING: {name} | Status: {state}", level="SYS")

    def log_msg(self, msg, level="INFO"):
        """
        Enhanced logging with TTG (Time-To-Go) prefixes and categorization.
        Levels: ADMIN (Blue), SCAN (Gray), TRADE (Green/Red), MONEY (Gold), ERROR (Banner)
        """
        now_ts = time.time()
        timestamp = datetime.fromtimestamp(now_ts).strftime('%H:%M:%S')
        
        # Calculate TTG Prefix [MM:SS]
        ttg_str = ""
        if self.market_data.get("start_ts", 0) > 0:
            rem = max(0, self.config.WINDOW_SECONDS - int(now_ts - self.market_data["start_ts"]))
            ttg_str = f"[{rem//60:02d}:{rem%60:02d}]"

        # Color/Category Mapping
        lv = level.upper()
        level_map = {
            "ADMIN": "SYS", 
            "SCAN": "SCAN", 
            "TRADE": "EXEC", 
            "MONEY": "RSLT", 
            "ERROR": "ERR", 
            "INFO": "INF",
            "MARKET": "MARKET",
            "VOLAT": "VOLAT",
            "BIAS": "BIAS",
            "STATS": "STATS",
            "SYS": "SYS"
        }
        short_lv = level_map.get(lv, lv[:6])
        tag = f"[{short_lv}]"
        prefix = f"{ttg_str}{tag} "

        # Outcome-based coloring (overrides category color)
        msg_lower = msg.lower()
        is_profit = any(x in msg_lower for x in ["profit", "win", "pnl: +", "rev: +", "refill: +"])
        is_loss = any(x in msg_lower for x in ["loss", "lose", "failed", "pnl: -", "err"])
        
        if not getattr(self, "session_date_logged", False):
            self.session_date_logged = True
            date_str = datetime.fromtimestamp(now_ts).strftime('%Y-%m-%d')
            # self.query_one(RichLog).write(f"[bold white]=== SESSION START: {date_str} ===[/]")

        if is_profit:         display_msg = f"[bold green]{prefix}{msg}[/]"
        elif is_loss:         display_msg = f"[bold red]{prefix}{msg}[/]"
        elif short_lv == "SYS":     display_msg = f"[bold skyblue]{prefix}{msg}[/]"
        elif short_lv == "SCAN":    display_msg = f"[dim white]{prefix}{msg}[/]"
        elif short_lv == "EXEC":    display_msg = f"[bold green]{prefix}{msg}[/]"
        elif short_lv == "RSLT":    display_msg = f"[bold gold3]{prefix}{msg}[/]"
        elif short_lv == "ERR":     display_msg = f"[bold white on red] !!! {short_lv}: {msg} !!! [/]"
        elif short_lv == "MARKET":  display_msg = f"[bold cyan]{prefix}{msg}[/]"
        elif short_lv == "VOLAT":   display_msg = f"[bold magenta]{prefix}{msg}[/]"
        elif short_lv == "BIAS":    display_msg = f"[bold yellow]{prefix}{msg}[/]"
        elif short_lv == "STATS":   display_msg = f"[bold white]{prefix}{msg}[/]"
        else:                       display_msg = f"{prefix}{msg}" # Default INFO style

        # [NEW] Display Filter Logic (Option 2)
        should_display = True
        if self.log_display_mode == "HIDE":
            if short_lv in self.log_display_filter: should_display = False
        elif self.log_display_mode == "ONLY":
            if short_lv not in self.log_display_filter: should_display = False
        
        if not should_display:
            # We still fall through to file logging below, but skip the RichLog write
            pass
        else:
            try:
                self.query_one(RichLog).write(display_msg)
            except:
                # During shutdown or if UI is not ready, skip RichLog
                pass
        
        # Mirror to console log file for persistence (pure ASCII scrubbing)
        import re
        # 1. Strip Rich tags
        clean_msg = re.sub(r'\[/?[a-z #0-9,.]+\]', '', display_msg if lv != "INFO" else msg)
        # 2. Strip non-ASCII characters (emojis/symbols)
        clean_msg = clean_msg.encode('ascii', 'ignore').decode('ascii').strip()
        
        try:
            if getattr(self, "log_settings", {}).get("console_txt", True):
                with open(self.console_log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{timestamp}] {clean_msg}\n")
        except: pass

    def dump_state_log(self):
        try:
            is_live = False
            try:
                cb_live = self.query_one("#cb_live")
                if cb_live.is_mounted:
                    is_live = cb_live.value
            except: pass
            
            self.sim_broker.log_snapshot(self.market_data, self.time_rem_str, is_live, self.live_broker.balance, self.risk_manager.risk_bankroll)
            
            # Push to Web Dashboard
            try:
                self.ftp_manager.push_session_stats(
                    pnl=self.session_pnl,
                    trades=self.session_total_trades,
                    status="ACTIVE",
                    interval=f"{self.config.MARKET_FREQ}M"
                )
            except: pass
        except Exception as e:
            # Silent fail to prevent interval crash if UI or files are locked
            pass

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
            # [CRITICAL] Guard: If UI is not fully mounted or already unmounting, 
            # query_one will fail or return default False, which would destroy user settings.
            try:
                sentinel = self.query_one("#cb_mom")
                if not sentinel.is_mounted: return 
            except:
                return # Abort save if UI is not queryable

            # Gather current UI field values (widgets must be mounted)
            def _v(wid, default=""):
                try: return self.query_one(wid).value
                except: return default
            def _cb(wid, default=False):
                try: return self.query_one(wid).value
                except: return default

            def _si(wid, default=0):
                try: return int(self.query_one(wid).value)
                except: return default

            data = {
                "scanner_weights": self.scanner_weights,
                "shield_time": _si("#inp_shield_time", 45),
                "shield_reach": _si("#inp_shield_reach", 5),
                "total_risk_cap": getattr(self, "total_risk_cap", 30.0),
                "inp_risk_alloc": _v("#inp_risk_alloc", "0.0"),
                "inp_amount":    _v("#inp_amount",    "1.00"),
                "inp_tp":        _v("#inp_tp",        "95"),
                "inp_sl":        _v("#inp_sl",        "40"),
                "inp_min_diff":  _v("#inp_min_diff",  "0"),
                "inp_min_price": _v("#inp_min_price", "0.55"),
                "inp_max_price": _v("#inp_max_price", "0.80"),
                "inp_skeptic_odds": _v("#inp_skeptic_odds", "0.05"),
                "inp_skeptic_guess": _v("#inp_skeptic_guess", "0.03"),
                "inp_penalty_pct": _v("#inp_penalty_pct", "10"),
                "cb_tp_active":  _cb("#cb_tp_active", False),
                "cb_hdo":        _cb("#cb_hdo", False),
                "cb_one_trade":  _cb("#cb_one_trade", False),
                "cb_bounce":     _cb("#cb_bounce", False),
                "sl_plus_mode":  self.sl_plus_mode,
                "grow_riskbankroll": getattr(self, "grow_riskbankroll", False),
                "mom_buy_mode":  self.mom_buy_mode,
                "bounce_mode":   getattr(self, "bounce_mode", False),
                "bounce_dip_cents": getattr(self, "bounce_dip_cents", 0.5),
                "penalty_percentage": getattr(self, "penalty_percentage", 0.10),
                "bet_mode":      "fixed", # Default
                "algo_enabled":  {code: _cb(f"#cb_{code.lower()}", False) for code in ALGO_INFO},
                "nit_settings": self.nit_settings,
                "vsn_settings": self.vsn_settings,
                "rsi_settings": self.rsi_settings,
                "tra_settings": self.tra_settings,
                "mid_settings": self.mid_settings,
                "lat_settings": self.lat_settings,
                "pos_settings": self.pos_settings,
                "ste_settings": self.ste_settings,
                "sli_settings": self.sli_settings,
                "min_settings": self.min_settings,
                "liq_settings": self.liq_settings,
                "cob_settings": self.cob_settings,
                "mes_settings": self.mes_settings,
                "gri_settings": self.gri_settings,
                "npa_settings": self.npa_settings,
                "fak_settings": self.fak_settings,
                "mea_settings": self.mea_settings,
                "vol_settings": self.vol_settings,
                "mos_settings": self.mos_settings,
                "zsc_settings": self.zsc_settings,
                "bri_settings": self.bri_settings,
                "wcp_settings": self.wcp_settings,
                "vpoc_settings": self.vpoc_settings,
                "sdp_settings": self.sdp_settings,
                "div_settings": self.div_settings,
                "ssi_settings": self.ssi_settings,
                "mom_adv_settings": self.mom_adv_settings,
                "mm2_adv_settings": self.mm2_adv_settings,
                "lw_lockout": self.lw_lockout,
                "sentiment_guard": self.sentiment_guard,
                "auto_sync_risk": self.auto_sync_risk,
                "exec_safety_mode": self.exec_safety_mode,
                "trend_efficiency": self.trend_efficiency,
                "market_freq": self.config.MARKET_FREQ,
                "log_settings": self.log_settings,  # Persist log toggles
                "volatility_scaling": self.volatility_scaling,
                "conviction_scaling":  self.conviction_scaling,
                "value_reentry": self.value_reentry
            }
            
            # [SANITY] Try to get bet_mode from UI if possible (it's not a standard value/checkbox)
            try:
                rs = self.query_one("#rs_bet_mode")
                if rs.pressed_button and rs.pressed_button.id == "rb_pct":
                    data["bet_mode"] = "pct"
            except: pass
            
            # Save HDO threshold from scanner object
            hdo_scanner = self.scanners.get("HDO")
            if hdo_scanner:
                data["hdo_threshold"] = getattr(hdo_scanner, "trigger_threshold", 0.59)
            
            cco = self.scanners.get("CoiledCobra")
            if cco:
                data["cco_settings"] = {
                    "thresh": cco.coil_threshold_pct,
                    "history": cco.coil_lookback_history,
                    "recent": cco.coil_lookback_recent
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
                self.safe_call(self.log_msg, f"[green]Web3 Connected via {rpc} (Chainlink Active)[/]")
                return
            except: continue
        self.safe_call(self.log_msg, "[red]All Web3 RPCs Failed. Using Binance backup.[/]")

    @work(exclusive=True, thread=True)
    def init_live_broker(self):
        if not getattr(self, "app_active", False): return
        self.safe_call(self.log_msg, "[dim]Initializing Wallet background connection...[/]", level="ADMIN")
        try:
            self.live_broker.init_client()
            if not getattr(self, "app_active", False): return
            if self.live_broker.client:
                # Clarify this is the "Wallet" balance to avoid confusion with SIM balance
                self.safe_call(self.log_msg, f"[bold green]Live Wallet Connected.[/] Balance: ${self.live_broker.balance:.2f}", level="ADMIN")
                self.safe_call(self.update_balance_ui)
            else:
                self.safe_call(self.log_msg, "[yellow]Live Wallet: No Private Key found. LIVE mode disabled.[/]", level="ADMIN")
        except Exception as e:
            if getattr(self, "app_active", False):
                self.safe_call(self.log_msg, f"[bold red]Live Wallet Init Error:[/] {e}", level="ERROR")


    def finalize_html_log(self):
        # Use a latch to ensure we only write the closing tags once
        if getattr(self, "_html_finalized", False):
            return
        if hasattr(self, "html_log_file") and os.path.exists(self.html_log_file):
            try:
                with open(self.html_log_file, "r+", encoding="utf-8") as f:
                    content = f.read()
                    if "</tbody></table>" not in content:
                        # Check if we have any actual data rows
                        has_data = "<tr class=" in content and "SESSION_DATA_PLACEHOLDER" not in content
                        
                        if not has_data:
                            # Replace placeholder with no-data message
                            if "<!-- SESSION_DATA_PLACEHOLDER -->" in content:
                                content = content.replace(
                                    "<!-- SESSION_DATA_PLACEHOLDER -->\n",
                                    f'<tr><td colspan="12"><div class="no-data">📊 No trading activity recorded during this session<br><small>Session ended early or no windows were processed</small></div></td></tr>\n'
                                )
                        else:
                            # Remove placeholder if data was added
                            content = content.replace("<!-- SESSION_DATA_PLACEHOLDER -->\n", "")
                        
                        # Write the final content
                        f.seek(0)
                        f.write(content)
                        f.truncate()
                        f.seek(0, os.SEEK_END)
                        f.write("</tbody></table></body></html>\n")
                        
                self._html_finalized = True
                # Final FTP upload
                if self.log_settings.get("verification_html", True):
                    self.ftp_manager.upload_html_log(self.html_log_file)
            except Exception as e:
                self.log_msg(f"[dim]Warning: Could not finalize HTML log: {e}[/]", level="ERROR")

    def update_balance_ui(self):
        is_live = self.query_one("#cb_live").value
        lbl = self.query_one("#header_stats")
        cap_display = f" (B.R.: ${self.risk_manager.risk_bankroll:.2f})" if self.risk_initialized else ""
        if is_live:
            lbl.update(f"[bold red]{self.config.MARKET_FREQ}-LIVE[/] | Bal: ${self.live_broker.balance:.2f}{cap_display}")
            lbl.classes = "live_mode"
        else:
            lbl.update(f"{self.config.MARKET_FREQ}-SIM | Bal: ${self.sim_broker.balance:.2f}{cap_display}")
            lbl.classes = ""

    def update_sell_buttons(self):
        md = self.market_data
        is_live = self.query_one("#cb_live").value
        btn_su = self.query_one("#btn_sell_up"); btn_sd = self.query_one("#btn_sell_down")
        
        # Calculate counts for labels
        up_cnt = len([i for i in self.window_bets.values() if i.get("side") == "UP" and not i.get("closed")])
        dn_cnt = len([i for i in self.window_bets.values() if i.get("side") == "DOWN" and not i.get("closed")])

        if is_live:
            btn_su.label = f"SELL UP ({up_cnt} LIVE)" if up_cnt > 0 else "SELL UP"
            btn_sd.label = f"SELL DN ({dn_cnt} LIVE)" if dn_cnt > 0 else "SELL DN"
        else:
            su = self.sim_broker.shares["UP"]; sd = self.sim_broker.shares["DOWN"]
            btn_su.label = f"SELL UP ({up_cnt})\n(${su * md['up_bid']:.2f})" if su > 0 else "SELL UP"
            btn_sd.label = f"SELL DN ({dn_cnt})\n(${sd * md['down_bid']:.2f})" if sd > 0 else "SELL DN"

    # --- Trade engine methods are inherited from TradeEngineMixin ---
    # fetch_market_loop, _check_tpsl, _run_last_second_exit, update_timer,
    # _check_bankroll_exhaustion, trigger_settlement, _add_risk_revenue,
    # trigger_buy, trigger_sell_all

    def analyze_pre_buy_conditions(self):
        """Analyze current market conditions for pre-buy decision based on advanced settings."""
        self.log_msg("[bold cyan]🔍 PRE-BUY ANALYSIS:[/] Evaluating market conditions...", level="ADMIN")
        
        try:
            # Get current market data
            md = self.market_data
            s = self.mom_adv_settings
            
            # Calculate key metrics
            atr_now = getattr(self.market_data_manager, "atr_5m", 0) or md.get("atr_5m", 0)
            btc_price = md.get("btc_price", 0)
            btc_open = md.get("btc_open", 0)
            btc_diff = btc_price - btc_open
            btc_range = md.get("btc_dyn_rng", 0)
            
            # Polymarket metrics
            up_ask = md.get("up_ask", 0)
            down_ask = md.get("down_ask", 0)
            up_bid = md.get("up_bid", 0)
            down_bid = md.get("down_bid", 0)
            odds_score = md.get("odds_score", 0)
            
            # Trend metrics
            trend_1h = md.get("trend_1h", "NEUTRAL")
            rsi_1m = md.get("rsi_1m", 50)
            
            # Determine ATR tier
            atr_low = s.get("atr_low", 20)
            atr_high = s.get("atr_high", 40)
            if atr_now <= atr_low:
                tier = "STABLE"
                tier_color = "[green]"
                offset = s.get("stable_offset", -5)
            elif atr_now >= atr_high:
                tier = "CHAOS"
                tier_color = "[red]"
                offset = s.get("chaos_offset", 10)
            else:
                tier = "NEUTRAL"
                tier_color = "[yellow]"
                offset = 0
            
            # Calculate price imbalance
            price_imbalance = (up_ask - down_ask) * 100  # in cents
            bid_imbalance = (up_bid - down_bid) * 100
            
            # Analysis factors
            factors = []
            up_score = 0
            down_score = 0
            
            # 1. Trend Analysis
            if trend_1h in ["S-UP", "M-UP", "W-UP"]:
                up_score += 2
                factors.append(f"Trend 1H: [green]BULLISH[/] ({trend_1h}) [+2]")
            elif trend_1h in ["S-DOWN", "M-DOWN", "W-DOWN"]:
                down_score += 2
                factors.append(f"Trend 1H: [red]BEARISH[/] ({trend_1h}) [+2]")
            else:
                factors.append(f"Trend 1H: [yellow]NEUTRAL[/] ({trend_1h}) [0]")
            
            # 2. BTC Movement Analysis
            if abs(btc_diff) > 50:  # Significant move
                if btc_diff > 0:
                    up_score += 1
                    factors.append(f"BTC Move: [green]+${btc_diff:.0f}[/] [+1]")
                else:
                    down_score += 1
                    factors.append(f"BTC Move: [red]${btc_diff:.0f}[/] [+1]")
            else:
                factors.append(f"BTC Move: [yellow]${btc_diff:.0f}[/] [0]")
            
            # 3. RSI Analysis
            if rsi_1m > 70:
                down_score += 1
                factors.append(f"RSI 1m: [red]{rsi_1m:.0f} (Overbought)[/] [+1]")
            elif rsi_1m < 30:
                up_score += 1
                factors.append(f"RSI 1m: [green]{rsi_1m:.0f} (Oversold)[/] [+1]")
            else:
                factors.append(f"RSI 1m: [yellow]{rsi_1m:.0f} (Neutral)[/] [0]")
            
            # 4. Polymarket Odds Analysis
            if abs(odds_score) > 5:  # Significant odds skew
                if odds_score > 0:
                    up_score += 1
                    factors.append(f"Odds Score: [green]+{odds_score:.1f}¢[/] (UP favored) [+1]")
                else:
                    down_score += 1
                    factors.append(f"Odds Score: [red]{odds_score:.1f}¢[/] (DN favored) [+1]")
            else:
                factors.append(f"Odds Score: [yellow]{odds_score:.1f}¢[/] (Balanced) [0]")
            
            # 5. Price Imbalance Analysis
            if abs(price_imbalance) > 2:  # More than 2 cents imbalance
                if price_imbalance > 0:
                    down_score += 1  # Higher UP ask suggests UP is expensive
                    factors.append(f"Ask Spread: [red]+{price_imbalance:.1f}¢[/] (UP premium) [+1 DN]")
                else:
                    up_score += 1  # Higher DOWN ask suggests DN is expensive
                    factors.append(f"Ask Spread: [green]{price_imbalance:.1f}¢[/] (DN premium) [+1 UP]")
            else:
                factors.append(f"Ask Spread: [yellow]{price_imbalance:.1f}¢[/] (Balanced) [0]")
            
            # 6. ATR Tier Adjustment
            factors.append(f"ATR Tier: {tier_color}{tier}[/] (ATR={atr_now:.1f}) [Offset: {offset:+}¢]")
            
            # 7. Volatility Analysis
            if btc_range > 100:
                factors.append(f"Volatility: [red]HIGH[/] (${btc_range:.0f} range) [Caution]")
            elif btc_range > 50:
                factors.append(f"Volatility: [yellow]MODERATE[/] (${btc_range:.0f} range)")
            else:
                factors.append(f"Volatility: [green]LOW[/] (${btc_range:.0f} range)")
            
            # Calculate final recommendation
            net_score = up_score - down_score
            if net_score >= 2:
                recommendation = "UP"
                rec_color = "[green]"
                confidence = "STRONG" if net_score >= 3 else "MODERATE"
            elif net_score <= -2:
                recommendation = "DOWN"
                rec_color = "[red]"
                confidence = "STRONG" if net_score <= -3 else "MODERATE"
            else:
                recommendation = "NEUTRAL"
                rec_color = "[yellow]"
                confidence = "WEAK"
            
            # Output analysis
            self.log_msg("", level="ADMIN")
            self.log_msg(f"[bold cyan]📊 MARKET SNAPSHOT:[/]", level="ADMIN")
            self.log_msg(f"  BTC: ${btc_price:,.2f} (Open: ${btc_open:,.2f}, Change: ${btc_diff:+,.2f})", level="ADMIN")
            self.log_msg(f"  Polymarket: UP {up_ask*100:.1f}¢/{up_bid*100:.1f}¢ | DN {down_ask*100:.1f}¢/{down_bid*100:.1f}¢", level="ADMIN")
            self.log_msg(f"  Indicators: RSI={rsi_1m:.0f} | ATR={atr_now:.1f} | Range=${btc_range:.0f}", level="ADMIN")
            self.log_msg("", level="ADMIN")
            
            self.log_msg(f"[bold cyan]⚖️  ANALYSIS FACTORS:[/]", level="ADMIN")
            for factor in factors:
                self.log_msg(f"  • {factor}", level="ADMIN")
            self.log_msg("", level="ADMIN")
            
            self.log_msg(f"[bold cyan]🎯 RECOMMENDATION:[/]", level="ADMIN")
            self.log_msg(f"  Direction: {rec_color}{recommendation}[/]", level="ADMIN")
            self.log_msg(f"  Confidence: {confidence} (Score: {net_score:+d})", level="ADMIN")
            self.log_msg(f"  UP Score: {up_score} | DOWN Score: {down_score}", level="ADMIN")
            
            # Advanced mode specific guidance
            if self.mom_buy_mode == "ADV":
                self.log_msg("", level="ADMIN")
                self.log_msg(f"[bold cyan]🔧 ADVANCED MODE GUIDANCE:[/]", level="ADMIN")
                if tier == "STABLE" and s.get("auto_stn_chaos", False):
                    self.log_msg(f"  • Auto-switch to [green]STN[/] mode in stable conditions", level="ADMIN")
                elif tier == "CHAOS" and s.get("auto_pbn_stable", False):
                    self.log_msg(f"  • Auto-switch to [green]PBN[/] mode in chaos conditions", level="ADMIN")
                
                # Threshold adjustment
                mom_scanner = self.scanners.get("Momentum")
                if mom_scanner:
                    base_threshold = getattr(mom_scanner, "base_threshold", 0.6) * 100  # Convert to cents
                    adjusted_threshold = base_threshold + offset
                    self.log_msg(f"  • Base threshold: {base_threshold:.0f}¢ → Adjusted: {adjusted_threshold:+.0f}¢", level="ADMIN")
            
            # Risk warnings
            if abs(btc_diff) > 200:
                self.log_msg("", level="ADMIN")
                self.log_msg(f"[bold red]⚠️  RISK WARNING:[/] Large BTC move detected (${btc_diff:+,.2f})", level="ADMIN")
            
            if atr_now > atr_high * 1.5:
                self.log_msg("", level="ADMIN")
                self.log_msg(f"[bold red]⚠️  VOLATILITY WARNING:[/] ATR ({atr_now:.1f}) significantly above chaos threshold", level="ADMIN")
            
            self.log_msg("", level="ADMIN")
            self.log_msg("[bold cyan]✅ Analysis complete[/]", level="ADMIN")
            
        except Exception as e:
            self.log_msg(f"[bold red]❌ Analysis error:[/] {e}", level="ADMIN")

    async def on_button_pressed(self, event: Button.Pressed):
        """Handle button presses."""
        bid = event.button.id
        if bid == "btn_settings":
            self.push_screen(GlobalSettingsModal(self))
        elif bid == "btn_pre_up" or bid == "btn_pre_down":
            side = "UP" if "up" in bid else "DOWN"
            self.log_msg(f"[bold cyan]Admin:[/] Executing immediate Pre-Buy {side} for the next window...")
            
            def _do_immediate_prebuy():
                try:
                    next_ts = self.market_data.get("start_ts", 0) + self.config.WINDOW_SECONDS
                    if next_ts <= self.config.WINDOW_SECONDS:
                        self.safe_call(self.log_msg, "[bold red]Admin Error:[/] No active window to base 'next' window off of.")
                        return
                        
                    next_slug = f"btc-updown-{self.config.MARKET_FREQ}m-{next_ts}"
                    d = self.market_data_manager.fetch_polymarket(next_slug)
                    
                    price = d.get("up_ask", 0) if side == "UP" else d.get("down_ask", 0)
                    if price <= 0:
                        self.safe_call(self.log_msg, "[bold red]Admin Error:[/] Next window prices unavailable. Cannot pre-buy.")
                        return
                        
                    token_id = d.get("up_id" if side == "UP" else "down_id")
                    
                    try: is_live = self.query_one("#cb_live").value
                    except: is_live = False
                    
                    try: pre_bs = float(self.query_one("#inp_amount").value)
                    except: pre_bs = 1.0
                        
                    if pre_bs > self.risk_manager.risk_bankroll: pre_bs = self.risk_manager.risk_bankroll
                    
                    # Enforce Global Window Cap for Manual Pre-Buy
                    total_window_cost = sum(info.get("cost", 0) for info in self.window_bets.values())
                    remaining_cap = max(0, getattr(self, "total_risk_cap", 30.0) - total_window_cost)
                    if pre_bs > remaining_cap:
                        pre_bs = remaining_cap
                        if pre_bs < 1.00:
                            self.safe_call(self.log_msg, f"[yellow]MANUAL PRE-BUY ABORTED:[/] Risk Cap Reached (${total_window_cost:.2f}/$30)")
                            return

                    if pre_bs < 1.00: pre_bs = 1.00 # hard floor for execution
                    
                    ok, msg, act_shares, act_price = self.trade_executor.execute_buy(
                        is_live, side, pre_bs, price, token_id, 
                        context={}, reason="PreBuy_NextWindow"
                    )
                    
                    if ok:
                        self.session_total_trades += 1
                        import time
                        def _commit():
                            self.pre_buy_pending = {
                                "side": side, "entry": act_price, "cost": pre_bs, 
                                "shares": act_shares, "algorithm": "Admin_PreBuy",
                                "slug": next_slug, "reason": "Immediate Manual"
                            }
                        self.risk_manager.register_bet(pre_bs)
                        self.safe_call(self.log_msg, f"[bold green]🚀 MANUAL PRE-BUY EXECUTED:[/] {side} @ {act_price*100:.1f}¢ | ${pre_bs:.2f} committed into {next_slug}")
                        self.safe_call(self.update_balance_ui)
                        self.safe_call(_commit)
                    else:
                        self.safe_call(self.log_msg, f"[bold red]🚀 MANUAL PRE-BUY FAILED:[/] {msg}")
                except Exception as e:
                    self.safe_call(self.log_msg, f"[bold red]🚀 MANUAL PRE-BUY ERROR:[/] {e}")
                    
            import threading
            threading.Thread(target=_do_immediate_prebuy, daemon=True).start()
        elif "btn_buy_" in bid: 
            await self.trigger_buy("UP" if "_up" in bid else "DOWN")
        elif "btn_sell_" in bid:
            await self.trigger_sell_all("UP" if "_up" in bid else "DOWN")

    async def perform_frequency_switch(self, new_freq, exit_positions=False):
        """Orchestrates a safe transition between market frequencies."""
        try:
            old_freq = self.config.MARKET_FREQ
            self.log_msg(f"[bold yellow]🔄 FREQUENCY SWITCH INITIATED:[/] {old_freq}m -> {new_freq}m", level="SYS")
            
            # 1. Handle Positions
            if exit_positions:
                pos_count = len(self.window_bets)
                if pos_count > 0:
                    self.log_msg(f"[bold red]Exiting {pos_count} positions before switch...[/]", level="TRADE")
                    await self.trigger_sell_all("UP")
                    await self.trigger_sell_all("DOWN")
            
            # 2. Show Session Summary
            self.show_session_summary()
            
            # 3. Apply changes to config
            self.config.MARKET_FREQ = new_freq
            
            # 4. Reset Session State (excluding Balance/BR)
            self.session_win_count = 0 
            self.session_total_trades = 0
            self.session_pnl = 0.0
            self.session_windows_settled = 0
            self.window_settled = False
            self.pre_buy_pending = None
            self.pre_buy_triggered = False
            self.hdo_fired_in_window = False
            self.window_realized_revenue = 0.0
            
            # 5. Reset Analytics
            self.mom_analytics = self._reset_mom_analytics()
            for sc in self.scanners.values():
                if hasattr(sc, "reset"): sc.reset() # Some scanners might have state
            
            # 6. Force First-Window Lockout
            self.mid_window_lockout = True
            
            # 7. Update UI
            self.update_balance_ui()
            self.log_msg(f"[bold green]✅ SWITCH COMPLETE:[/] Now trading {new_freq}m markets. [cyan]Lockout Active[/] until first window closes.", level="SYS")
            
            # Save new config
            self.save_settings()
            
        except Exception as e:
            self.log_msg(f"[bold red]ERROR during frequency switch:[/] {e}", level="ERROR")

    def show_session_summary(self):
        """Prints a comprehensive summary of the frequency-specific session being closed."""
        freq = self.config.MARKET_FREQ
        bal = self.sim_broker.balance
        pnl = self.session_pnl
        wins = self.session_win_count
        total = self.session_total_trades
        acc = (wins / total * 100) if total > 0 else 0
        
        self.log_msg("", level="STATS")
        self.log_msg(f"[bold white]══════════════════════════════════════════════════════[/]", level="STATS")
        self.log_msg(f"[bold white]  SESSION TERMINATED: {freq}M MARKET[/]", level="STATS")
        self.log_msg(f"[bold white]══════════════════════════════════════════════════════[/]", level="STATS")
        self.log_msg(f"  [dim]• Final PnL:[/] { '[green]+' if pnl>=0 else '[red]' }${pnl:,.2f}", level="STATS")
        self.log_msg(f"  [dim]• Accuracy:[/]  {acc:.1f}% ({wins}/{total} trades)", level="STATS")
        self.log_msg(f"  [dim]• Windows:[/]   {self.session_windows_settled}", level="STATS")
        self.log_msg(f"  [dim]• Balance:[/]   ${bal:,.2f}", level="STATS")
        self.log_msg(f"[bold white]══════════════════════════════════════════════════════[/]", level="STATS")
        self.log_msg("", level="STATS")
