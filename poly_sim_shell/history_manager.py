import sqlite3
import os
import threading
import logging
from datetime import datetime

logger = logging.getLogger("poly_history")

class HistoryManager:
    """
    Manages a shared SQLite database for historical market data and bot performance.
    Supports 5 distinct logging modes: Windows, Alpha, Darwin, Ticks, and Context.
    """
    def __init__(self, db_path=None):
        if db_path is None:
            # Default to ../poly_history.db relative to typical variant script location
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base_dir, "poly_history.db")
        
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        """Initialize all tables for the 5 selected propositions."""
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                
                # Table 1: windows (Unified Event Log)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS windows (
                        wid TEXT PRIMARY KEY,
                        timestamp TEXT,
                        winner TEXT,
                        btc_open REAL,
                        btc_close REAL,
                        btc_move REAL,
                        atr REAL,
                        pnl REAL,
                        variant TEXT
                    )
                """)
                
                # Table 2: variant_results (Alpha Ledger)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS variant_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        wid TEXT,
                        variant_name TEXT,
                        signal TEXT,
                        pnl REAL,
                        outcome TEXT,
                        FOREIGN KEY(wid) REFERENCES windows(wid)
                    )
                """)

                # Table 3: Darwin Vault (Evolutions & Experiments)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS darwin_evolutions (
                        version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT,
                        hypothesis TEXT,
                        code_snippet TEXT
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS darwin_experiments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        wid TEXT,
                        version_id INTEGER,
                        prediction TEXT,
                        actual TEXT,
                        confidence REAL,
                        FOREIGN KEY(wid) REFERENCES windows(wid),
                        FOREIGN KEY(version_id) REFERENCES darwin_evolutions(version_id)
                    )
                """)

                # Table 4: ticks (Granular Archive)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ticks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        wid TEXT,
                        elapsed_s INTEGER,
                        btc_price REAL,
                        up_price REAL,
                        down_price REAL,
                        depth_imb REAL,
                        side_hint TEXT,
                        FOREIGN KEY(wid) REFERENCES windows(wid)
                    )
                """)

                # Table 5: market_context (Metadata Graph)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS market_context (
                        wid TEXT PRIMARY KEY,
                        rsi REAL,
                        atr REAL,
                        trend_1h TEXT,
                        volatility_score REAL,
                        odds_spread REAL,
                        FOREIGN KEY(wid) REFERENCES windows(wid)
                    )
                """)
                
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to initialize SQLite DB: {e}")
            finally:
                conn.close()

    # --- Record Methods ---

    def record_window(self, data: dict):
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO windows 
                    (wid, timestamp, winner, btc_open, btc_close, btc_move, atr, pnl, variant)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get("wid"),
                    data.get("timestamp", datetime.now().isoformat()),
                    data.get("winner"),
                    data.get("btc_open"),
                    data.get("btc_close"),
                    data.get("btc_move"),
                    data.get("atr"),
                    data.get("pnl"),
                    data.get("variant", "vortex_pulse")
                ))
                conn.commit()
            except Exception as e:
                logger.error(f"Error recording window to SQLite: {e}")
            finally:
                conn.close()

    def record_alpha_trade(self, data: dict):
        """Alpha Ledger (Prop 2)."""
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO variant_results (wid, variant_name, signal, pnl, outcome)
                    VALUES (?, ?, ?, ?, ?)
                """, (data.get("slug"), data.get("algorithm"), data.get("side"), data.get("pnl", 0.0), data.get("outcome", "HOLD")))
                conn.commit()
            except Exception as e:
                logger.error(f"Error recording Alpha trade: {e}")
            finally:
                conn.close()

    def record_darwin_vault(self, experiment: dict):
        """Darwin Analytics Vault (Prop 3). Unified entry point."""
        hyp = experiment.get("hypothesis", "")
        code = experiment.get("new_algo_code", "")
        wid = experiment.get("window_id")
        
        v_id = -1
        if code and code != "null":
            v_id = self.record_darwin_evolution(hyp, code)
        
        data = {
            "wid": wid,
            "version_id": v_id if v_id != -1 else None,
            "prediction": experiment.get("signal"),
            "actual": experiment.get("winner"),
            "confidence": experiment.get("confidence")
        }
        self.record_darwin_experiment(data)

    def record_darwin_evolution(self, hypothesis: str, code: str) -> int:
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO variant_results (wid, variant_name, signal, pnl, outcome)
                    VALUES (?, ?, ?, ?, ?)
                """, (data.get("wid"), data.get("variant_name"), data.get("signal"), data.get("pnl"), data.get("outcome")))
                conn.commit()
            except Exception as e:
                logger.error(f"Error recording variant result: {e}")
            finally:
                conn.close()

    def record_darwin_evolution(self, hypothesis: str, code: str) -> int:
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO darwin_evolutions (timestamp, hypothesis, code_snippet) VALUES (?, ?, ?)",
                               (datetime.now().isoformat(), hypothesis, code))
                conn.commit()
                # Return the version_id of the new evolution
                cursor.execute("SELECT last_insert_rowid()")
                return cursor.fetchone()[0]
            except Exception as e:
                logger.error(f"Error recording Darwin evolution: {e}")
                return -1
            finally:
                conn.close()

    def record_darwin_experiment(self, data: dict):
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO darwin_experiments (wid, version_id, prediction, actual, confidence)
                    VALUES (?, ?, ?, ?, ?)
                """, (data.get("wid"), data.get("version_id"), data.get("prediction"), data.get("actual"), data.get("confidence")))
                conn.commit()
            except Exception as e:
                logger.error(f"Error recording Darwin experiment: {e}")
            finally:
                conn.close()

    def record_tick(self, ts: int, btc_price: float, up_price: float, down_price: float, up_bid: float, down_bid: float, wid: str = None):
        """Granular Tick Archive (Prop 4)."""
        with self._lock:
            conn = self._get_conn()
            try:
                # Calculate depth imbalance
                depth_imb = (up_bid - down_bid) if (up_bid + down_bid) > 0 else 0
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO ticks (wid, elapsed_s, btc_price, up_price, down_price, depth_imb, side_hint)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (wid, ts, btc_price, up_price, down_price, depth_imb, None))
                conn.commit()
            except Exception as e:
                logger.debug(f"Error recording tick: {e}")
            finally:
                conn.close()

    def record_context(self, data: dict):
        """Contextual Metadata Graph (Prop 5)."""
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO market_context (wid, rsi, atr, trend_1h, volatility_score, odds_spread)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (data.get("slug"), data.get("rsi"), data.get("atr"), data.get("trend"), 
                      data.get("vol_up", 0) - data.get("vol_dn", 0), data.get("odds_entry")))
                conn.commit()
            except Exception as e:
                logger.error(f"Error recording market context: {e}")
            finally:
                conn.close()
