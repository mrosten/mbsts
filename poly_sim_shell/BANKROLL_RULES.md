# Bankroll and Bet Sizing Rules (mbsts_v4)

This document outlines the precise, step-by-step rules governing how the bankroll and bet sizing currently operate, based on `app.py`, `risk.py`, and `config.py`.

## 1. The "Base Bankroll"
- **Sim Mode:** The bankroll is exactly whatever your simulated account total is.
- **Live Mode:** The active trading bankroll is dynamically initialized as exactly **1/8th (12.5%)** of your total Polymarket wallet balance (`LIVE_RISK_DIVISOR = 8`).

## 2. Base Calculation (The "Risk Percentages")
When an algorithm triggers, it takes your *active* Risk Bankroll (from step 1) and multiplies it by a specific risk percentage:
- **Default Risk (`DEFAULT_RISK_PCT`):** 12% of the bankroll.
- **Strong Signal Risk (`STRONG_RISK_PCT`):** 20% of the bankroll. 
  *(This higher 20% rate is strictly applied ONLY if the triggering algorithm is: "UPTREND", "STRONG_TREND", "COBRA", "LIQ_SWEEP", or "LATE_REVERSAL".)*

## 3. Modifiers & Penalties (The "Adjustments")
Once the base bet amount is calculated (e.g., $15.00), the bot checks market context to apply safety penalties:
- **Fakeout Penalty:** If the algorithm triggering is "Fakeout", the bet is immediately cut in half (**0.5x**).
- **Counter-Trend Penalty:** If the trade direction (UP/DOWN) goes against the current 4-Hour Trend, the bet is cut in half (**0.5x**). *(Ignored if the 4H trend is 'NEUTRAL')*
- **Tilt/Loss Penalty:** If the specific algorithm placing the bet has lost its last 2 trades consecutively, the bet is reduced by 30% (**0.7x multiplier**).

## 4. Hard Constraints (The "Clamping")
Finally, after all modifiers, the bot clamps the final dollar amount:
- **Maximum Cap:** No single bet will *ever* exceed **$100.00** (`MAX_BET_SESSION_CAP`).
- **Minimum Floor:** If the calculated bet is below **$5.50**, it will force the bet to exactly $5.50 (to satisfy API minimums).
- **Insufficient Funds:** If your entire available bankroll drops below $5.50, the bot calculates a bet size of **$0.00** and refuses to place the trade entirely.

## 5. Payout Replenishment (The "Refill Logic" in `app.py`)
When a 5-minute window settles:
1. Profits/revenues are added directly back to your active Risk Bankroll.
2. If your Risk Bankroll falls below the target (1/8th of your total wallet), the bot will attempt to automatically replenish it from your main Polymarket wallet to restore it back up to the target cap on the next window.

*(Note: In the current testing environment, the Moshe algorithm specifically intercept this entire flow at the last second, overriding steps 2-4 and forcefully executing at EXACTLY `$4.50` limit order at $0.90.)*
