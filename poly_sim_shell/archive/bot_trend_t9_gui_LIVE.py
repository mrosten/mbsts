import asyncio
"""
Bot: Legacy Trend Strategy (GUI Version)

Visual Terminal User Interface (TUI) for the T+9 Trend Strategy.
- Displays signal strength, timeline, and logs in a visual dashboard.
- Features: 'Sparklines', Signal Bars, and T+3/6/9 Checkpoints.
"""
import curses
import sys
import os
import time
import json
import msvcrt
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from collections import deque

from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# Load .env
load_dotenv()

# --- CONSTANTS ---
STATE_FILE = "live_trade_state.json"
LOG_FILE = "live_trade_log.txt"

# ANSI Constants
ESC = '\033'
CSI = ESC + '['
CLEAR = CSI + '2J'
HOME = CSI + 'H'
HIDE_CURSOR = CSI + '?25l'
SHOW_CURSOR = CSI + '?25h'
RESET = CSI + '0m'
BOLD = CSI + '1m'
DIM = CSI + '2m'

# Colors (Sleek Theme)
COLOR_BORDER = CSI + '90m'     # Dark Gray
COLOR_TITLE  = CSI + '1;37m'   # Bold White (No BG)
COLOR_PRICE_UP  = CSI + '1;32m' # Bright Green
COLOR_PRICE_DN  = CSI + '1;31m' # Bright Red
COLOR_WARN   = CSI + '1;33m'   # Yellow Text (No BG)
COLOR_UI     = CSI + '36m'     # Cyan Text
COLOR_GRAY   = CSI + '90m'     # Dark Gray
COLOR_SUCCESS = CSI + '1;32m'  # Bright Green
COLOR_PURPLE = CSI + '35m'

# Timezones
OFFSET_JERUSALEM = timedelta(hours=2) # IST (UTC+2) - Adjust for DST manually if needed
OFFSET_ET = timedelta(hours=-5)       # ET (UTC-5) 

# Env Vars
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
CHAIN_ID = 137
HOST = "https://clob.polymarket.com"

class LiveTraderGUI:
    def __init__(self):
        # Trading Config
        self.trade_size = 5.5
        self.btc_offset = -86.0
        self.auto_offset = True
        self.last_offset_update = 0
        self.last_trade_ts = 0
        
        # State
        self.is_running = True
        self.ui_state = "SCANNING"  # SCANNING, CONFIRM_BUY, EXECUTING, ERROR
        self.confirm_side = None
        self.confirm_token = None
        self.confirm_price = 0.0
        
        self.active_trade = None
        self.market_url = ""
        self.market_data = {
            "up_id": None, "down_id": None, 
            "up_price": 0.0, "down_price": 0.0,
            "btc_price": 0.0, 
            "open_price": 0.0,
            "start_ts": 0, "end_ts": 0
        }
        self.strategy_triggered = False
        self.seen_t3 = False
        
        # Logs
        self.log_buffer = deque(maxlen=8)
        
        # Networking
        self.session = requests.Session()
        self.client = None
        self.init_client()

    def log(self, msg):
        """Log to memory buffer and file"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}"
        self.log_buffer.append(line)
        try:
            with open(LOG_FILE, "a") as f:
                f.write(line + "\n")
        except: pass

    def init_client(self):
        if not PRIVATE_KEY:
            self.log("CRITICAL: No PRIVATE_KEY in .env!")
            return
        try:
            # Use Proxy if available
            key_acct = Account.from_key(PRIVATE_KEY)
            funder = PROXY_ADDRESS if PROXY_ADDRESS else key_acct.address
            
            self.client = ClobClient(
                host=HOST, 
                key=PRIVATE_KEY, 
                chain_id=CHAIN_ID, 
                signature_type=1 if PROXY_ADDRESS else 0,
                funder=funder
            )
            creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(creds)
            self.log(f"CLOB Client Connected (Funder: {funder})")
        except Exception as e:
            self.log(f"Client Init Error: {str(e)[:50]}")

    # --- Data Fetching ---
    async def fetch_spot_price(self):
        try:
            # Auto-Offset (Every 60s)
            now = time.time()
            if self.auto_offset and (now - self.last_offset_update > 60):
                cg_url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
                r1 = await asyncio.to_thread(self.session.get, cg_url, timeout=3.0)
                cg = float(r1.json()['bitcoin']['usd'])
                
                bin_url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
                r2 = await asyncio.to_thread(self.session.get, bin_url, timeout=1.5)
                raw_b = float(r2.json()["price"])
                
                self.btc_offset = cg - raw_b
                self.last_offset_update = now
                # self.log(f"Offset Calibrated: {self.btc_offset:.2f}")

            # Get Binance Price
            url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
            resp = await asyncio.to_thread(self.session.get, url, timeout=1.5)
            data = resp.json()
            if "price" in data:
                self.market_data["btc_price"] = float(data["price"]) + self.btc_offset
                
                # Check Open Price
                if self.market_data["open_price"] == 0 and self.market_data["start_ts"] > 0:
                     # Attempt to fetch historical
                     ts_ms = self.market_data["start_ts"] * 1000
                     h_url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={ts_ms}&limit=1"
                     h_r = await asyncio.to_thread(self.session.get, h_url, timeout=2)
                     h_d = h_r.json()
                     if h_d and len(h_d) > 0:
                         self.market_data["open_price"] = float(h_d[0][1]) + self.btc_offset
                         # self.log(f"OPEN PRICE CACHED: {self.market_data['open_price']:.2f}")
                     elif (time.time() - self.market_data["start_ts"]) < 60:
                         self.market_data["open_price"] = self.market_data["btc_price"]
                         # self.log(f"OPEN PRICE SET (LIVE): {self.market_data['open_price']:.2f}")
        except Exception: pass

    def safe_load(self, val, default):
        if isinstance(val, (list, dict)): return val
        try: return json.loads(val)
        except: return default

    async def fetch_market_data(self):
        # Metadata (Slug -> IDs)
        if not self.market_data["up_id"] and self.market_url:
            try:
                slug = self.market_url.split("/")[-1].split("?")[0]
                url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
                resp = await asyncio.to_thread(self.session.get, url, timeout=2.0)
                if resp.status_code == 200:
                    data = resp.json()
                    # self.log(f"DEBUG: Market Data Rx for {slug}") 
                    if "clobTokenIds" in data:
                        ids = self.safe_load(data["clobTokenIds"], [])
                        outcomes = self.safe_load(data.get("outcomes", "[]"), [])
                        
                        # Robust Mapping
                        if len(ids) >= 2 and len(outcomes) >= 2:
                             # self.log(f"DEBUG: IDs Found: {ids}") 
                             up_idx, down_idx = 0, 1
                             for i, name in enumerate(outcomes):
                                 if "Up" in name or "Yes" in name: up_idx = i
                                 elif "Down" in name or "No" in name: down_idx = i
                             
                             self.market_data["up_id"] = ids[up_idx]
                             self.market_data["down_id"] = ids[down_idx]
            except Exception as e:
                self.log(f"Metadata Error: {e}")

        # Prices (Poly)
        if self.market_data["up_id"]:
            try:
                clob_url = "https://clob.polymarket.com/price"
                p1 = await asyncio.to_thread(self.session.get, clob_url, params={"token_id": self.market_data["up_id"], "side": "buy"}, timeout=1)
                p2 = await asyncio.to_thread(self.session.get, clob_url, params={"token_id": self.market_data["down_id"], "side": "buy"}, timeout=1)
                
                r1 = p1.json()
                if "price" in r1: self.market_data["up_price"] = float(r1["price"])
                r2 = p2.json()
                if "price" in r2: self.market_data["down_price"] = float(r2["price"])
            except: pass

    # --- Trading Actions ---
    async def execute_trade(self, side, token_id, amount):
        if not self.client: return False
        
        self.ui_state = "EXECUTING"
        self.log(f"EXECUTING {side} BUY (${amount})...")
        
        try:
             # Logic from live_trade_cli
             price = self.market_data["up_price"] if side == "UP" else self.market_data["down_price"]
             if price <= 0: price = 0.50
             
             shares = round(float(amount) / price, 2)
             
             # Create Order
             order = OrderArgs(
                 price=0.99, # Market Buy effectively
                 size=shares,
                 side="BUY",
                 token_id=token_id
             )
             
             resp = await asyncio.to_thread(lambda: self.client.post_order(self.client.create_order(order)))
             
             if resp and (resp.get("success") or resp.get("orderID")):
                 oid = resp.get("orderID") or "UNKNOWN"
                 self.active_trade = {
                     "side": side,
                     "shares": shares,
                     "cost": amount,
                     "order_id": oid
                 }
                 self.log(f"SUCCESS: Order {oid} Placed!")
                 return True
             else:
                 err = resp.get("errorMsg") if resp else "Unknown"
                 self.log(f"FAILURE: {err}")
                 return False
                 
        except Exception as e:
            self.log(f"EXCEPTION: {e}")
            return False
        finally:
            self.ui_state = "SCANNING"

    # --- Input Handling ---
    def process_input(self):
        if msvcrt.kbhit():
            key = msvcrt.getch()
            try: key_char = key.decode().lower()
            except: return
            
            if key_char == 'q':
                self.is_running = False
            elif key_char == 'r':
                os.system('cls') # Force clear
                
            if self.ui_state == "CONFIRM_BUY":
                if key_char == 'y':
                    # Signal Async Execute
                    asyncio.create_task(self.execute_trade(self.confirm_side, self.confirm_token, self.trade_size))
                    self.ui_state = "EXECUTING" # Transient
                elif key_char == 'n':
                    self.log("Trade Cancelled by User.")
                    self.ui_state = "SCANNING"
                    self.strategy_triggered = True # Skip rest of window

    # --- UI Drawing ---
    def get_terminal_size(self):
        try: return os.get_terminal_size()
        except: return os.terminal_size((80, 24))

    def draw_ui(self):
        cols, lines = self.get_terminal_size()
        buf = [HOME]
        
        def _add(line):
            clean_line = line[:cols-1] 
            buf.append(CSI+"K" + clean_line + "\n")

        # Data Prep
        btc = self.market_data["btc_price"]
        op = self.market_data["open_price"]
        up_p = self.market_data["up_price"]
        dn_p = self.market_data["down_price"]
        
        drift = 0.0
        if op > 0: drift = abs(btc - op) / op
        
        # --- HEADER ---
        _add(f" {BOLD}POLYMARKET LIVE TRADER{RESET} ".center(cols + 10))
        
        # --- TIME BAR ---
        now_dt = datetime.now(timezone.utc)
        t_str = f"{COLOR_GRAY}{now_dt.strftime('%H:%M:%S')} UTC  |  {(now_dt + OFFSET_ET).strftime('%H:%M:%S')} ET{RESET}"
        _add(t_str.center(cols + 20))
        
        buf.append("\n")

        # --- TIMELINE (Restored) ---
        total_sec = 15 * 60
        elapsed_sec = 0
        if self.market_data["start_ts"] > 0:
            elapsed_sec = time.time() - self.market_data["start_ts"]
        elapsed_mins = elapsed_sec / 60.0
        
        # Explicit Checkpoints: [Start] -- [T+3 Calib] -- [T+6 Skip] -- [T+9 TRADE] -- [End]
        def _mark(m_min, lbl, active_window=0.2):
            is_past = elapsed_mins > m_min + active_window
            is_now = m_min - active_window <= elapsed_mins <= m_min + active_window
            
            sym = "○"
            col = COLOR_GRAY
            
            if is_now: 
                sym = "◉"
                col = COLOR_UI
            elif is_past:
                sym = "●"
                col = COLOR_SUCCESS
            
            return f"{col}{lbl} {sym}{RESET}"

        line = f"{COLOR_GRAY}─{RESET}" * 3
        # Explicitly named checkpoints as requested
        tl = f"{_mark(0,'Start')} {line} {_mark(3,'3m:Calib')} {line} {_mark(6,'6m:Skip')} {line} {_mark(9,'9m:TRADE')} {line} {_mark(15,'End')}"
        _add(tl.center(cols + 60)) 

        buf.append("\n")

        # --- SIGNAL STRENGTH ---
        target = 0.0004
        pct = min(drift / target, 1.25)
        bar_len = 40
        fill = int(pct * bar_len)
        fill = min(fill, bar_len)
        
        bar_char = "█"
        empty_char = "░"
        col = COLOR_GRAY
        if pct > 0.5: col = COLOR_UI
        if pct >= 1.0: col = COLOR_PRICE_UP
        
        bar_viz = f"{col}{bar_char * fill}{COLOR_GRAY}{empty_char * (bar_len - fill)}{RESET}"
        
        sig_txt = "WAITING FOR T+9..."
        if elapsed_mins > 8.8 and elapsed_mins < 9.2:
             if pct >= 1.0: sig_txt = f"{COLOR_PRICE_UP}>>> SIGNAL ACTIVE (T+9) <<<{RESET}"
             else: sig_txt = f"{COLOR_WARN}>>> WATCHING T+9 <<<{RESET}"
        elif elapsed_mins < 8.8:
             sig_txt = f"{COLOR_GRAY}Waiting for T+9 Window...{RESET}"
        
        _add(f"Signal: {pct*100:.0f}%".center(cols))
        _add(bar_viz.center(cols + 20))
        _add(sig_txt.center(cols + 10))
        
        buf.append("\n")

        # --- PRICES ---
        gray = COLOR_GRAY
        wht = CSI + '1;37m'
        up_s = f"{COLOR_PRICE_UP}UP  {wht}{up_p:.2f}{RESET}"
        dn_s = f"{wht}{dn_p:.2f}  {COLOR_PRICE_DN}DOWN{RESET}"
        _add(f"{up_s}      {gray}|{RESET}      {dn_s}".center(cols + 40))
        buf.append("\n")

        # --- STATUS ---
        status_col = COLOR_UI
        if self.ui_state == "CONFIRM_BUY": status_col = COLOR_WARN
        
        if self.ui_state == "CONFIRM_BUY":
             _add(f"{COLOR_WARN}!!! CONFIRM TRADE: {self.confirm_side} @ {self.confirm_price:.2f} !!!{RESET}".center(cols + 10))
             _add("[Y] Confirm   [N] Cancel".center(cols))
        elif self.active_trade:
             _add(f"{COLOR_SUCCESS}✔ POSITION ACTIVE: {self.active_trade['side']}{RESET}".center(cols + 10))
        else:
             _add(f"{COLOR_GRAY}Status: {status_col}{self.ui_state}{RESET}".center(cols + 10))

        # --- LOGS (Filtered) ---
        buf.append("\n") 
        _add(f"{COLOR_GRAY}" + "─" * cols + f"{RESET}")
        
        # Filter out technical logs for display
        visible_logs = [l for l in self.log_buffer if "Client Connected" not in l and "Starting GUI" not in l]
        for l in visible_logs:
            _add(f"{COLOR_GRAY}{l}{RESET}")
            
        # --- FOOTER ---
        _add(f"{COLOR_GRAY}[Q] Quit  [R] Refresh{RESET}".center(cols + 10))

        sys.stdout.write("".join(buf))
        sys.stdout.flush()

    # --- Main Loop ---
    async def run(self):
        os.system('cls')
        sys.stdout.write(HIDE_CURSOR)
        self.log("Starting GUI Trader...")
        
        # Initial Calib
        await self.fetch_spot_price()
        
        last_fetch = 0
        fetch_interval = 2.0 # Fast updates for UI
        
        while self.is_running:
            now_ts = time.time()
            
            # 1. Window Calc
            now_dt = datetime.now(timezone.utc)
            minutes = now_dt.minute
            floor = (minutes // 15) * 15
            start_dt = now_dt.replace(minute=floor, second=0, microsecond=0)
            ts_start = int(start_dt.timestamp())
            url = f"https://polymarket.com/event/btc-updown-15m-{ts_start}"
            
            # New Window Reset
            if url != self.market_url:
                if self.market_url: self.log("New Market Window")
                self.market_url = url
                self.market_data["up_id"] = None # Reset IDs to force refetch
                self.market_data["open_price"] = 0.0 # Reset Open
                self.market_data["start_ts"] = ts_start
                self.active_trade = None
                self.strategy_triggered = False
                self.seen_t3 = False
                self.ui_state = "SCANNING"

            # 2. Data Fetch
            if now_ts - last_fetch > fetch_interval:
                await self.fetch_spot_price()
                await self.fetch_market_data()
                last_fetch = now_ts
                
            # 3. Strategy Logic (Only if SCANNING)
            if self.ui_state == "SCANNING" and not self.active_trade and not self.strategy_triggered:
                elapsed_mins = (now_ts - ts_start) / 60.0
                
                # Checkpoints
                if 2.8 <= elapsed_mins <= 3.2: self.seen_t3 = True
                
                # T+6 Window (SKIP / MONITOR ONLY)
                check_t6 = 5.9 <= elapsed_mins <= 6.1
                if check_t6:
                     # Just log or show status, do not trigger trade
                     pass

                # T+9 Window (THE ACTIVE WINDOW)
                check_t9 = 8.9 <= elapsed_mins <= 9.1
                
                if check_t9:
                    if not self.seen_t3:
                        pass # Missed sampling
                    else:
                        # Drift Check
                        op = self.market_data["open_price"]
                        btc = self.market_data["btc_price"]
                        
                        drift_pct = 0.0
                        if op > 0: drift_pct = abs(btc - op) / op
                        
                        if drift_pct > 0.0004:
                            side = "UP" if btc > op else "DOWN"
                            price = self.market_data["up_price"] if side=="UP" else self.market_data["down_price"]
                            tid = self.market_data["up_id"] if side=="UP" else self.market_data["down_id"]
                            
                            if tid and price > 0.40: # Safety
                                # TRIGGER CONFIRMATION
                                self.confirm_side = side
                                self.confirm_price = price
                                self.confirm_token = tid
                                self.ui_state = "CONFIRM_BUY"
                                # Bell
                                print('\a')
                            else:
                                if price <= 0.40 and price > 0:
                                     self.log(f"Signal ignored: Price {price} too low")
                                     self.strategy_triggered = True
                
                # Close Strategy after T+9.5
                if elapsed_mins > 9.5 and not self.strategy_triggered:
                    pass

            # 4. Input & Draw
            self.process_input()
            self.draw_ui()
            
            await asyncio.sleep(0.05) # 20 FPS

        # Cleanup
        sys.stdout.write(SHOW_CURSOR + RESET + "\n")
        print("Exited.")

if __name__ == "__main__":
    try:
        app = LiveTraderGUI()
        asyncio.run(app.run())
    except KeyboardInterrupt:
        sys.stdout.write(SHOW_CURSOR + RESET + "\n")
