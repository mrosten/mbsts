# PROPOSAL: Darwin UI Evolution (v6.0 Concept)

This document outlines the proposed UI enhancements to provide more intuitive and real-time feedback for the **Darwin System Orchestrator** in Vortex Pulse.

## 1. Darwin HUD (Heads-Up Display)
**Goal**: Make Darwin's internal reasoning visible to the user without checking log files.
- **Implementation**: A semi-transparent overlay in the main UI that displays:
    - **Current Hypothesis**: Short-term market prediction logic.
    - **Regime Classification**: (e.g., "Chaos", "Stable", "Trend-Down").
    - **Confidence Score**: A 0-100% meter.
- **Visual Style**: Cyan-tinted glassmorphism with dynamic text updates.

## 2. AI-Management Indicators
**Goal**: Clearly distinguish between manual settings and those currently controlled by the AI.
- **Visual Brackets**: When Darwin overrides a setting (e.g., `Bet $` or `TP%`), the input box should glow **Cyan** and display a `🧬` icon.
- **Darwin Override Toggle**: A small master switch next to the Darwin label to "Pause AI Control" while keeping the bot running.

## 3. Discovery & Analysis Badges
**Goal**: Show the user which parts of the system are under active AI investigation.
- **Logic Pull Badge**: When Darwin uses the *Source Code Sniffer* to analyze a scanner, that scanner's label in the grid will receive a temporary `🧬` badge.
- **Regime Fit Indicator**: A small dot (Green/Yellow/Red) next to each scanner showing how well Darwin thinks its logic currently fits the market regime.

## 4. Darwin Vault Explorer (Analytics Page)
**Goal**: Provide a high-level view of Darwin's learning trajectory using the SQLite data.
- **Learning Curve**: A graph showing "Hypothesis Accuracy" over the last 100 windows.
- **Action Log**: A filterable table of every `system_action` Darwin has taken and its resultant PnL impact.

## 5. "Darwin Pulse" Animation
**Goal**: Create a tactile sense of "Thinking".
- **Interaction**: The Darwin label should pulse slowly during the Gemini API call and flash briefly when an action is applied through the Command Bridge.

---
**Status**: Proposal for Review  
**Author**: AI Assistant (Antigravity)  
**Version**: 1.0
