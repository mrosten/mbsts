"""
DARWIN — Self-Evolving AI Algorithm Agent
==========================================
Seed knowledge: "This is a 5-minute binary market (UP/DOWN)."
Everything else is discovered autonomously.

Modes:
  V1 — Blind Observer: observes, analyzes, logs, writes scripts. No trading signal.
  V2 — Sandboxed Experimenter: runs its own scanner code, tracks virtual P&L.

Architecture:
  - At end of each window, DarwinAgent.on_window_end() is called with full context.
  - Gemini reasons freely about what it has seen.
  - Gemini may write a new scanner function (V2) and/or run analysis scripts.
  - Results are stored in darwin/ directory and fed back next call.
  - In V2, Darwin's signal participates in weighted voting like any other scanner.
"""

import os
import json
import time
import subprocess
import threading
import traceback
from datetime import datetime
from pathlib import Path


# ===========================================================================
# DARWIN DIRECTORY STRUCTURE
# ===========================================================================
DARWIN_DIR = Path(__file__).parent / "darwin"
DARWIN_CURRENT_ALGO = DARWIN_DIR / "current_algo.py"
DARWIN_EXPERIMENT_LOG = DARWIN_DIR / "experiment_log.json"
DARWIN_OBSERVATIONS = DARWIN_DIR / "observations.md"
DARWIN_SCRATCH = DARWIN_DIR / "scratch"
DARWIN_BEST = DARWIN_DIR / "best_performers"


def _ensure_darwin_dirs():
    for d in [DARWIN_DIR, DARWIN_SCRATCH, DARWIN_BEST]:
        d.mkdir(parents=True, exist_ok=True)


# ===========================================================================
# SAFE SCRIPT RUNNER
# ===========================================================================

def run_darwin_script(script_path: str, timeout: int = 10) -> str:
    """Run a Darwin-authored script safely. Returns stdout or error string."""
    try:
        result = subprocess.run(
            ["python", script_path],
            capture_output=True, text=True,
            timeout=timeout,
            cwd=str(DARWIN_DIR)
        )
        output = result.stdout.strip() or ""
        if result.stderr.strip():
            output += f"\n[STDERR]: {result.stderr.strip()[:500]}"
        return output[:2000]  # Cap output length
    except subprocess.TimeoutExpired:
        return "[TIMEOUT: script exceeded time limit]"
    except Exception as e:
        return f"[RUN ERROR: {e}]"


# ===========================================================================
# SAFE ALGO RUNNER (V2)
# ===========================================================================

def run_darwin_algo(code: str, context: dict) -> str:
    """
    Safely execute Darwin's scanner function against the current context.
    Returns 'BET_UP', 'BET_DOWN', or 'HOLD'.
    Code must define: def scan(data) -> str
    """
    try:
        local_ns = {}
        exec(compile(code, "<darwin_algo>", "exec"), {}, local_ns)
        scan_fn = local_ns.get("scan")
        if not callable(scan_fn):
            return "HOLD"
        result = scan_fn(context)
        if result in ("BET_UP", "BET_DOWN", "HOLD"):
            return result
        return "HOLD"
    except Exception as e:
        return "HOLD"  # Always fail safe


# ===========================================================================
# EXPERIMENT LOG
# ===========================================================================

def load_experiment_log() -> list:
    if DARWIN_EXPERIMENT_LOG.exists():
        try:
            return json.loads(DARWIN_EXPERIMENT_LOG.read_text(encoding="utf-8"))
        except:
            return []
    return []


def save_experiment_log(log: list):
    try:
        DARWIN_EXPERIMENT_LOG.write_text(
            json.dumps(log[-200:], indent=2),  # Keep last 200 experiments
            encoding="utf-8"
        )
    except:
        pass


def load_current_algo() -> str:
    if DARWIN_CURRENT_ALGO.exists():
        return DARWIN_CURRENT_ALGO.read_text(encoding="utf-8")
    return ""


def save_current_algo(code: str):
    DARWIN_CURRENT_ALGO.write_text(code, encoding="utf-8")


# ===========================================================================
# DARWIN AGENT
# ===========================================================================

class DarwinAgent:
    """
    Self-evolving AI algorithm powered by Gemini.
    V1: observe + analyze + write scripts, no signal
    V2: like V1 + maintains and runs its own scanner code
    """

    MODE_V1 = "V1_OBSERVER"
    MODE_V2 = "V2_EXPERIMENTER"

    SEED_CONTEXT = (
        "You are DARWIN, an autonomous financial pattern discovery engine. "
        "You operate in a 5-minute binary prediction market (BTC UP or DOWN). "
        "Each 5-minute window closes and settles as either UP or DOWN from the starting price. "
        "You have no predefined strategy. You observe data, form hypotheses, write code, "
        "run analysis scripts, and evolve your own scanner algorithm window by window. "
        "Your goal: discover replicable patterns that predict the market direction. "
        "IMPORTANT: when writing analysis scripts (script_code), YOU MUST ONLY USE THE PYTHON STANDARD LIBRARY. "
        "Do NOT use external modules like 'pandas', 'numpy', 'scipy', etc. They are NOT installed."
    )

    def __init__(self, mode: str = MODE_V1, log_fn=None, app=None):
        _ensure_darwin_dirs()
        self.app = app
        self._mode = self.MODE_V1 # Initial default
        self.mode = mode # Use setter for mapping
        
        self.log_fn = log_fn or (lambda msg, **kw: print(f"[DARWIN] {msg}"))
        self.experiment_log = load_experiment_log()
        self.current_algo_code = load_current_algo()
        self.virtual_pnl = 0.0
        self.virtual_trades = 0
        self.virtual_wins = 0
        self._last_signal = "HOLD"
        self._last_signal_window = None
        self.fired = False  # Compatibility with BaseScanner
        self.triggered_signal = None
        self.triggered_signal = None
        self._genai = None # The module
        self._model = None # The model instance
        self._lock = threading.Lock()
        self._call_in_progress = False

        # Attempt to init Gemini client
        self._init_gemini()

        self.log_fn(
            f"[bold cyan]🧬 DARWIN {mode} initialized.[/] "
            f"Experiments on record: {len(self.experiment_log)}. "
            f"API: {'✅' if self._model else '❌ (check .env)'}",
            level="ADMIN"
        )

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, val):
        if val == "v2": self._mode = self.MODE_V2
        elif val == "v1": self._mode = self.MODE_V1
        else: self._mode = val

    def test_connection(self):
        """Test the Gemini API connection manually."""
        if not self._model:
            # Try to re-init if not initialized
            self._init_gemini()
        
        if not self._model:
            return "Error: Gemini client not initialized. Check your API key in .env"
            
        try:
            response = self._model.generate_content("Ping. Respond with 'PONG' if you are alive.")
            return f"Success! Gemini responded: {response.text.strip()}"
        except Exception as e:
            return f"Error during test: {str(e)}"

    def reset(self):
        self.fired = False
        self.triggered_signal = None

    def _init_gemini(self):
        try:
            import google.generativeai as genai
            import sys
            # Diagnostic: show which python we are using
            self.log_fn(f"[dim grey]DARWIN: Using Python: {sys.executable}[/]", level="ADMIN")
            
            # Use os.environ directly to ensure we get the latest loaded values
            api_key = os.environ.get("GEMINI_API_KEY", "")
            
            if not api_key:
                self.log_fn("[yellow]🧬 DARWIN: GEMINI_API_KEY not found in environment.[/]", level="ADMIN")
                return
            
            genai.configure(api_key=api_key)
            self._genai = genai
            self._model = genai.GenerativeModel("gemini-2.0-flash")
        except ImportError:
            self.log_fn("[yellow]DARWIN: google-generativeai not installed. Run: pip install google-generativeai[/]", level="ADMIN")
        except Exception as e:
            self.log_fn(f"[red]DARWIN: Gemini init failed: {e}[/]", level="ADMIN")

    # -----------------------------------------------------------------------
    # SIGNAL (V2 only) — called at window start
    # -----------------------------------------------------------------------

    def get_signal(self, context: dict) -> str:
        """Return BUY_UP / BUY_DOWN / WAIT for current context (V2 only)."""
        if self.mode != self.MODE_V2 or not self.current_algo_code:
            return "WAIT"
        signal = run_darwin_algo(self.current_algo_code, context)
        # Convert internal BET_UP -> BUY_UP for compatibility
        out = "WAIT"
        if signal == "BET_UP": out = "BUY_UP"
        elif signal == "BET_DOWN": out = "BUY_DOWN"
        
        self._last_signal = out
        self._last_signal_window = context.get("window_id")
        return out

    # -----------------------------------------------------------------------
    # RECORD OUTCOME (V2) — called at window end to track virtual P&L
    # -----------------------------------------------------------------------

    def record_outcome(self, window_id, actual_winner: str, our_signal: str, entry_price: float = 0.5):
        """Track Darwin's virtual P&L in V2 mode."""
        if self.mode != self.MODE_V2 or our_signal == "HOLD":
            return
        self.virtual_trades += 1
        # Simple binary: if signal matches winner, we win
        if our_signal == f"BET_{actual_winner}":
            pnl = round((1.0 - entry_price) * 10, 2)
            self.virtual_wins += 1
        else:
            pnl = -round(entry_price * 10, 2)
        self.virtual_pnl = round(self.virtual_pnl + pnl, 2)
        win_rate = round(self.virtual_wins / self.virtual_trades * 100, 1) if self.virtual_trades else 0
        self.log_fn(
            f"[cyan]🧬 DARWIN V-PnL:[/] {pnl:+.2f} | "
            f"Total: {self.virtual_pnl:+.2f} | "
            f"Win rate: {win_rate}% ({self.virtual_wins}/{self.virtual_trades})",
            level="ADMIN"
        )

    # -----------------------------------------------------------------------
    # MAIN HOOK — called at window end
    # -----------------------------------------------------------------------

    def on_window_end(self, context: dict):
        """
        Called at the end of each window. Packages context and calls Gemini
        in a background thread (so it doesn't block settlement).
        context keys expected:
            window_id, winner (UP/DOWN), pnl, invested, scanners_fired,
            btc_open, btc_close, btc_move_pct, atr, trend_1h, odds_score,
            up_price_open, up_price_close, tick_history (list of floats),
            tilt_next (direction/magnitude from NEXT preview)
        """
        if self._call_in_progress:
            self.log_fn("[dim]🧬 DARWIN: Skipping (previous call still in progress)[/]", level="SYS")
            return
        if not self._model:
            self.log_fn("[dim]🧬 DARWIN: No Gemini client — skipping[/]", level="SYS")
            return

        threading.Thread(
            target=self._run_gemini_cycle,
            args=(context,),
            daemon=True
        ).start()

    def _run_gemini_cycle(self, context: dict):
        with self._lock:
            self._call_in_progress = True
            try:
                self._gemini_cycle(context)
            except Exception as e:
                self.log_fn(f"[red]🧬 DARWIN error: {e}[/]", level="ERROR")
            finally:
                self._call_in_progress = False

    def _gemini_cycle(self, context: dict):
        t0 = time.time()

        # Record outcome for V2 (what was our last signal vs what actually happened)
        if self.mode == self.MODE_V2:
            self.record_outcome(
                context.get("window_id"),
                context.get("winner", ""),
                self._last_signal,
                context.get("up_price_open", 0.5)
            )

        # Build the last N experiment summaries for memory
        recent = self.experiment_log[-10:]
        memory_text = "\n".join([
            f"  Window {e.get('window_id','?')}: hypothesis='{e.get('hypothesis','?')}' "
            f"signal={e.get('signal','?')} winner={e.get('winner','?')} "
            f"outcome={e.get('outcome','?')}"
            for e in recent
        ]) or "  (no prior experiments)"

        # Current algo code summary
        algo_text = self.current_algo_code[:800] if self.current_algo_code else "(none yet)"

        # Build prompt
        v2_instruction = ""
        if self.mode == self.MODE_V2:
            v2_instruction = f"""
CURRENT SCANNER CODE (your active algorithm):
```python
{algo_text}
```

Your virtual P&L: {self.virtual_pnl:+.2f} across {self.virtual_trades} trades.

TASK (in addition to observation):
- If the current algorithm should be changed, provide a new `scan(data)` function in the field "new_algo_code".
- The function receives a dict called `data` with keys: btc_open, btc_close, btc_move_pct, atr, trend_1h, odds_score, up_price_open, tilt_dir, tilt_mag
- It must return exactly one of: "BET_UP", "BET_DOWN", "HOLD"
- Keep it simple and testable.
"""

        prompt = f"""{self.SEED_CONTEXT}

=== CURRENT WINDOW RESULT ===
Window ID: {context.get('window_id', '?')}
Winner: {context.get('winner', '?')}
BTC Move: {context.get('btc_move_pct', 0):+.3f}%
ATR: {context.get('atr', 0):.1f}
1H Trend: {context.get('trend_1h', '?')}
Odds Score: {context.get('odds_score', 0):+.1f}¢
UP Open: {context.get('up_price_open', 0)*100:.1f}¢ → Close: {context.get('up_price_close', 0)*100:.1f}¢
Next Window Tilt: {context.get('tilt_next', 'None')}
Scanners that fired: {context.get('scanners_fired', [])}
PnL this window: ${context.get('pnl', 0):+.2f}

=== YOUR MEMORY (last 10 experiments) ===
{memory_text}

{v2_instruction}

=== YOUR TASK ===
Reason freely. Look for patterns. Form a hypothesis. 
Optionally write a short Python analysis script (saved and run immediately).
Summarize your observation in 1-3 sentences.

Respond ONLY with valid JSON (no markdown fences):
{{
  "hypothesis": "short string",
  "observation": "1-3 sentence observation",
  "confidence": 0.0-1.0,
  "script_filename": "optional_script.py (or null)",
  "script_code": "optional python code (or null)",
  "new_algo_code": "optional def scan(data): ... (or null)",
  "notes": "optional notes for future self"
}}
IMPORTANT: Use the JSON literal null (no quotes) for optional fields if not used. Do not use the string "null".
"""

        try:
            if not self._model:
                self._init_gemini()
            
            if not self._model:
                self.log_fn("[yellow]🧬 DARWIN: Cannot observe, Gemini not initialized.[/]", level="SYS")
                return

            response = self._model.generate_content(
                prompt,
                request_options={"timeout": 60}
            )
            raw = response.text.strip()

            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            self.log_fn(f"[yellow]🧬 DARWIN: JSON parse failed ({e})[/]", level="SYS")
            return
        except Exception as e:
            self.log_fn(f"[red]🧬 DARWIN: Gemini call failed: {e}[/]", level="ERROR")
            return

        elapsed_api = round(time.time() - t0, 1)

        # Log observation
        hyp = parsed.get("hypothesis", "")
        obs = parsed.get("observation", "")
        conf = parsed.get("confidence", 0)
        self.log_fn(
            f"[bold cyan]🧬 DARWIN[/] ({elapsed_api}s) | "
            f"[italic]{hyp}[/] | conf={conf:.0%}",
            level="ADMIN"
        )
        if obs:
            self.log_fn(f"[dim cyan]  └ {obs}[/]", level="ADMIN")

        # Run analysis script if requested
        script_output = ""
        script_fn = parsed.get("script_filename")
        script_code = parsed.get("script_code")
        
        # [FIX] Guard against literal "null" strings or None from the model
        if script_fn and script_code and str(script_fn).lower() != "null" and str(script_code).lower() != "null":
            script_path = DARWIN_SCRATCH / script_fn
            script_path.write_text(script_code, encoding="utf-8")
            script_output = run_darwin_script(str(script_path))
            if script_output:
                self.log_fn(f"[dim cyan]  └ Script [{script_fn}]: {script_output[:200]}[/]", level="SYS")

        # Update current algo (V2)
        new_code = parsed.get("new_algo_code")
        if self.mode == self.MODE_V2 and new_code and "def scan(" in new_code:
            save_current_algo(new_code)
            self.current_algo_code = new_code
            self.log_fn(f"[bold cyan]🧬 DARWIN: Algorithm updated[/]", level="ADMIN")

        # Log the experiment
        experiment = {
            "window_id": context.get("window_id"),
            "timestamp": datetime.now().isoformat(),
            "winner": context.get("winner"),
            "hypothesis": hyp,
            "observation": obs,
            "confidence": conf,
            "signal": self._last_signal if self.mode == self.MODE_V2 else "N/A",
            "outcome": "WIN" if (self._last_signal == f"BET_{context.get('winner')}") else "LOSS" if self._last_signal != "HOLD" else "HOLD",
            "script_run": script_fn,
            "script_output": script_output[:500] if script_output else None,
            "algo_updated": bool(new_code),
            "api_latency_s": elapsed_api,
            "notes": parsed.get("notes", "")
        }
        self.experiment_log.append(experiment)
        save_experiment_log(self.experiment_log)

        # [NEW] SQLite Darwin Vault Hook (Prop 3)
        if self.app and getattr(self.app, "db_log_darwin", False) and getattr(self.app, "history", None):
            try:
                self.app.history.record_darwin_vault(experiment)
            except:
                pass

        # Append to observations.md
        try:
            with open(DARWIN_OBSERVATIONS, "a", encoding="utf-8") as f:
                f.write(f"\n## Window {context.get('window_id')} — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
                f.write(f"**Winner:** {context.get('winner')} | **Conf:** {conf:.0%}\n")
                f.write(f"**Hypothesis:** {hyp}\n")
                f.write(f"**Observation:** {obs}\n")
                if parsed.get("notes"):
                    f.write(f"**Notes:** {parsed['notes']}\n")
                if script_output:
                    f.write(f"**Script output:** `{script_output[:300]}`\n")
        except:
            pass
    def on_chat_submit(self, message: str) -> str:
        """Handle a direct user chat message. Returns AI response string."""
        if not self._model:
            return "Error: Darwin is not connected (no API key or model)."

        # Context for the chat: recent observations and experiments
        recent_obs = ""
        if DARWIN_OBSERVATIONS.exists():
            try:
                # Get last 1000 chars of observations for context
                recent_obs = DARWIN_OBSERVATIONS.read_text(encoding="utf-8")[-1000:]
            except: pass

        chat_prompt = f"""{self.SEED_CONTEXT}
        
        You are talking to the USER in a playful, helpful way about your observations and the algorithms you are developing.
        Stay in character as DARWIN. Be concise but insightful.
        
        RECENT OBSERVATIONS CONTEXT:
        {recent_obs}
        
        USER MESSAGE: "{message}"
        
        YOUR RESPONSE (playful/insightful/concise):"""

        try:
            # print(f"[DARWIN] Sending chat prompt to Gemini...")
            # Use a timeout to prevent indefinite hanging
            response = self._model.generate_content(
                chat_prompt,
                request_options={"timeout": 30}
            )
            # print(f"[DARWIN] Gemini response received.")
            return response.text.strip()
        except Exception as e:
            # print(f"[DARWIN] Chat error: {e}")
            return f"Error: {str(e)}"
