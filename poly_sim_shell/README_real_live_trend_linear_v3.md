# Real Live Trend Linear Bot v3 (Data-Driven)

**Script:** `real_live_trend_linear_v3.py`
**Status:** 🔴 LIVE TRADING (Real Money)
**Logic Base:** `sim_live_trend_linear_v3.py` (Version 6.0)

## Overview
This is the **advanced, data-driven version** of the automated trading bot. It implements rules derived from analyzing 748 simulated trades to maximize profitability and minimize drawdowns.

### Key Logic Improvements (vs v2)
1.  **Hard Position Cap ($15)**: The bot will **never** spend more than $15 on a single trade, regardless of bankroll size. In simulations, large bets caused 94% of losses.
2.  **Exhaustion Filter**: If the price rises for **5 consecutive samples** (approx 30s), the bot **skips** the trade. This prevents "buying the top" of a spike.
3.  **Time-of-Day Sizing**: Automatically reduces bet size by **40%** during historically bad trading hours (05:00, 08:00, 11:00, 16:00 UTC).
4.  **Sweet Spot Tiering**:
    *   **Sweet Spot (<$0.72)**: Targets **20%** of bankroll (up to $15 cap).
    *   **Standard ($0.72 - $0.85)**: Targets **12%** of bankroll.
    *   **High Risk (>$0.85)**: Ignored (unless High-Conf signal).
5.  **Loss Streak Protection**: Reduces trade size by **30%** after 2 consecutive losses.

## Strategy
The bot scans the **BTC 15-Minute Up/Down** market between **T-5:00** and **T-9:00** (middle of the window).

### Signals
1.  **High Confidence (Rising 88-93)**:
    *   Price is between $0.88 and $0.93.
    *   Price is actively rising (Higher than 30s ago).
    *   Drift > 0.04%.
    *   *Goal: Catch the final run-up to $0.99.*

2.  **Strong Uptrend (Momentum)**:
    *   **Momentum**: Price gained >= $0.10 in last 90s.
    *   **Consistency**: Price rose at least 2 samples in a row.
    *   **Not Exhausted**: Price rose fewer than 5 samples in a row.
    *   **Price**: Must be < $0.85.
    *   *Goal: Catch the middle of a strong move.*

## Execution & Safety
*   **Proxy Support**: Automatically handles Polymarket Proxy signatures (`neg_risk=True` / `False` fallback).
*   **Limit Orders**: Places limit orders at `Current Price + $0.05` (capped at $0.99) to ensure fill while protecting against massive slippage.
*   **Instant Take-Profit**: Immediately posts a **Sell Limit @ $0.99** after buying.
*   **Reserves**: Allows you to set a "Reserve" amount that the bot will never touch.

## Usage
```bash
python real_live_trend_linear_v3.py
```
*   **Startup**: Enter your desired starting bankroll (e.g., `20` to trade with $20).
*   **Logs**: Check `REAL_live_v3_log_...txt` for detailed decision logs.

## ⚠️ Requirements
*   **Private Key**: Must be in `.env`.
*   **Proxy Address**: Must be in `.env` (if using proxy).
*   **USDC Balance**: Account must have USDC (Polygon) to trade.
*   **MATIC Balance**: Account (or Relayer) needs MATIC for gas (Polymarket covers this via Relayer usually).
