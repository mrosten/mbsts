"""
Polymarket Bet Price Analysis & Prediction Model (v2)
======================================================
NOTE: The drift_pct in this data is always positive (absolute value).
We need to use (btc_price - btc_open) directly for signed drift.

Key insight: up_price ≈ probability that final price > open price
- When btc_price > btc_open: up_price is HIGH
- When btc_price < btc_open: up_price is LOW
"""

import pandas as pd
import numpy as np
from scipy import optimize
from scipy.stats import norm
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')


def load_and_clean_data(filepath):
    """Load CSV and compute SIGNED drift."""
    df = pd.read_csv(filepath)
    
    # SIGNED drift (critical fix!)
    df['signed_drift'] = (df['btc_price'] - df['btc_open']) / df['btc_open']
    
    df['time_remaining'] = 900 - df['elapsed_sec']
    df['time_remaining_pct'] = df['time_remaining'] / 900
    
    # Filter valid data
    df = df[(df['up_price'] >= 0) & (df['up_price'] <= 1)]
    df = df[(df['down_price'] >= 0) & (df['down_price'] <= 1)]
    df = df[(df['elapsed_sec'] >= 0) & (df['elapsed_sec'] <= 900)]
    
    return df


def analyze_data(df):
    """Explore the corrected data."""
    print("=" * 60)
    print("DATA EXPLORATION (SIGNED DRIFT)")
    print("=" * 60)
    
    print(f"\nTotal data points: {len(df)}")
    print(f"Unique 15-min windows: {df['window_start'].nunique()}")
    
    print(f"\nSIGNED Drift range: {df['signed_drift'].min()*100:.4f}% to {df['signed_drift'].max()*100:.4f}%")
    
    print("\n--- Correlations with UP_PRICE (using SIGNED drift) ---")
    print(f"  signed_drift: {df['up_price'].corr(df['signed_drift']):.4f}")
    print(f"  elapsed_sec: {df['up_price'].corr(df['elapsed_sec']):.4f}")
    
    # Show some sample rows
    print("\n--- Sample rows ---")
    sample = df[['elapsed_sec', 'btc_price', 'btc_open', 'signed_drift', 'up_price', 'down_price']].head(10)
    print(sample.to_string())


def logistic_model(signed_drift, time_remaining_pct, k, alpha, beta):
    """
    Improved logistic model with time decay.
    
    up_price = sigmoid(k * signed_drift * time_scale)
    
    Where time_scale increases as time runs out, making the market
    more sensitive to drift near the end.
    """
    # Clamp time to avoid division issues
    t = np.maximum(time_remaining_pct, 0.001)
    
    # Time scaling: sensitivity increases as time runs out
    # At t=1 (start): time_scale ≈ 1
    # At t=0 (end): time_scale ≈ 1 + alpha
    time_scale = 1 + alpha * (1 - t) ** beta
    
    z = k * signed_drift * time_scale * 100  # Scale to percentage
    up_price = 1 / (1 + np.exp(-z))
    down_price = 1 - up_price
    
    return up_price, down_price


def fit_model(df):
    """Fit the logistic model using least squares."""
    print("\n" + "=" * 60)
    print("MODEL FITTING: Logistic with Time Decay")
    print("=" * 60)
    
    def objective(params):
        k, alpha, beta = params
        pred_up, pred_down = logistic_model(
            df['signed_drift'].values,
            df['time_remaining_pct'].values,
            k, alpha, beta
        )
        mse_up = np.mean((pred_up - df['up_price'].values) ** 2)
        mse_down = np.mean((pred_down - df['down_price'].values) ** 2)
        return mse_up + mse_down
    
    # Grid search + optimization for robustness
    best_result = None
    best_loss = float('inf')
    
    for k_init in [20, 50, 100, 200]:
        for alpha_init in [2, 5, 10, 20]:
            for beta_init in [0.5, 1, 2]:
                try:
                    result = optimize.minimize(
                        objective,
                        [k_init, alpha_init, beta_init],
                        bounds=[(1, 500), (0.1, 100), (0.1, 5)],
                        method='L-BFGS-B'
                    )
                    if result.fun < best_loss:
                        best_loss = result.fun
                        best_result = result
                except:
                    pass
    
    k, alpha, beta = best_result.x
    
    print(f"\nOptimal Parameters:")
    print(f"  k (sensitivity):     {k:.4f}")
    print(f"  alpha (time decay):  {alpha:.4f}")
    print(f"  beta (decay curve):  {beta:.4f}")
    
    # Evaluate
    pred_up, pred_down = logistic_model(
        df['signed_drift'].values,
        df['time_remaining_pct'].values,
        k, alpha, beta
    )
    
    print("\n--- UP Price Prediction ---")
    print(f"  MSE:  {mean_squared_error(df['up_price'], pred_up):.6f}")
    print(f"  MAE:  {mean_absolute_error(df['up_price'], pred_up):.4f}")
    print(f"  R²:   {r2_score(df['up_price'], pred_up):.4f}")
    
    print("\n--- DOWN Price Prediction ---")
    print(f"  MSE:  {mean_squared_error(df['down_price'], pred_down):.6f}")
    print(f"  MAE:  {mean_absolute_error(df['down_price'], pred_down):.4f}")
    print(f"  R²:   {r2_score(df['down_price'], pred_down):.4f}")
    
    return k, alpha, beta


def generate_formulas(k, alpha, beta):
    """Output the prediction formulas."""
    print("\n" + "=" * 60)
    print("FINAL PREDICTION FORMULAS")
    print("=" * 60)
    
    print(f"""
JavaScript Implementation:
--------------------------
function estimateBetPrices(btcPrice, btcOpen, elapsedSec) {{
    // Calculate signed drift (positive = up, negative = down)
    const signedDrift = (btcPrice - btcOpen) / btcOpen;
    
    // Time remaining as fraction (1 = start, 0 = end)
    const t = Math.max((900 - elapsedSec) / 900, 0.001);
    
    // Time scaling - increases sensitivity near end of window
    const timeScale = 1 + {alpha:.4f} * Math.pow(1 - t, {beta:.4f});
    
    // Logistic transformation
    const z = {k:.4f} * signedDrift * timeScale * 100;
    const upPrice = 1 / (1 + Math.exp(-z));
    const downPrice = 1 - upPrice;
    
    return {{ upPrice, downPrice }};
}}

// Example: BTC at 78000, opened at 78100, 400 seconds elapsed
// estimateBetPrices(78000, 78100, 400)


Python Implementation:
----------------------
import numpy as np

def estimate_bet_prices(btc_price, btc_open, elapsed_sec):
    '''
    Estimate Polymarket UP/DOWN prices based on BTC price movement.
    
    Args:
        btc_price: Current BTC price
        btc_open: BTC price at start of 15-min window
        elapsed_sec: Seconds elapsed (0-900)
    
    Returns:
        tuple: (up_price, down_price) where each is 0-1
    '''
    # Signed drift (positive = price up, negative = price down)
    signed_drift = (btc_price - btc_open) / btc_open
    
    # Time remaining as fraction
    t = max((900 - elapsed_sec) / 900, 0.001)
    
    # Time scaling
    time_scale = 1 + {alpha:.4f} * (1 - t) ** {beta:.4f}
    
    # Logistic transformation
    z = {k:.4f} * signed_drift * time_scale * 100
    up_price = 1 / (1 + np.exp(-z))
    down_price = 1 - up_price
    
    return up_price, down_price


# Example usage:
# up, down = estimate_bet_prices(78000, 78100, 400)
# print(f"UP: ${{up:.3f}}, DOWN: ${{down:.3f}}")
""")
    
    print("\n" + "=" * 60)
    print("MODEL INTERPRETATION")
    print("=" * 60)
    print(f"""
The model works as follows:

1. SIGNED DRIFT = (current_price - open_price) / open_price
   - Positive drift → UP side leading
   - Negative drift → DOWN side leading

2. TIME SCALING = 1 + {alpha:.2f} * (1 - time_remaining)^{beta:.2f}
   - At start (t=1): scale ≈ 1.0 (low sensitivity)
   - At end (t→0): scale ≈ {1 + alpha:.1f} (high sensitivity)
   
3. UP_PRICE = sigmoid({k:.1f} * drift * time_scale)
   - Near fair value (drift≈0): UP ≈ DOWN ≈ $0.50
   - With time decay: prices become extreme as time runs out

Key insight: As we approach the end of the 15-min window,
the market becomes MORE sensitive to small price movements.
A 0.1% drift means more with 1 minute left than with 10 minutes left.
""")


def plot_results(df, k, alpha, beta):
    """Visualize model performance."""
    pred_up, _ = logistic_model(
        df['signed_drift'].values,
        df['time_remaining_pct'].values,
        k, alpha, beta
    )
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # 1. Actual vs Predicted
    ax1 = axes[0, 0]
    ax1.scatter(df['up_price'], pred_up, alpha=0.4, s=10, c=df['elapsed_sec'], cmap='viridis')
    ax1.plot([0, 1], [0, 1], 'r--', linewidth=2, label='Perfect prediction')
    ax1.set_xlabel('Actual UP Price')
    ax1.set_ylabel('Predicted UP Price')
    ax1.set_title(f'Actual vs Predicted (R²={r2_score(df["up_price"], pred_up):.3f})')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Signed drift vs UP price
    ax2 = axes[0, 1]
    scatter = ax2.scatter(df['signed_drift'] * 100, df['up_price'], 
                         c=df['elapsed_sec'], cmap='plasma', alpha=0.5, s=15)
    ax2.axhline(0.5, color='gray', linestyle='--', alpha=0.7)
    ax2.axvline(0, color='gray', linestyle='--', alpha=0.7)
    plt.colorbar(scatter, ax=ax2, label='Elapsed (sec)')
    ax2.set_xlabel('Signed Drift (%)')
    ax2.set_ylabel('UP Price')
    ax2.set_title('Drift vs UP Price (colored by time)')
    ax2.grid(True, alpha=0.3)
    
    # 3. Residuals by time
    ax3 = axes[1, 0]
    residuals = df['up_price'] - pred_up
    ax3.scatter(df['elapsed_sec'], residuals, alpha=0.4, s=10)
    ax3.axhline(0, color='red', linestyle='--')
    ax3.set_xlabel('Elapsed Seconds')
    ax3.set_ylabel('Residual (Actual - Predicted)')
    ax3.set_title('Residuals Over Time')
    ax3.grid(True, alpha=0.3)
    
    # 4. Residual histogram
    ax4 = axes[1, 1]
    ax4.hist(residuals, bins=50, edgecolor='black', alpha=0.7, color='steelblue')
    ax4.axvline(0, color='red', linestyle='--', linewidth=2)
    ax4.axvline(residuals.mean(), color='green', linestyle='--', linewidth=2, label=f'Mean: {residuals.mean():.4f}')
    ax4.set_xlabel('Residual')
    ax4.set_ylabel('Frequency')
    ax4.set_title(f'Residual Distribution (std={residuals.std():.4f})')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('bet_price_analysis_v2.png', dpi=150)
    print("\nPlot saved to: bet_price_analysis_v2.png")


def test_predictions(k, alpha, beta):
    """Show example predictions."""
    print("\n" + "=" * 60)
    print("EXAMPLE PREDICTIONS")
    print("=" * 60)
    
    test_cases = [
        (78000, 78100, 300, "Down 0.13%, 5 min elapsed"),
        (78000, 78100, 600, "Down 0.13%, 10 min elapsed"),
        (78000, 78100, 850, "Down 0.13%, 14 min elapsed"),
        (78200, 78100, 300, "Up 0.13%, 5 min elapsed"),
        (78200, 78100, 600, "Up 0.13%, 10 min elapsed"),
        (78200, 78100, 850, "Up 0.13%, 14 min elapsed"),
        (78050, 78100, 450, "Down 0.06%, 7.5 min"),
        (78150, 78100, 450, "Up 0.06%, 7.5 min"),
    ]
    
    print(f"\n{'Scenario':<35} {'UP Price':<12} {'DOWN Price':<12}")
    print("-" * 60)
    
    for btc_price, btc_open, elapsed, desc in test_cases:
        signed_drift = (btc_price - btc_open) / btc_open
        t = max((900 - elapsed) / 900, 0.001)
        time_scale = 1 + alpha * (1 - t) ** beta
        z = k * signed_drift * time_scale * 100
        up_price = 1 / (1 + np.exp(-z))
        down_price = 1 - up_price
        
        print(f"{desc:<35} ${up_price:.3f}        ${down_price:.3f}")


def main():
    print("=" * 60)
    print("POLYMARKET BET PRICE ANALYSIS v2")
    print("(Using SIGNED drift for correct price modeling)")
    print("=" * 60)
    
    filepath = r"C:\MyStuff\coding\turbindo-master\poly_sim_shell\sim_live_v2_detailed_2026-Feb-01_16-25-58.csv"
    df = load_and_clean_data(filepath)
    
    analyze_data(df)
    
    k, alpha, beta = fit_model(df)
    
    generate_formulas(k, alpha, beta)
    
    test_predictions(k, alpha, beta)
    
    try:
        plot_results(df, k, alpha, beta)
    except Exception as e:
        print(f"\nPlotting error: {e}")
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
