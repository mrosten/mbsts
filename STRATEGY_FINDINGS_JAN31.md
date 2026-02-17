# Bitcoin 15m Options Strategy Findings
**Date:** January 31, 2026
**Data Source:** 3-minute candle data from Binance (BTCUSDT)

## 1. Executive Summary
Analysis of market behavior on Jan 31st represents a strong case for **trend continuation** strategies within 15-minute windows. The market demonstrated high predictability once a move was established, provided there was sufficient signal strength.

*   **Best Strategy:** "Hybrid Early Bird" (Check 6m, then 9m)
*   **Win Rate:** ~88%
*   **Key Filter:** Avoid trading when the price drift is < 0.04% from the Open.

---

## 2. Strategies Analyzed

### A. The "Safe" Late Entry (9-Minute Mark)
*   **Logic:** Wait until the 9-minute mark (closing of the 3rd 3m candle). If price is > 0.04% away from Open, enter in that direction.
*   **Performance:**
    *   **Accuracy:** **88.89%** (24/27 correct)
    *   **Pros:** High confidence, filters out most noise.
    *   **Cons:** Misses opportunities; entry price is often worse (chasing the trend).

### B. The "Hybrid Early Bird" (Recommended)
*   **Logic:**
    1.  At **6 Minutes:** Check if Signal Strength > 0.04%. If YES -> **ENTER**.
    2.  If NO -> Wait until **9 Minutes**. Check if Signal Strength > 0.04%. If YES -> **ENTER**.
    3.  If NO -> **NO TRADE**.
*   **Performance:**
    *   **Accuracy:** **87.88%** (29/33 correct)
    *   **Trade Volume:** 33 Trades (vs 27 for Safe Strategy).
    *   **Efficiency:** **70% of trades (23/33) were entered at the 6-minute mark**, securing significantly better pricing without sacrificing accuracy.

---

## 3. Failure Analysis: When does it fail?
We analyzed the specific blocks where the 9-minute prediction failed.

*   **Primary Culprit:** **Low Volatility / Noise**.
*   **Data:**
    *   Failed predictions had **65% weaker signals** than successful ones.
    *   The "Failed" moves averaged only a **0.03%** deviation from the open (practically flat).
*   **Takeaway:** The strategy doesn't fail because of "reversals" (volatility); it fails because of "indecision" (flatness).
*   **Solution:** The **0.04% Signal Strength Threshold** is the critical component to filter out these coin-flip scenarios.

---

## 4. Operational Guidelines for Bot
To implement the **Hybrid Strategy**:

1.  **Poll at T+6m:**
    *   Calculate `Abs(Price - Open) / Open`.
    *   If `> 0.0004` (0.04%): **Buy Immediately**. Stop processing this block.
2.  **Poll at T+9m:**
    *   If no trade yet, calculate `Abs(Price - Open) / Open`.
    *   If `> 0.0004`: **Buy Immediately**.
3.  **Risk Management:**
    *   This strategy relies on high win-rate trend continuation.
    *   Since entry is mid-candle, ensure the options market liquidity is sufficient before executing key orders.
