# Live Dynamic Strategy Bot (1-Sec)

**File:** `live_trade_dynamic_1sec.py`

This is a high-frequency trading bot designed for **Polymarket BTC 15-Minute Markets**. Unlike standard bots that check prices every few minutes, this bot samples data **every second** to calculate real-time volatility and market efficiency metrics.

## Strategy: "The Swing Hunter"

This bot implements the strategy optimized in our `sim_local_dynamic_1sec.py` simulator (which achieved ~121% returns in testing).

### Core Logic
1.  **High Volatility**: Waits for the market to enter a "Swing Zone" (Top 20% volatility).
2.  **Low Efficiency**: Checks if price action is "choppy" (Efficiency Ratio < 0.35).
3.  **Momentum vs. Reversion**:
    *   **Momentum**: If price drifts **0.15% - 0.35%**, it follows the trend (Bets with the move).
    *   **Reversion**: If price drifts **> 0.35%** (Extreme), it fades the move (Bets against it).

### Execution
*   **Wager Size**: Dynamic sizing ($5 minimum, up to $100 max) based on conviction.
*   **Liquidity Cap**: Never bets more than $100 per trade to avoid slippage.
*   **Auto-Exit**: Immediately places a Limit Sell order at **$0.99** to capture max profit if the trade wins.

## Setup

1.  **Environment Variables**: Ensure your `.env` file in `poly_sim_shell/` has:
    ```ini
    PRIVATE_KEY=0xYourPrivateKey...
    PROXY_ADDRESS=0xYourProxyAddress...
    ```

2.  **Dependencies**:
    ```bash
    pip install requests asyncio numpy python-dotenv py-clob-client eth-account
    ```

## Usage

Run the bot from the command line:

```bash
python poly_sim_shell/live_trade_dynamic_1sec.py
```

1.  It will ask for a **Base Wager Amount** (Default: $50).
    *   *Note: Actual bet size scales dynamically but is capped at $100.*
2.  It will calibrate against Binance spot prices.
3.  It will verify the active Polymarket event URLs.
4.  **Display**:
    *   It prints a real-time "Heartbeat" showing BTC Price, Option Prices, and Drift.
    *   When a signal triggers, it logs ``>>> SIGNAL: UP | Swing MOMENTUM...`` and executes immediately.

## ⚠️ RISK WARNING

*   **Real Money**: This bot executes trades on the Polygon mainnet using real USDC.
*   **Auto-Execution**: Trades are placed **automatically** without confirmation.
*   **Speed**: Be aware that 1-second sampling means it can react faster than you can see on the web UI.

## Troubleshooting

*   **Logs**: Check `live_dynamic_log.txt` for a history of all checks and trades.
*   **"SKIPPED"**: If you see skipped trades, it's likely due to safety filters (e.g., price too low/high or spread too wide).
