import streamlit as st
import os
import time
import requests
import json
import asyncio
from dotenv import load_dotenv
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
import market_analysis

# Page Config
st.set_page_config(page_title="Polymarket Turbo Trader", layout="wide")

# Load Env
load_dotenv()
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
HOST = "https://clob.polymarket.com"
CHAIN_ID = 137
GAMMA_API_BASE = "https://gamma-api.polymarket.com"

# --- HELPERS ---
@st.cache_resource
def get_client():
    if not PRIVATE_KEY: return None
    funder = PROXY_ADDRESS if PROXY_ADDRESS else Account.from_key(PRIVATE_KEY).address
    try:
        client = ClobClient(host=HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID, signature_type=1, funder=funder)
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        return client
    except Exception as e:
        st.error(f"Client Init Error: {e}")
        return None

def get_market_data(url):
    try:
        slug = url.strip("/").split("?")[0].split("/")[-1]
        api_url = f"{GAMMA_API_BASE}/markets/slug/{slug}"
        resp = requests.get(api_url, timeout=2)
        if resp.status_code == 200:
            return resp.json(), slug
    except:
        pass
    return None, None

def get_outcome_indices(outcomes_list):
    # Returns (up_idx, down_idx)
    # Tries to find "Up", "Yes", "Higher" -> 0
    # "Down", "No", "Lower" -> 1
    # Defaults to 0, 1 if unsure
    
    up_idx = 0
    down_idx = 1
    
    # Normalize
    norm = [str(o).lower() for o in outcomes_list]
    
    # Find UP
    for i, name in enumerate(norm):
        if name in ["up", "yes", "higher", "above"]:
            up_idx = i
            break
            
    # Find DOWN
    for i, name in enumerate(norm):
        if name in ["down", "no", "lower", "below"]:
            down_idx = i
            break
            
    return up_idx, down_idx

def place_trade(client, market_data, outcome, shares):
    try:
        # Dynamic Index
        token_ids = json.loads(market_data.get("clobTokenIds", "[]"))
        outcomes = json.loads(market_data.get("outcomes", "[]"))
        
        up_i, down_i = get_outcome_indices(outcomes)
        outcome_idx = up_i if outcome.lower() == "up" else down_i
        
        target_token = token_ids[outcome_idx]
        
        # Market buy -> limit 0.99
        buy_args = OrderArgs(price=0.99, size=shares, token_id=target_token, side="BUY")
        resp = client.create_order(buy_args)
        return client.post_order(resp), target_token
    except Exception as e:
        return {"success": False, "error": str(e)}, None

def place_sell(client, token_id, shares):
    try:
        sell_args = OrderArgs(price=0.01, size=shares, token_id=token_id, side="SELL")
        resp = client.create_order(sell_args)
        return client.post_order(resp)
    except Exception as e:
        return {"success": False, "error": str(e)}

# --- UI ---
# --- UI ---
# Remove duplicate title here

import threading

# --- BACKGROUND PRICE MONITOR ---
class PriceMonitor:
    def __init__(self):
        self.prices = {"up": 0.0, "down": 0.0}
        self.running = False
        self.thread = None
        self.url = None

    def start(self, url):
        self.url = url
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._worker, daemon=True)
            self.thread.start()
    
    def _worker(self):
        while self.running:
            if self.url:
                try:
                    data, _ = get_market_data(self.url)
                    if data:
                        ps = json.loads(data.get("outcomePrices", "[]"))
                        outs = json.loads(data.get("outcomes", "[]"))
                        
                        if len(ps) >= 2 and len(outs) >= 2:
                            up_i, down_i = get_outcome_indices(outs)
                            
                            self.prices["up"] = float(ps[up_i])
                            self.prices["down"] = float(ps[down_i])
                            self.prices["up_label"] = outs[up_i]
                            self.prices["down_label"] = outs[down_i]
                except Exception as e:
                    print(f"Monitor Error: {e}")
            time.sleep(0.5) # Background refresh rate

@st.cache_resource
def get_monitor():
    return PriceMonitor()

# --- UI START ---
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #FAFAFA; }
    .metric-card {
        background-color: #262730;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #464b5d;
        text-align: center;
    }
    h1 { color: #00e5ff; }
</style>
""", unsafe_allow_html=True)

st.title("🚀 Polymarket Turbo Trader")

# 1. URL Input
with st.container(border=True):
    url = st.text_input("Polymarket Event URL", placeholder="https://polymarket.com/event/...")

if url:
    monitor = get_monitor()
    monitor.start(url)
    
    client = get_client()
    if not client:
        st.error("Could not initialize CLOB Client. Check .env")
        st.stop()
    
    # Initial Slug Fetch
    slug = url.strip("/").split("?")[0].split("/")[-1]
    st.subheader(f"Strategy for: {slug}")
    
    # CONTAINER FOR DASHBOARD
    dashboard_container = st.container(border=True)

    analysis_container = st.expander("📊 Market Analysis & Technical Indicators", expanded=True)
    with analysis_container:
        if st.button("🔄 Refresh Analysis"):
            with st.spinner("Analyzing Market..."):
                results = market_analysis.analyze_market_data(url)
                if "error" in results:
                    st.error(results["error"])
                else:
                    # Recommendation Banner
                    rec = results.get('recommendation', 'N/A')
                    rec_color = "red"
                    if "BETTING UP" in rec: rec_color = "green"
                    elif "BETTING DOWN" in rec: rec_color = "red"
                    else: rec_color = "orange"
                    
                    st.markdown(f"""
                    <div style="background-color: #1e1e1e; padding: 15px; border-radius: 8px; border-left: 5px solid {rec_color}; margin-bottom: 20px;">
                        <h3 style="margin:0; color: {rec_color};">{rec}</h3>
                        <p style="margin:0; opacity: 0.8;">Strike: ${results.get('strike_price', 0):,.2f} | Current: ${results.get('current_price', 0):,.2f}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                    # Metrics Row 1
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Strike Price", f"${results.get('strike_price', 0):,.2f}", delta=f"{results.get('diff', 0):.2f}", delta_color="normal")
                    c2.metric("RSI (14)", f"{results.get('rsi', 0):.1f}", list(results.get('rsi_status','').split(' '))[-1]) # Hacky parsing for emoji or status
                    c3.metric("Trend", results.get('trend', 'N/A'))
                    
                    # Metrics Row 2
                    c4, c5, c6 = st.columns(3)
                    c4.metric("Bollinger Status", results.get("bb_status", "N/A"))
                    c5.metric("SMA 50 Status", results.get("sma_status", "N/A"))
                    c6.metric("Volatility", results.get("vol_status", "N/A"))
                
                    st.info(f"**Recommendation:** {results.get('recommendation', 'N/A')}")
                    if 'reasoning' in results:
                        st.caption(f"**Analysis:** {results['reasoning']}")
                    
                    # Detailed Text
                    if "bb_lower" in results:
                        st.caption(f"BB Range: ${results['bb_lower']:,.0f} - ${results['bb_upper']:,.0f}")
                        st.caption(f"ATR (14): ${results.get('atr', 0):.2f} | BandWidth: {results.get('bandwidth', 0):.2f}%")

    # 4. Trading Panel (Static)
    trade_container = st.container(border=True)
    with trade_container:
        st.write("### ⚡ Instant Trade")
        amount_col, btn_col1, btn_col2 = st.columns([1, 1, 1])
        with amount_col:
            shares = st.number_input("Shares to Buy", min_value=1.0, value=5.0, step=1.0)
    
    # Place Order Handler Logic (outside container UI flow, but state managed)
    if "active_position" not in st.session_state:
        st.session_state.active_position = None

    with btn_col1:
        if st.button(f"BUY UP", type="primary", use_container_width=True):
             # Use monitor price for estimation, but execution uses API in place_trade?
             # Actually, place_trade needs market_data which contains token IDs.
             # We can fetch that just-in-time or cache it.
             # For speed, let's fetch it JIT since it's a one-time click.
             data, _ = get_market_data(url)
             if data:
                with st.spinner("Buying..."):
                    res, token = place_trade(client, data, "up", shares)
                    if res.get("success"):
                        p_up = monitor.prices["up"]
                        st.success(f" Bought UP! ID: {res.get('orderID')}")
                        st.session_state.active_position = {
                            "type": "up", "size": shares, "entry": p_up, 
                            "sl": max(0.01, p_up - 0.05), "token": token, "status": "watching"
                        }
                    else:
                        st.error(f"Failed: {res}")

    with btn_col2:
        if st.button(f"BUY DOWN", type="primary", use_container_width=True):
             data, _ = get_market_data(url)
             if data:
                with st.spinner("Buying..."):
                    res, token = place_trade(client, data, "down", shares)
                    if res.get("success"):
                        p_down = monitor.prices["down"]
                        st.success(f"Bought DOWN! ID: {res.get('orderID')}")
                        st.session_state.active_position = {
                            "type": "down", "size": shares, "entry": p_down, 
                            "sl": max(0.01, p_down - 0.05), "token": token, "status": "watching"
                        }
                    else:
                        st.error(f"Failed: {res}")

    # --- FRAGMENT FOR LIVE UPDATES ---
    @st.fragment(run_every=0.1) # UI updates very fast (reading from memory)
    def update_dashboard():
        # Read from Monitor (Instant)
        p_up = monitor.prices["up"]
        p_down = monitor.prices["down"]
        
        # Display Prices
        c1, c2 = st.columns(2)
        c1.metric(f"UP Price ({monitor.prices.get('up_label', 'Up')})", f"${p_up:.3f}")
        c2.metric(f"DOWN Price ({monitor.prices.get('down_label', 'Down')})", f"${p_down:.3f}")
        
        # Monitor Active Position
        if st.session_state.active_position and st.session_state.active_position["status"] == "watching":
            pos = st.session_state.active_position
            st.warning(f"🛡️ STOP LOSS ACTIVE | {pos['type'].upper()} | Trigger: < ${pos['sl']:.3f}")
            
            curr_price = p_up if pos["type"] == "up" else p_down
            
            # TRIGGER Check
            if curr_price > 0 and curr_price <= pos["sl"]:
                st.error(f"🚨 STOP LOSS TRIGGERED (${curr_price} <= {pos['sl']})! SELLING...")
                res = place_sell(client, pos["token"], pos["size"])
                if res.get("success"):
                    st.toast("✅ Auto-Sold Successfully!", icon="🛡️")
                    st.session_state.active_position["status"] = "sold"
                    st.rerun() # Force full reload to update state
                else:
                    st.error(f"Sell Failed: {res}")

    with dashboard_container:
        update_dashboard()
