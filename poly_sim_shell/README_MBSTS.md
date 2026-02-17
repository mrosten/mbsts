# MBSTS Simulator & Live Bot (Multi-Strategy Bitcoin Trading System)

This application is a sophisticated Textual User Interface (TUI) for simulating and live-trading **Bitcoin 5-Minute Up/Down Options** on Polymarket. It aggregates data from Chainlink (On-Chain Price), Binance (Volatility/Candles), and Polymarket (Orderbook) to generate trading signals based on five distinct algorithms.

## 🚀 Features

*   **Hybrid Execution:** Run purely in **Simulation Mode** (paper trading) or switch to **Live Mode** (real USDC simulated via Proxy/Mainnet) instantly.
*   **Risk Management Bankroll:** Define a strict "Session Risk" amount. The bot will stop trading if this amount is depleted or add to it as you profit.
*   **Visual Dashboard:** Real-time TUI displaying BTC price, "Odds" score, Trend probability, and status of all 5 algorithms.
*   **Automated Trading Checks:**
    *   **Strict Price Filter:** No trade is taken unless Bitcoin has moved at least **$25** from the Open Price in the direction of the bet (e.g., must be >= +$25 for UP, <= -$25 for DOWN).
    *   **Price Filter:** Only enters trades between **20¢ and 95¢**.
    *   **1 Trade Max:** Option to restrict the bot to a single high-conviction trade per 5-minute window.
    *   **Last Second Exit:** Automatically attempts to sell positions before the window closes (at 4:45 elapsed) to capture spreads or salvage value.

## 🛠 Setup & Configuration

### Prerequisites
*   Python 3.10+
*   `pip install -r requirements.txt` (Dependencies: `textual`, `web3`, `requests`, `python-dotenv`, `py-clob-client`, `eth-account`)

### Environment Variables (`.env`)
Create a `.env` file in the same directory for Live Trading:

```ini
# Polygon RPC (Optional, defaults to public public nodes)
POLYGON_RPC_URL=https://polygon-rpc.com

# Live Trading Credentials (REQUIRED for Live Mode)
PRIVATE_KEY=your_private_key_here
PROXY_ADDRESS=your_proxy_address_here_if_using_polymarket_proxy
```

### Running the Bot
```powershell
python mbsts_sim_and_live.py
```

## 🧠 Algorithms (Scanners)

The bot uses 5 distinct logic modules ("Scanners") to analyze the market every 2 seconds.

### 1. 🏹 Slingshot (`Sling`)
*   **Logic:** Reversal/Bounce Detector.
*   **Trigger UP (Reclaim):** Price crosses **ABOVE** the 20-period Moving Average (1m candles) after being below it for the previous 2 candles.
*   **Trigger DOWN (Break):** Price crosses **BELOW** the 20-period MA after being above it for 2 candles.
*   **Invalidation:** Instant if price crosses back over the MA.

### 2. 📊 PolyOdds (`Poly`)
*   **Logic:** Orderbook & Trend Confirmation.
*   **Trigger UP:**
    *   Polymarket "Yes" price >= 55¢
    *   Polymarket "No" price <= 45¢
    *   Statistical Trend Probability >= 50%
    *   Current Price > Open Price
*   **Trigger DOWN:**
    *   Polymarket "No" price >= 55¢
    *   "Yes" price <= 45¢
    *   Trend Probability < 50%
    *   Current Price < Open Price

### 3. 🐍 Cobra (`Cobra`)
*   **Logic:** Volatility Breakout (Bollinger-style).
*   **Data:** 1-minute candles over the last 90 minutes.
*   **Trigger UP (Explosive):** Price breaks **ABOVE** SMA(20) + 2 Standard Deviations.
*   **Trigger DOWN (Explosive):** Price breaks **BELOW** SMA(20) - 2 Standard Deviations.
*   **Wait:** Logic pauses if 5 minutes have elapsed (data stale).

### 4. 🚩 BullFlag (`Flag`)
*   **Logic:** Pattern Recognition (Staircase).
*   **Trigger UP:**
    *   Identifies at least **3 duplicate "Higher Lows"** in the last 15 minutes.
    *   Current Price must be near the "High" of the window (>= 99.95%).
*   **Trigger DOWN:** Not implemented (Long-only strategy currently).

### 5. 🎲 TrendOdds (`TO`)
*   **Logic:** Confluence of Statistical Trend and "Odds Score".
*   **Trigger UP:**
    *   Price > Open AND (Odds Score >= 3 OR (Trend > 55% AND Odds >= 2)).
*   **Trigger DOWN:**
    *   Price < Open AND (Odds Score >= 3 OR (Trend < 45% AND Odds >= 2)).

## 🧮 Master Signal & Odds

### Odds Score (The "Strict Filter")
The **Odds Score (1-5)** is the most critical metric. It measures how far the price has moved relative to the asset's recent volatility.
*   `Diff` = Abs(Current Price - Open Price)
*   `Range` = Average High-Low range of 1m candles over the last hour.
*   `Ratio` = Diff / Range

| Score | Ratio Requirement | Meaning |
| :--- | :--- | :--- |
| **5/5** | >= 2.0x Range | **Extreme Move.** Very high probability of holding direction. |
| **4/5** | >= 1.5x Range | **Strong Move.** |
| **3/5** | >= 1.0x Range | **Solid Move.** Moves > 1x Average Range rarely reverse fully. |
| **2/5** | >= 0.5x Range | **Weak/Chop.** Required minimum for ANY trade. |
| **1/5** | < 0.5x Range | **Noise.** Trading is forbidden. |

### Master Signal
A composite score (-3 to +3) derived from the active scanners to color-code the UI.
*   **Cobra:** +/- 2 points (High Weight)
*   **Slingshot:** +/- 1 point
*   **Poly:** +/- 1 point
*   **Flag:** +/- 1 point

*   **> +3:** STRONG BUY UP (Green Border)
*   **< -3:** STRONG BUY DOWN (Red Border)

## 🖥 Controls

*   **Manual Bet $:** Set the wager size for manual clicks.
*   **Starting Risk Bankroll:** Set a "Stop Loss" cap. If you start with $50 here, the bot will use this as its trading balance. Wins add to it, losses subtract. If it hits $0, trading stops.
*   **Checkboxes:**
    *   **Algo Names (Sling, Poly, etc.):** Toggle specific algorithms on/off.
    *   **Strong Only:** Only trade if Master Score is "STRONG" or Odds >= 3.
    *   **1 Trade Max:** **(Recommended)** Stop trading for the 5m window after ONE successful entry.
    *   **ENABLE LIVE TRADING:** The "Safety Switch". Must be checked to send real orders. Defaults to OFF.

## ⚠️ Disclaimer
This software is for educational purposes. Cryptocurrency trading involves significant risk. The "Live Mode" interacts with real financial contracts. Use at your own risk.
