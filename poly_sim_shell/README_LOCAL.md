# Offline Simulator (Local CSV)

**Location:** `poly_sim_shell/sim_local_cli.py`

## Overview
This tool allows you to backtest the "Hybrid Early Bird" strategy against historical Bitcoin price data stored in local CSV files. It simulates 15-minute market windows, applies a custom options pricing model, and tracks Profit & Loss (PnL) with dynamic position sizing.

## Features
*   **Offline Mode:** Runs entirely on local data (no API calls).
*   **Custom Pricing:** Estimates UP/DOWN option prices using a Normal Distribution model based on current volatility.
*   **Dynamic Wagering:** Scales bet size from **5%** (at 50% certainty) to **33%** (at 100% certainty) of your balance.
*   **Strategy:** Implements the T+6m and T+9m Drift Checks (Threshold: 0.04%).

## Data Requirements
The tool expects a CSV file in the same directory (`poly_sim_shell/`) with 3-minute candle data.
**Required Columns:** `Open Time`, `Open`, `High`, `Low`, `Close`.

## Pricing Model Logic
The probability of an outcome is calculated using the Z-Score of the current price divergence relative to the remaining time and volatility.
*   **Drift:** Percentage difference between Current Price and Strike (Open) Price.
*   **Volatility:** Estimated from the standard deviation of log returns in the dataset.
*   **Formula:** `Probability = CDF(Drift / Volatility_Remaining)`

## Position Sizing logic
Instead of a fixed trade size, the simulator calculates a "Wager Percentage" based on the estimated probability (Price) of the trade winning.

| Certainty (Price) | Wager % of Balance |
| :--- | :--- |
| **50¢** (Coindeflip) | **5%** (Base Bet) |
| **75¢** (Strong) | **19%** |
| **99¢** (Certain) | **33%** (Max Cap) |

## Usage
1.  Place your CSV file (e.g., `back_test_results_2026-01-31_3min.csv`) in `poly_sim_shell/`.
2.  Run the script:
    ```powershell
    python poly_sim_shell/sim_local_cli.py
    ```
3.  Select the file from the menu.
4.  Enter your starting balance.

The simulator will print a window-by-window log of trades and a final PnL report.
