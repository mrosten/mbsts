# Real Live Trend Linear Bot v2

**Script:** `real_live_trend_linear_v2.py`
**Status:** 🔴 LIVE TRADING (Real Money)

## Overview
This is a **real-money automated trading bot** designed for Polymarket's **Bitcoin 15-Minute** binary markets (Up/Down). It executes a "strong uptrend" following strategy, buying "Yes" shares when specific momentum criteria are met within a defined time window.

### Key Features
*   **Automatic Market Scanning**: Continuously finds the active 15-minute BTC market.
*   **Smart Momentum Detection**: Tracks price checkpoints to identify strong directional moves.
*   **Proxy Wallet Support**: Fully compatible with Polymarket's Proxy Wallets (Magic Link).
*   **Safety First**:
    *   **Kill Switch**: Stops automatically after `N` consecutive losses (default: 3).
    *   **Bankroll Reservation**: Allows you to set aside funds that the bot *cannot* touch.
    *   **Instant Take-Profit**: Immediately places a Limit Sell order at **$0.99** upon any purchase.

## Prerequisites

1.  **Environment Variables (`.env`)**:
    *   `PRIVATE_KEY`: Your Polygon EOA Private Key.
    *   `PROXY_ADDRESS`: Your Polymarket Proxy Wallet Address (Start with `0x...`).
    *   `POLYGON_RPC_URL`: (Optional) Custom RPC for better reliability.

2.  **Dependencies**:
    *   `py-clob-client`
    *   `eth-account`
    *   `requests`
    *   `python-dotenv`

## Strategy Logic

The bot operates on a **15-minute cycle**:

1.  **Scanning Window (T-900s to T-360s)**:
    *   Fetches live BTC price from Binance/Coinbase.
    *   Fetches Polymarket Order Book prices for "Up" and "Down".
    *   Calculates "Drift" (Difference between Start Price and Current Price).

2.  **Signal Generation (T-600s to T-360s)**:
    *   **High Confidence Signal**:
        *   Price must be **Rising** (Current > Prev Checkpoint).
        *   Price range: **$0.88 - $0.95**.
        *   Drift > 0.04%.
    *   **Strong Uptrend Signal**:
        *   Consistent momentum over 3+ checkpoints.
        *   Momentum gain >= $0.10.
        *   Price < $0.85 (Early entry).

3.  **Execution**:
    *   Buys "Up" or "Down" shares based on direction.
    *   Size is calculated based on Bankroll % and Bollinger Band multipliers (if enabled).
    *   **Instant TP**: Immediately posts a GTC Limit Sell limit order at **$0.99** to lock in max profit if the event resolves Yes.

## Usage

Run the script from your terminal:

```bash
python real_live_trend_linear_v2.py
```

### Interactive Startup
The bot will ask you 3 questions upon launch:
1.  **Max Consecutive Losses**: How many losses in a row before stopping? (Default: 3).
2.  **Starting Bankroll**: How much of your balance to risk? (Enter a number or press Enter for ALL).
3.  **Bollinger Band Sizing**: Use volatility-based sizing? (Y/n).

## Output & Logging

*   **Console**: Real-time ticker showing BTC price, Drift, and Trade Status.
*   **Log File**: `REAL_live_v2_log_YYYYMMDD_HHMMSS.txt` (Detailed events).
*   **CSV File**: `REAL_live_v2_detailed_YYYYMMDD_HHMMSS.csv` (Time-series data for analysis).
*   **Loss Tracker**: `loss_tracker.json` (Persists win/loss streak across restarts).

## ⚠️ CRITICAL WARNINGS ⚠️
1.  **Proxy Configuration**: This script assumes `signature_type=1`. If you are using a Gnosis Safe or EOA directly, you may need to modify the code or key derivation logic.
2.  **Real Funds**: This script SPENDS MONEY. Monitor it closely.
3.  **Kill Switch**: Do not disable the kill switch unless you are monitoring the bot 24/7.
