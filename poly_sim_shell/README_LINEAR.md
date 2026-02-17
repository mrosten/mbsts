# Linear Trend Strategy Simulator (1-Sec)
# Version 2.0
**File:** `sim_trend_linear_1sec.py`

This simulator implements a specialized "Linear Trend" strategy designed to catch strong, steady movements early (at T+7 minutes) while retaining a safety fallback (at T+9 minutes). It uses 1-second granularity data for precise volatility estimation.

## 🧠 Core Strategy Logic

### 1. Sampling Phase (Minute 5:00 to 7:00)
*   The bot checks the price **every 30 seconds**.
*   It records the price of the "Winning Side" (UP or DOWN) at:
    *   T+5:00 (300s)
    *   T+5:30 (330s)
    *   T+6:00 (360s)
    *   T+6:30 (390s)
    *   T+7:00 (420s)

### 2. Entry Triggers
The bot has three distinct entry points, prioritized in order:



2.  **T+7 Linear Trend Trigger**
    *   **Time:** Minute 7:00
    *   **Condition:**
        *   **Relaxed Linearity:** Generally increasing.
        *   *Exception:* A "dip" is allowed IF:
            *   It is small (≤ $0.05).
            *   AND the *next* sample recovers (strictly increases).
            *   (The sample at T+7:00 cannot form a dip).
        *   Drift > 0.04%.
        *   Price < $0.85 (Safety Cap).
    *   **Action:** Buy "Linear Trend" (20% of Balance). This detects strong, unidirectional moves.

3.  **T+9 Standard Fallback**
    *   **Time:** Minute 9:00
    *   **Condition:** Drift > 0.04% AND Price < $0.85.
    *   **Action:** Buy Standard (10% of Balance). Catches late developing trends.

## ⚙️ Calibration & Safety

This simulator has been scientifically calibrated against 3-minute data to ensure realistic pricing and effective risk management.

*   **Volatility Multiplier (1.55x)**:
    *   1-second returns normally underestimate volatility compared to 3-minute candles.
    *   We apply a **1.55x multiplier** to the volatility calculation.
    *   *Effect:* Prevents the model from being "overconfident" and pricing options at $0.98 too early. It forces entry prices down to realistic levels ($0.60 - $0.80).

*   **Global Price Cap (< $0.85)**:
    *   The bot triggers **NO TRADE** if the option price is above $0.85.
    *   *Reason:* Buying at $0.90+ requires a >90% win rate to break even. Caps ensure we only enter when the Risk/Reward ratio is favorable.

## 🚀 Usage

Run the simulator from the command line:

```bash
python poly_sim_shell/sim_trend_linear_1sec.py
```

1.  **Select Data File**: Choose `BTC_Dec1_2024_1s.csv` (Option 1).
2.  **Enter Balance**: Input your starting bankroll (e.g., `100`).

### Expected Results (Dec 1, 2024 Data)
*   **Win Rate**: ~84%

## 🔴 Live Paper Trading

You can also run this strategy on **real-time market data** (with fake money) using:

```bash
python poly_sim_shell/sim_live_trend_linear.py
```

*   **Logic**: Identical to `sim_trend_linear_1sec.py`.
*   **Data**: Fetches live BTC prices from Binance and Polymarket.
*   **Sampling**: Runs in a loop, checking price at T+5:00, T+5:30... etc.
*   **Requirements**: Internet connection (no API keys needed for simulation).

