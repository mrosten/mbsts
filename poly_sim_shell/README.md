# PolySim & Live Trading Shell

This specific folder contains **Real Money** trading bots for Polymarket's 15m Bitcoin Markets.

> **⚠️ WARNING: REAL FUNDS**  
> These scripts execute real transactions on the Polygon Chain. Use at your own risk.  
> Ensure your `.env` file is secure.

---

## 🤖 Active Bots (The "Swing" Strategy)

The current best-performing strategy, optimized for **1-second data**.

### 1. Live Swing Bot (`bot_swing_1sec.py`)
This is the **primary live trading bot**.
*   **Strategy**: "Swing Hunter" (Dynamic 1-sec sampling).
    *   **Momentum**: Follows drift (0.15% - 0.35%).
    *   **Reversion**: Fades extreme moves (> 0.35%).
    *   **Safety**: Waits for high volatility + low efficiency (choppy market).
*   **Wager**: Fixed **$5.50** minimum or Dynamic Sizing (configurable).
*   **Run**: `python poly_sim_shell/bot_swing_1sec.py`

### 2. Swing Simulator (`sim_swing_1sec.py`)
The backtesting engine for the Swing Strategy.
*   **Data**: Uses 1-second interval CSVs (in `data/`).
*   **Run**: `python poly_sim_shell/sim_swing_1sec.py`

---

## 🏛️ Trend / Legacy Bots (The "T+9" Strategy)

Previous generation strategies relying on 3-minute checkpoints (T+6, T+9).

### 1. Trend Bot CLI (`bot_trend_t9.py`)
*   **Strategy**: classic "Early Bird". Checks drift > 0.04% at 6m and 9m marks.
*   **Features**: Manual Confirmation (Press 'Yes'), Auto-Sell @ $0.99.
*   **Run**: `python poly_sim_shell/bot_trend_t9.py`

### 2. Trend Bot GUI (`bot_trend_t9_gui.py`)
*   **Visuals**: A terminal UI with signal bars and timeline.
*   **Run**: `python poly_sim_shell/bot_trend_t9_gui.py`

### 3. Simulators

| File | Strategy | Data Interval | Description |
|---|---|---|---|
| `sim_trend_linear_1sec.py` | **Linear Trend** | 1-Sec | Checks for linear price increases from T+5 to T+7. Calibrated 1.55x Vol. |
| `sim_live_trend_linear.py` | **Live Linear** | Real-Time | **Paper Trader**. Runs the Linear Trend strategy on live market data. |
| `sim_dynamic_old.py` | Paper Trader | Real-Time | Simulated live trading (Fake Money). |
| `sim_trend_t9.py` | Trend (T+9) | 3-Min | Legacy T+9 strategy. |

### Strategy Documentation
- **[READ: Linear Trend Strategy](README_LINEAR.md)**: Details on the new "Linear" logic and calibration.

---

## 🛠️ Tools & Data

*   **`tool_fetch_1sec.py`**: Downloads 1-sec granularity data from Binance for the Swing Simulator.
*   **`tool_fetch_3min.py`**: Downloads 3-min granularity data.
*   **`data/`**: Directory containing all CSV datasets.

---

## ⚙️ Setup

1.  **Environment**:
    Create a `.env` file in `poly_sim_shell/`:
    ```ini
    PRIVATE_KEY=0xYourKey...
    PROXY_ADDRESS=0xOptionalProxy...
    ```

2.  **Dependencies**:
    ```bash
    pip install requests asyncio numpy pandas python-dotenv py-clob-client eth-account
    ```
