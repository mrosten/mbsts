import time
import asyncio
import requests
from datetime import datetime
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Label
from textual.containers import Container, Vertical, Horizontal
from textual import work
from web3 import Web3
from mbsts_v4.config import POLYGON_RPC_LIST, CHAINLINK_BTC_FEED, CHAINLINK_ABI

class PriceCheckerApp(App):
    """A fast BTC price checker comparing Chainlink and Multiple Exchanges."""
    
    CSS = """
    Screen {
        align: center middle;
        background: #111111;
    }
    #main_container {
        width: 70;
        height: 35;
        border: thick cyan;
        background: #1a1a1a;
        padding: 1;
    }
    .price_row {
        height: 3;
        margin: 1 0;
        padding: 0 2;
        background: #222222;
        content-align: left middle;
    }
    .label {
        width: 25%;
        text-style: bold;
        color: #888888;
    }
    .value {
        width: 45%;
        text-align: right;
        color: white;
        text-style: bold;
    }
    .diff {
        width: 30%;
        text-align: right;
        color: #aaaaaa;
        text-style: italic;
    }
    #cl_val { color: #00ff00; }
    #bi_val { color: #ffff00; }
    #cb_val { color: #0000ff; }
    #kr_val { color: #ff00ff; }
    #by_val { color: #00ffff; }
    
    #status {
        text-align: center;
        margin-top: 1;
        color: #666666;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main_container"):
            # Chainlink (Reference)
            with Horizontal(classes="price_row"):
                yield Label("CHAINLINK:", classes="label")
                yield Label("CONNECTING...", id="cl_val", classes="value")
                yield Label("", classes="diff") # No diff for reference
            
            # Exchanges
            with Horizontal(classes="price_row"):
                yield Label("BINANCE:", classes="label")
                yield Label("FETCHING...", id="bi_val", classes="value")
                yield Label("", id="bi_diff", classes="diff")

            with Horizontal(classes="price_row"):
                yield Label("COINBASE:", classes="label")
                yield Label("FETCHING...", id="cb_val", classes="value")
                yield Label("", id="cb_diff", classes="diff")

            with Horizontal(classes="price_row"):
                yield Label("KRAKEN:", classes="label")
                yield Label("FETCHING...", id="kr_val", classes="value")
                yield Label("", id="kr_diff", classes="diff")

            with Horizontal(classes="price_row"):
                yield Label("BYBIT:", classes="label")
                yield Label("FETCHING...", id="by_val", classes="value")
                yield Label("", id="by_diff", classes="diff")
            
            yield Static("Ready", id="status")
        yield Footer()

    def on_mount(self):
        self.prices = {
            "cl": 0.0, "bi": 0.0, "cb": 0.0, "kr": 0.0, "by": 0.0
        }
        self.w3 = None
        self.contract = None
        self.title = "Multi-Exchange Oracle Monitor"
        
        # Start the loops
        self.init_web3()
        self.set_interval(0.5, self.update_chainlink)
        self.set_interval(0.5, self.update_binance)
        self.set_interval(1.0, self.update_coinbase)
        self.set_interval(1.0, self.update_kraken)
        self.set_interval(0.5, self.update_bybit)
        self.set_interval(0.5, self.calculate_drifts)

    @work(exclusive=True, thread=True)
    def init_web3(self):
        for rpc in POLYGON_RPC_LIST:
            try:
                w3 = Web3(Web3.HTTPProvider(rpc))
                if w3.is_connected():
                    self.w3 = w3
                    self.contract = self.w3.eth.contract(
                        address=Web3.to_checksum_address(CHAINLINK_BTC_FEED), 
                        abi=CHAINLINK_ABI
                    )
                    self.query_one("#status").update(f"Connected to {rpc}")
                    return
            except:
                continue
        self.query_one("#status").update("All RPCs failed!")

    def update_chainlink(self):
        if self.contract:
            try:
                # LatestAnswer usually updates every 5-10 mins or on 0.5% move
                raw = self.contract.functions.latestAnswer().call()
                self.prices["cl"] = float(raw) / 10**8
                self.query_one("#cl_val").update(f"${self.prices['cl']:,.2f}")
            except: pass

    def update_binance(self):
        try:
            r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=1).json()
            p = float(r['price'])
            self.prices["bi"] = p
            self.query_one("#bi_val").update(f"${p:,.2f}")
        except: pass

    def update_coinbase(self):
        try:
            r = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=1).json()
            p = float(r['data']['amount'])
            self.prices["cb"] = p
            self.query_one("#cb_val").update(f"${p:,.2f}")
        except: pass

    def update_kraken(self):
        try:
            r = requests.get("https://api.kraken.com/0/public/Ticker?pair=XBTUSD", timeout=1).json()
            p = float(r['result']['XXBTZUSD']['c'][0])
            self.prices["kr"] = p
            self.query_one("#kr_val").update(f"${p:,.2f}")
        except: pass

    def update_bybit(self):
        try:
            r = requests.get("https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT", timeout=1).json()
            p = float(r['result']['list'][0]['lastPrice'])
            self.prices["by"] = p
            self.query_one("#by_val").update(f"${p:,.2f}")
        except: pass

    def calculate_drifts(self):
        ref = self.prices["cl"]
        if ref <= 0: return # No reference yet

        for ex in ["bi", "cb", "kr", "by"]:
            val = self.prices[ex]
            if val > 0:
                diff = val - ref
                pct = (diff / ref) * 100
                color = "[green]" if abs(pct) < 0.05 else ("[yellow]" if abs(pct) < 0.1 else "[red]")
                self.query_one(f"#{ex}_diff").update(f"{color}{'+' if diff >= 0 else ''}${diff:.2f} ({pct:+.2f}%)")

if __name__ == "__main__":
    app = PriceCheckerApp()
    app.run()
