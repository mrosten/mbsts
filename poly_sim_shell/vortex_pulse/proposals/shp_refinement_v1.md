# ShapeMatcher (SHP) Algorithm Refinement Proposals
**Date:** 2026-04-03
**Status:** Brainstorming / Draft

Following the initial implementation of the visual pattern scanner, these are the proposed refinements to enhance its accuracy, robustness, and user experience.

## 1. Dynamic Time Warping (DTW) - Time-Elasticity
*   **Concept**: Move away from rigid 30-point linear resampling.
*   **Benefit**: Allows the market to match a drawing even if it forms slightly faster or slower than the hand-drawn original.
*   **Implementation**: Use a DTW distance metric instead of Euclidean distance to find the "best alignment" in the time domain.

## 2. ATR-Relative Leeway (Volatility Scaling)
*   **Concept**: Automatically scale the price leeway based on the current 5-minute ATR.
*   **Benefit**: Ensures the "tightness" of the match is consistent. A 5¢ leeway is huge in a stagnant market but impossible in a high-volatility "chaos" phase.
*   **Formula**: `Effective_Leeway = Base_Leeway * (Current_ATR / Baseline_ATR)`.

## 3. Visual "Ghosting" on Main Chart
*   **Concept**: Render the high-confidence pattern as a dim overlay on the `PulseLeanChart`.
*   **Benefit**: Provides immediate visual feedback to the user on how the live price action is tracking against their chosen archetype.
*   **Trigger**: Show ghosting when similarity > 60%.

## 4. Critical "Anchor" Points
*   **Concept**: Allow users to mark specific nodes in the drawing as "Anchors".
*   **Benefit**: Certain price levels (like a specific support floor) are more important than others. If the market misses an anchor, the match is discarded regardless of overall RMSE.

## 5. Multi-Pattern "Heat Mapping"
*   **Concept**: A small UI widget showing sparklines of all active patterns and their current match %.
*   **Benefit**: Allows the user to monitor multiple setups simultaneously without switching modals.

## 6. Velocity-Weighted Completion
*   **Concept**: Ensure the *momentum* at the moment of match aligns with the intended breakout direction.
*   **Benefit**: Prevents "False Matches" where the price reaches the final coordinate but is exhausted or reversing, rather than surging into the trade.
