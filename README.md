# 🚀 Polymarket Turbo Trader v2 (NiceGUI Edition)

## Overview
**Polymarket Turbo Trader v2** is a professional-grade, low-latency trading terminal designed for high-frequency trading and algorithmic position management on Polymarket (Polygon Network).

Unlike standard web interfaces, this tool connects directly to the **CLOB (Central Limit Order Book)** API for millisecond-latency execution and real-time pricing, bypassing standard caching layers. It is built with **NiceGUI** (Vue.js + FastAPI) for a reactive, modern, and dark-themed user interface.

---

## 🌟 Key Features

### 0. 💸 NEW: Real Money Live Trading Shell
**Located in `/poly_sim_shell`** - A dedicated suite of terminal bots for T+9 Drift Strategies.
*   **Standard Bot**: Configurable, safer trading.
*   **Dynamic Bot**: Sizing scales with momentum.
*   **GUI Bot**: Beautiful terminal monitoring.
*   **Linux Runner**: Auto-installing start script.
*   See `poly_sim_shell/README.md` for full instructions.

### 1. ⚡ Zero-Latency Trading Engine
*   **Direct CLOB Access:** Bypasses Gamma API cache; fetches bids/asks directly from the matching engine.
*   **Rapid Execution:** Single-click "EXECUTE TRADE" buttons fire Limit Orders (IOC) instantly.
*   **Background Heartbeat:** A robust `asyncio` loop fetches data in the background (every ~1s), ensuring the UI never freezes.
*   **Echo Badge:** The UI dynamically confirms which side (UP/DOWN) you are targeting.

### 2. 🛡️ Advanced Stop Loss Manager
Located immediately below the Quick Trade panel, this specific module protects your active positions:
*   **Echo Protection:** Automatically tracks your selected trading side (UP/DOWN).
*   **Auto-Update Trigger:** Trigger price automatically follows the market (`Current - Dist`) when inactive, so it's always ready to set.
*   **Trailing Stop:** Toggle "Auto-Trail" to have your trigger price move UP with the market to lock in profits.
*   **Precision Control:** Use the **Spin Box** to set trailing distance in 1-cent increments (e.g., $0.05).
*   **Safety Lock:** "Set Manual SL" is disabled if no valid trade or price is detected.

### 3. 🤖 Auto-Strategies (Algorithmic Trading)
Expand the **"Auto-Strategies"** panel to enable bot logic:
*   **Reversion Master 📉:** Buys dips (RSI < 30) and sells rips (RSI > 70) in range-bound markets.
*   **Trend Surfer 🏄:** Enters positions when SuperTrend momentum flips direction.
*   **Bracket Bot 🛡️:** Automatically posts Take Profit and Stop Loss orders immediately upon trade entry.
*   **T-4 Sniper:** (Experimental) Special logic to trade the final 4-minute volatility window.

### 4. 🧠 Real-Time Market Analysis
*   **Live Metrics:** Updates Price, Strike Price, Time Remaining, RSI, and Volatility every second.
*   **Divergence:** Shows the spread between the implied probability and the logic-derived value.
*   **Convergence Zone:** Visual warnings when the market is entering the final minutes involving high Time Decay (Theta).

---

## 🛠️ Installation & Setup

### Prerequisites
*   Python 3.10+
*   A Polymarket Account (Polygon Wallet) with USDC bridged.

### 1. Clone & Install
```bash
git clone https://github.com/your-repo/turbindo.git
cd turbindo
pip install -r requirements.txt
# Ensure nicegui is installed
pip install nicegui
```

### 2. Configuration (.env)
Create a `.env` file in the root directory (critical for trading):
```env
PRIVATE_KEY=0xYOUR_PRIVATE_KEY_HERE
PROXY_ADDRESS=0xYOUR_PROXY_ADDRESS  # Optional: Standard for Polymarket Proxy Wallets
```

### 3. Run the App
Launch the NiceGUI interface:
```bash
# Windows
run.bat

# Manual
python main.py
```
*App will open at `http://localhost:8085`*

---

## 🖥️ User Guide

### The Dashboard Layout
1.  **Market Analysis:** Top card showing the event URL and calculated signals.
2.  **Quick Trade Panel:**
    *   **Lever:** Toggle **UP** (Green) or **DOWN** (Red).
    *   **Control:** Set Share Size (e.g., 5 shares) and Refresh Rate.
    *   **Execute:** Fires the trade immediately.
3.  **Stop Loss Manager:**
    *   Set a "Trigger Price" manually or use the "Trailing" switch.
    *   Click "Set Manual SL" to arm the protection.
4.  **Auto-Strategies:** Toggle automated bots on/off.

### Troubleshooting
*   **Trade Fails / Silent Failure:**
    *   **Check Minimum Order Value:** Polymarket (CLOB) often rejects orders with a total value < $1.00 USD. Increase your Share Size (e.g., minimum 5-10 shares).
    *   **Check Logs:** Look at the terminal output for `DEBUG` messages regarding `OrderArgs`.
*   **Proxy Error:** Ensure your `PROXY_ADDRESS` in `.env` matches your Polymarket Proxy Wallet, not your EOA (Metamask) address.

---

## ⚠️ Disclaimer
This software is provided for **educational and research purposes only**. Cryptocurrency trading, especially on prediction markets, involves **substantial risk of loss**. The authors are not responsible for any financial losses incurred while using this software. Use at your own risk.
