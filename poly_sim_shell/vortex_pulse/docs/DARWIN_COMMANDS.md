# 🧬 Darwin AI — Command & Interaction Guide

Darwin is a self-evolving AI agent that can analyze market context and take direct system actions. This guide outlines how you can interact with Darwin via the chat interface to orchestrate your trading strategy.

## 🛠️ Direct System Control
Darwin can modify your risk and scanner settings on the fly. You can give these commands in natural language:

### Scanner Management
- **"Darwin, turn off all scanners except MOM and MM2."**
- **"Enable the RSI and Nitro scanners."**
- **"Focus only on trend-following algorithms for the next hour."**

### Risk & Profit Parameters
- **"Set my bet size to $10.00."**
- **"Tighten our Stop Loss to 25%."**
- **"If BTC volatility is high (> $100), cut our total risk cap in half."**

### Scanner Tuning
- **"Increase the Momentum threshold to 0.70."**
- **"Darwin, lengthen the RSI lookback period to 20 for more stability."**

---

## 🧠 Strategic Auditing & Reasoning
Darwin has the ability to "see" the system code and explain market performance.

### Performance Analysis
- **"Why did we lose the last window? Audit our entry price vs. settlement delta."**
- **"Find our weakest scanner over the last 10 windows and suggest a replacement."**

### Code Inspection
- **"Show me the RSI scanner code and tell me if it's too sensitive for this market."**
- **"Analyze the 'BullFlag' logic and compare it to our recent losses."**
(Darwin uses its internal `SourceCodeSniffer` to read the actual Python files).

---

## 🧬 Evolution & Experimentation
For advanced users, Darwin can write its own code to discover new strategies.

- **"Darwin, evolve a new 'Nitro' variant focused on 15-second pre-window velocity."**
- **"Write and run a script to simulate how MM2 would have performed if we used a 5-period ATR."**
- **"Create a 'Whale Shield' logic that monitors Binance depth changes and apply it to our virtual signal."**

---

## 🔝 Pro-Level Commands
- **"Darwin, assume full control: optimize my portfolio weights based on the last 24H win rates."**
- **"Analyze the failure points of the Staircase scanner and write a patch to fix it in `current_algo.py`."**

---

> [!TIP]
> **Playful Character**: Darwin is designed to be an insightful, playful collaborator. It often speaks in "biological" or "evolutionary" terms—it's not just a bot, it's a digital ecosystem!
