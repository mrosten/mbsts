# Proposal: Algorithm Refinement & Signal Pruning

Based on the Gemini log analysis, the bot is suffering from "Death by a Thousand Cuts" due to high-frequency, low-probability signals (Fakeouts and Snaps). Conversely, the MA20 "Slingshot" and Bollinger "Cobra" signals are highly effective.

## Proposed Strategy: Prune & Re-Weight

### 1. Disable High-Failure Scanners
*   **[DISABLE] Grind-Snap (GRI)**: This signal triggered 5 times with 0 wins. The logic is too sensitive to minor price oscillations.
*   **[DISABLE] N-Pattern Confirmed (NPA)**: Exhibited poor performance in Log 1. Breakout-following in choppy markets often leads to buying the local top.

### 2. Tighten "Bleeder" Logic
*   **Fakeout (FAK)**: Currently triggers on ANY move above open followed by a move below.
    *   **Change**: Require a minimum "Rescue Spike" height of at least **0.05%** of price before it counts as a failed attempt.
*   **Min-One Wick (MIN)**: Currently triggers on 2.0x wicks.
    *   **Change**: Increase threshold to **3.0x** body size to capture only extreme rejection candles.

### 3. Implement "Trend Gate" for Shorts
The logs show many `BET_DOWN` failures while the 4H trend was likely Neutral or Up.
*   **Enforcement**: Update the logic so that **ALL** `BET_DOWN` signals (including Slingshot Breakdown and Fakeout) require the `trend_4h` to be `DOWN` or `NEUTRAL` (never `UP`).

### 4. Reinforce "Power Signals"
*   **Slingshot (SLI)**: Maintain `MAX_BET` status for MA20 reclaims/breakdowns as they are the most profitable.
*   **Cobra (COB)**: Consider increasing the bet size for Cobra signals as they had a 100% win rate in the samples.

## Verification Plan
### Automated Testing
*   Run a fresh 1-hour simulation with these filters applied.
*   Compare the "Return %" and "Max Drawdown" against the previous baseline.
*   Verify that `BET_DOWN_FAKEOUT` frequency is reduced by at least 50%.
