# Sim Live Trend Linear v4.2 (Algorithm Reference)

**Status:** SIMULATION ONLY (Testing Phase)
**Script:** `sim_live_trend_linear_v4_2.py`
**Base Logic:** V3 (Data-Driven) + V4 (Macro) + V4.2 (News & Walls)

## 1. Core Logic Strategy (The Trigger)
The bot looks for a **Strong Uptrend** in the 15-minute timeframe between **T+300s** (5m) and **T+540s** (9m).

*   **Momentum**: Price must have risen `>= $0.25` in the last 90 seconds (Tightened from v3).
*   **Consistency**: Price must define a "rising" pattern for at least **3 consecutive checks** (~15s).
*   **Drift**: `(BTC_Price - Open_Price) / Open_Price` must be `> 0.04%`.
*   **Entry Ceiling**: Current Price must be `< $0.85`.
*   **Exhaustion**: Current Price must **NOT** have risen for `6 consecutive samples` (prevents buying the top).

### B. Late Game Sniper (v4.2 Signal 2)
*   **Time Window**: **T+11m to T+13m** (2-4 mins remaining).
*   **Price Condition**: `$0.80 <= Price <= $0.92` (Clear winner emerging, but not locked).
*   **Drift Condition**: `> 0.30%` (Market has moved significantly; unlikely to reverse).
*   **Macro Confluence**: Must match the **4H Trend** (e.g., if buying UP, 4H must be UP).
*   **Goal**: Catch the "easy money" at the end of a strong trend day.

## 2. Context Layers (The Filters)

### A. News Shock Detector (v4.2)
*   **Source**: RSS Scan (Cointelegraph, etc.) every 60s.
*   **Keywords**: `SEC`, `ETF`, `HACK`, `EXPLOIT`, `CPI`, `FED`, `WAR`, `CRASH`.
*   **Logic**:
    *   If KEYWORD found in recent title: **HALT TRADING** for 15 minutes.
    *   *Effect*: Prevents strategies from running blindly into a "News Nuke".

### B. Order Book "Wall" Detection (v4.2)
*   **Source**: Polymarket CLOB (`/book` endpoint).
*   **Metric**: `Wall Ratio = Bid_Volume / Ask_Volume` (within 5 cents of spread).
*   **Logic**:
    *   **Ratio < 0.5** (Thick Resistance): **SIZE * 0.5** (or SKIP). "Don't buy into a brick wall."
    *   **Ratio > 2.0** (Thick Support): **SIZE * 1.2**. "Whales are supporting this move."

### C. Macro Trend "River Current" (v4)
*   **Source**: Binance 4H Candles.
*   **Metric**: 4H SMA(3) vs SMA(10).
*   **Logic**:
    *   If 4H Trend is **DOWN** but we want to buy **UP**: **SIZE * 0.5**. "Swimming upstream is dangerous."

### D. Volatility Regime (v4)
*   **Source**: Binance 1H Candles (24h period).
*   **Metric**: ATR % (Average True Range).
*   **Logic**:
    *   **Low Volatility (< 0.5%)**: **SIZE * 0.6**. Breakouts often fail in low vol; markets just chop.

## 3. Position Sizing & Risk Management

### A. Base Sizing
*   **Sweet Spot (<$0.72)**: Target 20% of Bankroll.
*   **Standard ($0.72-$0.85)**: Target 12% of Bankroll.
*   **Bollinger Band Weight**: Multiplier (0.5x to 1.5x) based on price position within 36-period bands.

### B. Caps & Cuts
*   **Hard Cap**: Max **$15.00** per trade (Safety).
*   **Time-of-Day**: -40% Size at 5, 8, 11, 16 UTC (History of losses).
*   **Loss Streak**: -30% Size if 2+ consecutive losses.

### C. Partial Mitigation Hedge (The "Soft Floor")
*   **Trigger**:
    *   Trade is active.
    *   Time elapsed > 10 mins (`T+600`).
    *   We are **Losing Badly** (Price < $0.20).
    *   Opponent is **Winning** (Opp Price > $0.80).
*   **Action**:
    *   Buy Opponent side using **30% of Original Cost**.
*   **Result**:
    *   If Loss occurs: The hedge payout **reduces the net loss**.
    *   If Win occurs (Double Reversal): The hedge cost **reduces the net profit**, but we still win.
    *   *Goal*: Soften the blow of a reversal without risking a catastrophic "Double Down".
