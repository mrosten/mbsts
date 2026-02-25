# Polymarket Sniper v4 (run_sniper_v4.py)
This document outlines the core logic and operational details of the Poly Sim Shell's V4 Sniper Algorithm (`run_sniper_v4.py`), with a specific focus on its risk management, betting percentage calculations, and bankroll behavior.

## Overview
`run_sniper_v4.py` is the entry point script for `mbsts_v4`. It initializes the trading environment by instantiating either a `SimBroker` or `LiveBroker`, depending on the user's selection, and runs the `SniperApp`. The core logic for handling funds and bet sizes is centralized in the `RiskManager` and `AlgorithmPortfolio` classes in `mbsts_v4/risk.py`, with thresholds defined in `mbsts_v4/config.py`.

## Betting Percentages Logic
The system uses a dynamic, proportional betting model rather than fixed-dollar amounts. This ensures the system automatically scales down during downswings and scales up during upswings.

### 1. Base Sizing
Every algorithm's default bet side is **12%** (`DEFAULT_RISK_PCT = 0.12`). 
The bet size is calculated as `0.12 * current_available_bankroll`.

> [!NOTE]
> *Current Available Bankroll* is dynamic. In simulator mode, it is the full balance of the specific algorithm. In Live Mode, the total starting balance is divided by 8 (`LIVE_RISK_DIVISOR`), meaning the system effectively trades with only 12.5% of the true account balance to protect funds.

### 2. High-Conviction Scaling (Strong Patterns)
If the trading algorithm detects a high-conviction setup (specifically patterns containing "UPTREND", "STRONG_TREND", "COBRA", "LIQ_SWEEP", or "LATE_REVERSAL"), the system aggressively scales up the bet size to **20%** of the current bankroll (`STRONG_RISK_PCT = 0.20`).

### 3. Risk Mitigation (Bet Slashes)
The algorithm aggressively cuts the calculate bet size under adverse conditions:
- **Counter-Trend:** If the overarching 4-hour trend disagrees with the current trade's direction, the bet size is slashed by **50%** (`cost *= 0.5`).
- **Fakeouts:** If the pattern identifies as a "FAKEOUT", the bet size is also slashed by **50%**.
- **Losing Streaks:** If an algorithm has suffered 2 or more consecutive losses, its bet size is slashed by **30%** (`cost *= 0.7`) to prevent rapid depletion during a choppy market phase.

### 4. Clamping and Limits
After percentage calculations and mitigations, the bet size is clamped:
- **Maximum Cap:** No single bet can exceed **$100.00** (`MAX_BET_SESSION_CAP`).
- **Minimum Bet Step-Up:** If the calculated bet is below **$5.50** (`MIN_BET`), but the algorithm still has at least $5.50 in its balance, it will bypass the percentage rule and forcefully bet the minimum $5.50. This prevents the bot from making micro-bets that fall under exchange minimums, acting as a final "all-in" for the remaining dust. If the balance is strictly less than $5.50, the bet size drops to **$0.00**.

## Bankroll Growth and Retention Logic
The system isolates the bankroll on a **per-algorithm** basis using `AlgorithmPortfolio`. This prevents a single underperforming strategy from draining the capital allotted to a successful one.

### Trade Registration & Deductions
When a trade is placed, the calculated `cost` is immediately deducted from the algorithm's `balance`. The trade is kept in a list of `active_trades`.

### Trade Settlement
Once the market window closes, the `settle_window` function resolves all `active_trades`:
1. **Winning Trades:** The algorithm's `balance` increases by the number of `shares` won (payout). The net profit is essentially `payout - initial_cost`. The consecutive loss counter is reset to 0.
2. **Draws/Ties:** The original `cost` is fully refunded directly back into the `balance`. No loss or gain is recorded, but a `draw` tally is incremented.
3. **Losing Trades:** Because the initial `cost` was already deducted at trade entry, nothing is added back. The consecutive loss counter increments by 1.

### Algo Deactivation (Death)
If an individual algorithm's `balance` ever drops below the `MIN_BET` threshold ($5.50) after settlement, its `is_active` flag is set to `False`. The algorithm "dies" and will no longer participate in the market, cleanly preserving the remainder of its sub-$5.50 balance without throwing errors or attempting invalid trades.
