#!/usr/bin/env python3
"""
Standalone PBN Analysis Test
Tests the PBN analysis logic without full project dependencies
"""

def run_pbn_analysis(btc_price, btc_open, up_ask, down_ask, atr_5m, trend_1h, rsi_1m, odds_score):
    """
    Simulate the PBN analysis logic from MomentumScanner
    """
    print(f"\n🧠 Running PBN Analysis...")
    print(f"  BTC: ${btc_price} (Open: ${btc_open}) | Change: ${btc_price - btc_open:+.0f}")
    print(f"  Prices: UP {up_ask*100:.1f}¢ / DN {down_ask*100:.1f}¢ | Spread: {(up_ask - down_ask)*100:.1f}¢")
    print(f"  ATR: {atr_5m:.1f} | Trend: {trend_1h} | RSI: {rsi_1m:.0f} | Odds: {odds_score:+.1f}¢")
    
    factors = []
    up_score = 0
    down_score = 0
    
    # 1. Trend Analysis
    if trend_1h in ["S-UP", "M-UP", "W-UP"]:
        up_score += 2
        factors.append(f"Trend 1H: BULLISH ({trend_1h}) [+2]")
    elif trend_1h in ["S-DOWN", "M-DOWN", "W-DOWN"]:
        down_score += 2
        factors.append(f"Trend 1H: BEARISH ({trend_1h}) [+2]")
    else:
        factors.append(f"Trend 1H: NEUTRAL ({trend_1h}) [0]")
    
    # 2. BTC Movement Analysis
    btc_diff = btc_price - btc_open
    if abs(btc_diff) > 50:
        if btc_diff > 0:
            up_score += 1
            factors.append(f"BTC Move: +${btc_diff:.0f} [+1]")
        else:
            down_score += 1
            factors.append(f"BTC Move: ${btc_diff:.0f} [+1]")
    else:
        factors.append(f"BTC Move: ${btc_diff:.0f} [0]")
    
    # 3. RSI Analysis
    if rsi_1m > 70:
        down_score += 1
        factors.append(f"RSI 1m: {rsi_1m:.0f} (Overbought) [+1]")
    elif rsi_1m < 30:
        up_score += 1
        factors.append(f"RSI 1m: {rsi_1m:.0f} (Oversold) [+1]")
    else:
        factors.append(f"RSI 1m: {rsi_1m:.0f} (Neutral) [0]")
    
    # 4. Polymarket Odds Analysis
    if abs(odds_score) > 5:
        if odds_score > 0:
            up_score += 1
            factors.append(f"Odds Score: +{odds_score:.1f}¢ (UP favored) [+1]")
        else:
            down_score += 1
            factors.append(f"Odds Score: {odds_score:.1f}¢ (DN favored) [+1]")
    else:
        factors.append(f"Odds Score: {odds_score:.1f}¢ (Balanced) [0]")
    
    # 5. Price Imbalance Analysis
    price_imbalance = (up_ask - down_ask) * 100
    if abs(price_imbalance) > 2:
        if price_imbalance > 0:
            down_score += 1
            factors.append(f"Ask Spread: +{price_imbalance:.1f}¢ (UP premium) [+1 DN]")
        else:
            up_score += 1
            factors.append(f"Ask Spread: +{price_imbalance:.1f}¢ (DN premium) [+1 UP]")
    else:
        factors.append(f"Ask Spread: {price_imbalance:.1f}¢ (Balanced) [0]")
    
    # 6. ATR Tier Analysis
    atr_low = 30
    atr_high = 120
    tier = "CHAOS" if atr_5m >= atr_high else "STABLE" if atr_5m <= atr_low else "NEUTRAL"
    tier_color = "RED" if tier == "CHAOS" else "GREEN" if tier == "STABLE" else "YELLOW"
    offset = 25 if tier == "CHAOS" else (-5 if tier == "STABLE" else 0)
    factors.append(f"ATR Tier: {tier} (ATR={atr_5m:.1f}) [Offset: {offset:+}¢]")
    
    # 7. Volatility Analysis
    btc_range = 200  # Simulated
    if btc_range > 100:
        factors.append(f"Volatility: HIGH (${btc_range:.0f} range) [Caution]")
    elif btc_range > 50:
        factors.append(f"Volatility: MODERATE (${btc_range:.0f} range)")
    else:
        factors.append(f"Volatility: LOW (${btc_range:.0f} range)")
    
    # Calculate final recommendation
    net_score = up_score - down_score
    if net_score > 0:
        side = "UP"
        confidence = "STRONG" if net_score >= 3 else "MODERATE" if net_score >= 2 else "WEAK"
    elif net_score < 0:
        side = "DOWN"
        confidence = "STRONG" if net_score <= -3 else "MODERATE" if net_score <= -2 else "WEAK"
    else:
        side = None
        confidence = "NONE"
        
    if side:
        reason = f"PBN Analysis: {confidence} {side} (Score: {net_score:+d})"
    else:
        reason = f"PBN Analysis: INDECISIVE (Score: {net_score:+d}) | Completely Tied"
    
    # Display analysis
    print(f"\n🧠 PBN MULTI-FACTOR ANALYSIS:")
    print(f"  Decision: {side or 'SKIP'} | Confidence: {confidence} | Score: {net_score:+d}")
    print(f"  UP Score: {up_score} | DOWN Score: {down_score}")
    print(f"  Factors:")
    for factor in factors:
        print(f"    • {factor}")
    print(f"  Final Reason: {reason}")
    
    # Fallback logic
    if not side:
        fallback_side = "UP" if up_ask > down_ask else "DOWN"
        fallback_reason = f"PBN Analysis: INDECISIVE - picked {fallback_side} (higher price: UP={up_ask*100:.1f}¢, DN={down_ask*100:.1f}¢)"
        print(f"\n🔄 FALLBACK: {fallback_reason}")
        return fallback_side, fallback_reason
    
    return side, reason

def test_scenarios():
    """Test various PBN scenarios"""
    print("=" * 80)
    print("PBN ANALYSIS STANDALONE TEST")
    print("=" * 80)
    
    test_cases = [
        {
            "name": "🚀 STRONG BULLISH - Perfect Storm",
            "btc_price": 73200, "btc_open": 72900, "up_ask": 0.55, "down_ask": 0.45,
            "atr_5m": 45.0, "trend_1h": "S-UP", "rsi_1m": 25, "odds_score": 10.0
        },
        {
            "name": "📉 STRONG BEARISH - Perfect Storm", 
            "btc_price": 72600, "btc_open": 72900, "up_ask": 0.45, "down_ask": 0.55,
            "atr_5m": 55.0, "trend_1h": "S-DOWN", "rsi_1m": 75, "odds_score": -10.0
        },
        {
            "name": "⚖️ INDECISIVE - Coin Flip",
            "btc_price": 72950, "btc_open": 72900, "up_ask": 0.505, "down_ask": 0.495,
            "atr_5m": 35.0, "trend_1h": "NEUTRAL", "rsi_1m": 50, "odds_score": 1.0
        },
        {
            "name": "🌪️ HIGH VOLATILITY - Chaos Market",
            "btc_price": 73100, "btc_open": 72900, "up_ask": 0.54, "down_ask": 0.46,
            "atr_5m": 125.0, "trend_1h": "M-UP", "rsi_1m": 40, "odds_score": 5.0
        },
        {
            "name": "😴 LOW VOLATILITY - Stable Market",
            "btc_price": 72980, "btc_open": 72900, "up_ask": 0.502, "down_ask": 0.498,
            "atr_5m": 15.0, "trend_1h": "W-UP", "rsi_1m": 45, "odds_score": 2.0
        },
        {
            "name": "🔄 MIXED SIGNALS - Conflicting Data",
            "btc_price": 72700, "btc_open": 72900, "up_ask": 0.53, "down_ask": 0.47,
            "atr_5m": 60.0, "trend_1h": "S-DOWN", "rsi_1m": 20, "odds_score": 8.0
        }
    ]
    
    results = []
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"TEST {i}: {test['name']}")
        print(f"{'='*80}")
        
        side, reason = run_pbn_analysis(
            test['btc_price'], test['btc_open'], test['up_ask'], test['down_ask'],
            test['atr_5m'], test['trend_1h'], test['rsi_1m'], test['odds_score']
        )
        
        results.append({
            "test": test['name'],
            "side": side,
            "reason": reason
        })
        
        print(f"\n📤 EXECUTION DECISION: {side} - {reason}")
    
    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    
    for result in results:
        print(f"{result['test']:<30} → {result['side']:<5} | {result['reason']}")

if __name__ == "__main__":
    test_scenarios()
    print(f"\n✅ Test completed successfully!")
