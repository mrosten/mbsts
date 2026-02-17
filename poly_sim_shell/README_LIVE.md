# Live Trading Bot (Real Money)

**Location:** `poly_sim_shell/live_trade_cli.py`

## ⚠️ WARNING: REAL MONEY RISK
This script executes **REAL** trades on the Polymarket CLOB (Central Limit Order Book).
*   It uses your **PRIVATE_KEY** from `.env`.
*   Trades are **IRREVERSIBLE**.
*   Ensure you have sufficient USDC (Polygon) and MATIC (for gas, though Polymarket is often gasless via proxy).

## Methodology
This bot runs the "Hybrid Early Bird" strategy live with **Manual Confirmation**:
1.  **Sync:** Connects to Polymarket/Binance. Prints the **Monitoring URL** for easy access.
2.  **Sampling (Required):** The bot **MUST** be active at the **T+3m** mark (Heartbeat) to qualify for trading. If you start late (e.g., at T+5), it will skip trading for that window to ensure data integrity.
3.  **Signal:** Checks for Drift > 0.04% at **T+6m** and **T+9m** (T+9 check is skipped if T+6 triggers).
4.  **Confirmation:** If a signal is found, the bot will **BEEP** and pause for your input: `>>> CONFIRM PURCHASE ...?`.
5.  **Execute:** You must type **`YES`** (full word) to execute. Any other input cancels the trade.

## Strategy Logic: "Hybrid Early Bird"
The bot uses a **Drift-Following** strategy. It assumes that if Bitcoin's price moves significantly from the Opening Price at specific times, the 15-minute candle will close in that direction.

### 1. The Metric: Drift %
Signal strength is calculated as the percentage difference between the **Real-Time Price** and the **Opening Price** (T-0:00).
```
Drift % = Abs(Current Price - Opening Price) / Opening Price
```

### 2. The Checkpoints
The bot evaluates the market at two specific moments:

*   **Checkpoint A (T+6 Minutes):**
    *   **Window:** 5:45 to 6:15 elapsed.
    *   **Condition:** Is `Drift % > 0.04%`?
    *   **Action:** If YES -> **SIGNAL**.

*   **Checkpoint B (T+9 Minutes):**
    *   **Window:** 8:45 to 9:15 elapsed.
    *   **Condition:** (Only if no trade taken at T+6) Is `Drift % > 0.04%`?
    *   **Action:** If YES -> **SIGNAL**.

### 3. The Decision
If a SIGNAL is generated:
1.  **Direction:**
    *   `Price > Open` -> **UP**
    *   `Price < Open` -> **DOWN**
2.  **Safety Validation:**
    *   **Sampling:** Did the bot witness the T+3 heartbeat? (Required to ensure valid trend).
    *   **Price Floor:** Is the Token Price > $0.40? (Ensures we are backing the favorite; avoids buying 16-cent losers).
3.  **Prompt:** If all checks pass, the bot Beeps and asks `CONFIRM PURCHASE?`. You must type `YES` to proceed.

## Configuration
*   **Trade Size:** Fixed at **$5.50 USDC**.
*   **Safety:** 
    *   **Price Floor:** Aborts if price < $0.40 (prevents buying the wrong side).
    *   **One Trade:** Stops after 1 trade per 15-minute window.
    *   **Stateless:** The bot does not save state to disk. Restarting it resets its memory (so run only one instance!).

## Usage
1.  Ensure `.env` contains your `PRIVATE_KEY` and `PROXY_ADDRESS`.
2.  Run the bot:
    ```powershell
    python poly_sim_shell/live_trade_cli.py
    ```
3.  **Important:** active terminals must be kept open. If you close the terminal, the bot stops.
4.  **Dynamic Variant:** To visualize dynamic wager sizing (5-33%):
    ```powershell
    python poly_sim_shell/live_trade_dynamic_cli.py
    ```
    *(Note: The Dynamic bot also has the Safety Floor and Double-Trade protection, but currently Auto-Executes without manual confirmation).*

## File Structure
*   `live_trade_cli.py`: Main executable (Standard/Manual).
*   `live_trade_dynamic_cli.py`: Dynamic Sizing variant.
*   `live_trade_log.txt`: Persistent log of all actions.
