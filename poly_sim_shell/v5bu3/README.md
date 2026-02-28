# Polymarket Sniper V5: System Architecture & Operation Guide

## Overview
Polymarket Sniper V5 is a fully automated, high-frequency execution bot designed to trade short-term directional options (UP/DOWN) on the Polymarket BTC Market.

V5 leverages a custom Textual (TUI) interface mapping to robust background threaded task loops. It evaluates 20 distinct technical algorithms continuously, managing risk dynamically, and executing limit fill-or-kill orders exactly when predetermined price thresholds are met.

## Execution Core (`app.py`)
### 1. Market Synchronization
The system operates on strict **5-minute windows**. At the start of every minute evenly divisible by 5 (e.g., `13:00`, `13:05`), the bot:
- Queries the Kraken REST API for a pinpoint accurate `BTC Open Price`.
- Queries the Binance API for the trailing 60-minute OHLCV candles to compute structural indicators (Moving Averages, RSI, Bollinger Bands).
- Queries the Polymarket CLOB (Central Limit Order Book) via Web3 proxy headers to get live option pricing (bids/asks).

### 2. Algorithm Scanning
Ticks occur every **1.0 second**. During each tick, the core loop (`fetch_market_loop`) feeds the live tick data into the active algorithms (e.g., *Cobra Breakout, Moshe Sniper, N-Pattern*). If a scanner detects its geometric or statistical condition, it returns an explicit `res` (Result) string containing its `BET_UP` or `BET_DOWN` signal.

### 3. Sizing & The Risk Manager
If an algorithm triggers, the execution pipeline passes the signal to `risk_manager.py`. 
- **Base Allocation:** Computes a base bet (default 12%) of your available **Risk Bankroll**.
- **Trend Alignment:** Slashes the bet size in half (50% penalty) if the algorithm is triggering a bet *against* the 4-Hour Macro Trend (e.g., betting DOWN when 4H trend is UP).
- **Scanner Custom Weighting:** Finally, V5 multiplies this base risk calculation by the specific algorithm's user-defined **Weight** configuration (saved in `v5_settings.json`). *e.g., a Weight of 1.67x boosts a $12 base bet to a $20 order.*

### 4. PENDING Orders & Price Bounds (The V5 Upgrade)
Once the trade size is confirmed, the V5 engine checks the live Option Price against your `Min Option Price` and `Max Option Price` input boxes.
- **Immediate Execution:** If the option price is exactly between the bounds (e.g., price is 35¢, bounds are [15¢ - 99¢]), it fires a Market Market order instantly.
- **Pending (Holding):** If the option price is *too cheap* (e.g., currently 12¢, but your Min is 20¢), the trade is **held in a queue**. The algorithm's 3-letter code starts blinking yellow in the UI. 
Every single tick thereafter, V5 checks the pending queue. The very millisecond the option price naturally rises back into the `20¢ - 99¢` bracket, V5 executes the delayed order automatically!

### 5. Automated Loss Recovery Carry-Over
If an algorithm executes a trade, but the 5-minute round settles as a **LOSS**, V5 assumes the geographic structure the algorithm detected is still valid but was slightly early. Under the hood, V5 takes that losing algorithm and pushes it directly into the `Pending Bets` queue for the **NEXT** 5-minute window! It will blink yellow and wait for your minimum price to hit again to execute a recovery trade.

### 6. Last-Second Exits & Settlement
- At exactly **1 second remaining** in the round (second 59), V5 bypasses standard logic and executes an emergency **Last Second Exit**. It blasts a resting Limit Sell order at 99¢ for any winning shares held, attempting to capture profit instantly without waiting for Polymarket's slow manual Web3 oracle settlement.
- Immediately after, V5 "Settles" the window internally. It resets the timer, updates the PnL metrics, and compounds all won revenue back into your active usable **Risk Bankroll** for the next 5-minute hunt.
