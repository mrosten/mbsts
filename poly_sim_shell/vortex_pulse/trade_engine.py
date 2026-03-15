import time
import asyncio
import threading
import os
import concurrent.futures
from datetime import datetime, timezone

# Handle imports for both package and direct execution
try:
    from .config import TradingConfig
    from .market import calculate_rsi, calculate_bb, calculate_atr
except ImportError:
    # Running directly from vortex_pulse directory
    from config import TradingConfig
    from market import calculate_rsi, calculate_bb, calculate_atr


class TradeEngineMixin:
    """
    Mixin class containing all trade execution, settlement, TP/SL,
    pre-buy, and timer logic for PulseApp.
    
    All methods reference `self` which is the PulseApp instance at runtime.
    """
    
    def safe_call(self, func, *args, **kwargs):
        """Utility for background threads to safely update the UI without crashing during shutdown."""
        try:
            if not getattr(self, "app_active", False): return
            self.call_from_thread(func, *args, **kwargs)
        except RuntimeError:
            pass # App is shutting down

    def _handle_successful_buy(self, name, side, cost, act_shares, act_price, is_live):
        ticket_id = f"{name}_{time.time()}"
        target_tp = self.committed_tp
        target_sl = self.committed_sl
        
        # Check if algorithm has custom TP/SL
        sc = self.scanners.get(name)
        if sc:
            if getattr(sc, "custom_tp", None): target_tp = float(sc.custom_tp) / 100.0
            if getattr(sc, "custom_sl", None): target_sl = float(sc.custom_sl) / 100.0

        limit_order_id = None
        try:
            use_tranche = self.query_one("#cb_tranche").value
        except:
            use_tranche = False
            
        if use_tranche and is_live and cost >= TradingConfig.MIN_LIMIT_ORDER_SIZE:
             # Fire Limit Order!
             tid = self.market_data["up_id" if side=="UP" else "down_id"]
             limit_price = target_tp
             placed, order_or_err = self.trade_executor.live.place_limit_sell(side, tid, act_shares, limit_price)
             if placed:
                 limit_order_id = order_or_err
                 self.log_msg(f"[bold cyan]Tranche Limit Order Placed:[/bold cyan] {act_shares:.2f} {side} @ {limit_price*100:.1f}¢ (ID: {limit_order_id[-6:]})", level="TRADE")
             else:
                 self.log_msg(f"[bold yellow]Limit Order Failed:[/bold yellow] {order_or_err}", level="ERROR")
        elif use_tranche and is_live and cost < TradingConfig.MIN_LIMIT_ORDER_SIZE:
             self.log_msg(f"[yellow]Tranche too small (${cost:.2f} < $5.50) for limit order. Using global monitor.[/yellow]", level="SCAN")
             
        self.risk_manager.register_bet(cost)
        slug = self.market_data.get("slug", "N/A")
        self.window_bets[ticket_id] = {"side":side,"entry":act_price,"cost":cost,"algorithm":name, "shares":act_shares, "limit_order_id":limit_order_id, "target_tp":target_tp, "target_sl":target_sl, "slug":slug, "is_live":is_live}
        self.last_execution_time = time.time()
        if name in self.portfolios:
            self.portfolios[name].record_trade(ticket_id, side, act_price, cost, act_shares, target_tp=target_tp, target_sl=target_sl, contract_price=act_price)
            if limit_order_id:
                self.portfolios[name].ledger[ticket_id]["limit_order_id"] = limit_order_id

    def apply_global_skeptic_filter(self, side, price, name="Scanner"):
        """
        Calculates the effective minimum entry price based on global skepticism premiums.
        Returns (True, None, 0.0) if price is acceptable with no penalty,
               (True, None, penalty_pct) if price is acceptable with penalty,
               (False, reason_string, 0.0) if price is blocked.
        """
        try:
            base_min = float(self.query_one("#inp_min_price").value)
            max_pr = float(self.query_one("#inp_max_price").value)
        except:
            base_min, max_pr = 0.55, 0.80

        # 1. Check Max Price first (Hard Bound, no penalties apply)
        # Moshe-90 is explicitly exempt in the main loop call, but we handle it here for safety
        if price > max_pr and "Moshe" not in name:
            return False, f"Price {price*100:.1f}c > Max {max_pr*100:.1f}c", 0.0

        effective_min = base_min
        penalties = []
        total_penalty_pct = 0.0

        # 2. Odds Conflict Penalty
        # Odds favors UP if > 5.0, favors DOWN if < -5.0
        odds = self.market_data.get("odds_score", 0)
        try:
            odds_skeptic = float(self.query_one("#inp_skeptic_odds").value)
        except:
            odds_skeptic = getattr(self, "global_skeptic_odds", 0.05)
        
        if (side == "UP" and odds < -5.0) or (side == "DOWN" and odds > 5.0):
            effective_min += odds_skeptic
            penalties.append(f"Odds Conflict (+{odds_skeptic*100:.0f}c)")
            total_penalty_pct += getattr(self, "penalty_percentage", 0.10)

        # 3. Guess Conflict Penalty
        # Net Guess Score >= 2 is UP, <= -2 is DOWN, others are Neutral/Chop
        guess_score = self.market_data.get("net_guess_score", 0)
        try:
            guess_skeptic = float(self.query_one("#inp_skeptic_guess").value)
        except:
            guess_skeptic = getattr(self, "global_skeptic_guess", 0.03)
        
        # Conflict if Guess is strictly Neutral or Opposite
        guess_side = "UP" if guess_score >= 2 else ("DOWN" if guess_score <= -2 else "NEUTRAL")
        if guess_side == "NEUTRAL" or guess_side != side:
            effective_min += guess_skeptic
            penalties.append(f"Guess Conflict (+{guess_skeptic*100:.0f}c)")
            total_penalty_pct += getattr(self, "penalty_percentage", 0.10)

        if price < effective_min:
            reason = f"{price*100:.1f}c < {effective_min*100:.1f}c"
            if penalties:
                reason += f" ({', '.join(penalties)})"
            return False, reason, 0.0

        return True, None, total_penalty_pct

    def _refant_finalize_bet(self, name, sd, bs, pr, res, info=None):
        """
        Unified method to apply skepticism and conviction scaling.
        Returns (ok, finalized_bs, skeptic_penalty_pct).
        """
        ok_filter, filter_reason, skepticism_penalty = self.apply_global_skeptic_filter(sd, pr, name=name)
        if not ok_filter:
            return False, bs, skepticism_penalty

        final_bs = bs
        # 1. Skepticism Penalty (Tax on bet size, not a filter block)
        if skepticism_penalty > 0:
            original_bs = final_bs
            final_bs *= (1.0 - skepticism_penalty)
            log_tag = "skeptic_logged"
            if info is not None:
                if not info.get(log_tag):
                    self.log_msg(f"SKEPTIC: {skepticism_penalty*100:.0f}% Cut | Target: {name}", level="SYS")
                    info[log_tag] = True
            else:
                self.log_msg(f"SKEPTIC: {skepticism_penalty*100:.0f}% Cut | Target: {name} (${original_bs:.2f} -> ${final_bs:.2f})", level="SYS")

        # 2. Market Conviction Scaling
        conv_cfg = getattr(self, "conviction_scaling", {"enabled": False})
        if conv_cfg.get("enabled"):
            odds_score = self.market_data.get("odds_score", 0.0)
            conv_mult = 1.0
            sentiment_match = (sd == "UP" and odds_score > 0) or (sd == "DOWN" and odds_score < 0)
            abs_odds = abs(odds_score)
            if sentiment_match:
                if abs_odds >= conv_cfg.get("extreme_thresh", 20.0):
                    conv_mult = conv_cfg.get("mult_decisive", 1.50)
                elif abs_odds >= conv_cfg.get("high_thresh", 10.0):
                    conv_mult = conv_cfg.get("mult_strong", 1.25)
            if abs_odds < 3.0: # Weak odds penalty
                conv_mult = conv_cfg.get("penalty", 0.50)
            
            if conv_mult != 1.0:
                final_bs *= conv_mult
                log_tag = "conv_logged"
                if info is not None:
                    if not info.get(log_tag):
                        tag = "BOOST" if conv_mult > 1.0 else "PENALTY"
                        self.log_msg(f"CONVICTION {tag}: {conv_mult}x (Odds:{odds_score:+.1f}) -> ${final_bs:.2f}", level="SYS")
                        info[log_tag] = True
                else:
                    tag = "BOOST" if conv_mult > 1.0 else "PENALTY"
                    self.log_msg(f"CONVICTION {tag}: {conv_mult}x (Odds:{odds_score:+.1f}) -> ${final_bs:.2f}", level="SYS")
        
        return True, final_bs, skepticism_penalty

    async def fetch_market_loop(self):
        if not getattr(self, "app_active", False): return
        if self.halted: return  # Bot frozen — bankroll exhausted
        try:
            freq = self.config.MARKET_FREQ
            now = datetime.now(timezone.utc); floor = (now.minute // freq) * freq
            ts_start = int(now.replace(minute=floor, second=0, microsecond=0).timestamp())
            
            # Initialize loop variables to prevent UnboundLocalError on fetch failure
            candles = ([], [], [], []); poly = {}; cur = 0; opn = 0; rsi = 50.0
            up_bid = down_bid = up_ask = down_ask = 0.5
            
            # Map scanner names to their UI checkbox IDs
            scanner_map = {
                "NPattern": "#cb_npa", "Fakeout": "#cb_fak", "Momentum": "#cb_mom", "MM2": "#cb_mm2",
                "RSI": "#cb_rsi", "TrapCandle": "#cb_tra", "MidGame": "#cb_mid", "LateReversal": "#cb_lat",
                "BullFlag": "#cb_sta", "CoiledCobra": "#cb_cco", "PostPump": "#cb_pos", "StepClimber": "#cb_ste",
                "Slingshot": "#cb_sli", "MinOne": "#cb_min", "Liquidity": "#cb_liq", "Cobra": "#cb_cob",
                "Mesa": "#cb_mes", "MeanReversion": "#cb_mea", "GrindSnap": "#cb_gri", "VolCheck": "#cb_vol",
                "Moshe": "#cb_mos", "ZScore": "#cb_zsc", "Nitro": "#cb_nit", "VolSnap": "#cb_vsn", "HDO": "#cb_hdo", "Briefing": "#cb_bri",
                "WCP": "#cb_wcp", "VPOC": "#cb_vpoc", "SDP": "#cb_sdp", "DIV": "#cb_div", "SSI": "#cb_ssi",
                "SSC": "#cb_ssc", "ADT": "#cb_adt"
            }
            
            if not self.risk_initialized:
                try:
                    val = float(self.query_one("#inp_risk_alloc").value)
                    self.risk_manager.set_bankroll(val, is_live=self.query_one("#cb_live").value)
                    self.risk_initialized = True
                except: pass
            is_new_window = False
            is_first_tick = (self.market_data["start_ts"] == 0)
            
            if ts_start != self.market_data["start_ts"]:
                if not is_first_tick:
                    is_new_window = True
                    
                    # GAP DETECTION (v5.9.9): Prevent stale settlements after long disconnections
                    last_window_ts = getattr(self, "last_window_ts", 0)
                    gap = ts_start - last_window_ts if last_window_ts > 0 else 0
                    if last_window_ts > 0 and gap > 420: # 7-minute gap (tolerant to 5m + slight drift)
                        self.log_msg(f"[bold yellow]GAP DETECTED: {gap}s since last window. Skipping stale settlement/audit.[/]", level="ADMIN")
                        self.audit_buffer = None # Discard pending audit for the window before the gap
                    else:
                        # [FIX] Capture state for the window we are about to settle
                        old_slug = self.market_data.get("slug")
                        old_strike = self.market_data.get("window_strike")
                        self.trigger_settlement(settlement_slug=old_slug, settlement_strike=old_strike)
                
                self.last_window_ts = ts_start # Track for gap detection
                
                self.market_data["start_ts"] = ts_start # Latch immediately to prevent double-trigger
                self.sim_broker.promote_prebuy()  # Move any pre-buy shares/costs to current window
                
                # --- [NEW] Full Wallet Sync Mode ---
                if getattr(self, "auto_sync_risk", False):
                    is_live = self.query_one("#cb_live").value
                    if is_live: self.live_broker.update_balance()
                    main_bal = self.live_broker.balance if is_live else self.sim_broker.balance
                    self.risk_manager.risk_bankroll = main_bal
                    self.risk_manager.target_bankroll = main_bal
                    self.log_msg(f"SYNC: ${main_bal:.2f} ({'FULL' if getattr(self, 'auto_sync_risk', False) else 'PARTIAL'})", level="SYS")
                # ------------------------------------

                self.window_settled = False # reset latch for new window
                self.last_second_exit_triggered = False # reset latch for late exits
                self.next_window_preview_triggered = False # reset next-window preview latch
                self.pre_buy_triggered = False # reset pre-buy latch for new window
                self.hdo_fired_in_window = False # reset HDO latch for new window
                self.window_realized_revenue = 0.0 # reset revenue tracker for new window
                
                # Transfer any pre-buy position into window_bets so TP/SL monitors it
                if self.pre_buy_pending:
                    sd = self.pre_buy_pending.get("side", "??")
                    reason = self.pre_buy_pending.get("reason", "")
                    reason_str = f" ({reason})" if reason else ""
                    key = f"Momentum_PreBuy_{time.time()}"
                    self.window_bets[key] = self.pre_buy_pending
                    # Note: Shares are promoted by sim_broker.promote_prebuy() above.
                    self.pre_buy_pending = None
                    action = "LONG" if sd == "UP" else "SHORT"
                    self.log_msg(f"MONITORING: [{action}] Active | Status: TP/SL Engaged {reason_str}", level="ADMIN")

                self.skipped_logs.clear() # reset the spam preventer
                self.pending_bets.clear()  # discard any stale pending bets from last window
                self.bounce_pending.clear() # discard any stale bounce entries from last window
                for sc in self.scanners.values(): sc.reset() # reset all scanner signals/timers
                
                if self.mid_window_lockout:
                    self.mid_window_lockout = False
                    self.log_msg("[bold green]Lockout Lifted. Clean Window Started. Trading Enabled.[/]")

                # Reset Lean Chart for new window
                try: self.query_one("#pulse_lean_chart").reset()
                except: pass

            # Calculate correct elapsed time using the actual window start
            elapsed = int(now.timestamp()) - ts_start
            # Moved self.market_data["start_ts"] = ts_start up to the is_new_window block for race safety
            
            # Mid-Window Safety Lockout Activation (If booting the bot deeply into a round)
            if is_first_tick and elapsed > 10:
                self.mid_window_lockout = True
                self.log_msg(f"[bold yellow]Booted Mid-Round ({elapsed}s elapsed). Waiting for next clean window to start trading...[/]")
                
            # Initial 10-second Lockout (prevents instant execution before APIs stabilize)
            is_initial_lockout = elapsed < 10
            slug = f"btc-updown-{freq}m-{ts_start}"
            self.market_data["slug"] = slug  # Essential for accounting
            
            # Fetch Kraken Open Price instantly to avoid API lag from other services
            cur = await asyncio.to_thread(self.market_data_manager.fetch_current_price)
            opn = await asyncio.to_thread(self.market_data_manager.update_history, cur, ts_start, elapsed)

            # --- [NEW] Connection Resumption Logic ---
            if self.market_data_manager.just_reconnected:
                self.market_data_manager.just_reconnected = False
                if elapsed > 90:
                    self.mid_window_lockout = True
                    self.log_msg(f"[bold yellow]RECONNECTED: {elapsed}s into window. SUSPENDING trading for this round...[/]", level="ADMIN")
                else:
                    self.log_msg(f"[bold green]RECONNECTED: {elapsed}s into window. Resuming normally...[/]", level="ADMIN")
                
                # Elegant Resume Statement with Guess (if possible)
                try:
                    up_p = self.market_data.get("up_price", 0.5) * 100
                    dn_p = self.market_data.get("down_price", 0.5) * 100
                    guess = "UP" if up_p > dn_p else "DOWN"
                    self.log_msg(f"RESUME: Guess=[bold cyan]{guess}[/] (UP={up_p:.1f}¢ | DN={dn_p:.1f}¢)", level="SCAN")
                except: pass
            # ------------------------------------------
            
            if is_new_window:
                self.awaiting_next_strike = True
                # Strike will be populated later in the loop from 'poly' data

            if not getattr(self, "app_active", False): return

            # Refactored for efficiency: use asyncio.to_thread with gather
            # to avoid creating a new ThreadPoolExecutor every second
            try:
                results = await asyncio.gather(
                    asyncio.to_thread(self.market_data_manager.update_4h_trend),
                    asyncio.to_thread(self.market_data_manager.update_1h_trend),
                    asyncio.to_thread(self.market_data_manager.fetch_candles_60m),
                    asyncio.to_thread(self.market_data_manager.fetch_polymarket, slug)
                )
                candles, poly = results[2], results[3]
            except Exception as e:
                self.safe_call(self.log_msg, f"[dim]Fetch error: {e}[/]")
                # [FIX] Provide full dict structure to prevent downstream KeyErrors
                candles, poly = ([], [], [], []), {
                    "up_price": 0.5, "down_price": 0.5,
                    "up_bid": 0.5, "down_bid": 0.5,
                    "up_ask": 0.51, "down_ask": 0.51,
                    "up_id": "unknown_up", "down_id": "unknown_down",
                    "p2b": None
                }

            # --- [DEFERRED LOGGING & AUDIT LOGIC] ---
            # v5.9.8: Settlement is now immediate at T=0. 
            if is_new_window:
                # 0. Settlement already triggered at rollover (lines 212-216)
                self.audit_completed = False # Reset audit latch for new window
                
                # 1. Capture current window strike (will be compared at T+30 in NEXT window's audit)
                self.market_data["window_strike"] = poly.get("p2b") if poly else None
                
                # 2. Immediate Header (v5.9.8)
                self.generate_window_briefing()
                if self.query_one("#cb_live").value:
                    self.live_broker.update_balance()
                    
                active_str = ""
                open_bets = [info for info in self.window_bets.values() if not info.get("closed")]
                if open_bets:
                    unique_sides = sorted(list(set(info["side"] for info in open_bets)))
                    active_str = f" | [bold green]Active: {', '.join(unique_sides)}[/]"
                
                try: t_str = datetime.fromtimestamp(ts_start).strftime('%b %d %H:%M')
                except: t_str = str(ts_start)
                self.log_msg(f"WIN: {t_str} | Op: [bold white]${opn:,.2f}[/]{active_str}", level="ADMIN")

            # 3. Store HTML price to beat at T+30 for documentation
            if elapsed >= 30 and elapsed <= 35:
                slug = f"btc-updown-{self.config.MARKET_FREQ}m-{ts_start}"
                html_change = self.market_data_manager.store_html_price_to_beat(slug, elapsed)

            # 4. Compare HTML price to beat at T+330 for PnL correction
            if elapsed >= 330 and elapsed <= 335:
                slug = f"btc-updown-{self.config.MARKET_FREQ}m-{ts_start}"
                html_change = self.market_data_manager.compare_html_price_to_beat(slug, elapsed)
                
                if html_change and html_change.get("changed"):
                    self.log_msg(f"[bold red]⚠️ HTML PTB CHANGED: ${html_change['t30_price']:,.2f} → ${html_change['t330_price']:,.2f}[/]", level="ERROR")
                    self.log_msg(f"[bold yellow]PnL correction needed[/]", level="ERROR")
                    # TODO: Implement PnL correction logic here

            # 4. Background Audit at T+10-15s (User requested: 10-15 seconds into next window)
            if 10 <= elapsed <= 15 and not getattr(self, "audit_completed", False) and getattr(self, "audit_buffer", None):
                self.audit_completed = True # Latch immediately to prevent double-fire
                buf = self.audit_buffer
                self.audit_buffer = None 
                
                # Fetch official data
                audit_slug = buf.get("slug")
                current_slug = self.market_data.get("slug")
                
                async def _perform_official_audit():
                    if not getattr(self, "app_active", False): return
                    try:
                        # Capture the elapsed time at audit start for consistent logging
                        audit_start_elapsed = int(time.time() - self.market_data["start_ts"])
                        
                        # 1. Fetch official baseline from CURRENT window
                        self.log_msg(f"[bold cyan]🔍 AUDIT INITIATED:[/bold cyan] T+{audit_start_elapsed}s - Fetching state for {audit_slug}...", level="SYS")
                        
                        # We may need to retry a few times if the market isn't 'resolved' yet
                        official_winner = "TIE"
                        audit_src = "Poly"
                        p2b_next = None
                        
                        for attempt in range(3):
                            audit_data = await asyncio.to_thread(self.market_data_manager.fetch_polymarket, audit_slug, force_refresh=True)
                            p2b_next = audit_data.get("p2b")
                            
                            if audit_data.get("resolution_status") == "resolved":
                                # Identify Winner from Outcome Prices (definitive)
                                prices = audit_data.get("outcome_prices", [])
                                if len(prices) >= 2:
                                    if float(prices[0]) == 1.0: official_winner = "UP"
                                    elif float(prices[1]) == 1.0: official_winner = "DOWN"
                                break
                            
                            if attempt < 2:
                                current_elapsed = int(time.time() - self.market_data["start_ts"])
                                self.log_msg(f"[dim]Audit: T+{current_elapsed}s - Market {audit_slug} not resolved yet. Retrying in 5s...[/]")
                                await asyncio.sleep(5)

                        # 2. Definitively Establish the Strike-to-Strike Baseline
                        p2b_start = buf.get("strike_o") # T=0 Strike recorded at window start
                        
                        if p2b_start is None:
                            self.log_msg(f"[dim]Audit Aborted: Base strike missing from buffer.[/]", level="SYS")
                            return

                        if not p2b_next:
                            # Fallback if Poly fails to return P2B even on audit
                            p2b_next = buf.get("close_price") 
                            audit_src = "Krak"
                            
                        # Final safety check before comparisons
                        if p2b_next is None:
                            self.log_msg(f"[dim]Audit Aborted: Closing price missing from all sources.[/]", level="SYS")
                            return

                        # If no Poly resolution, fallback to strike-comparison logic
                        if official_winner == "TIE":
                            if p2b_next > p2b_start: official_winner = "UP"
                            elif p2b_next < p2b_start: official_winner = "DOWN"
                        
                        if p2b_start is not None and p2b_next is not None:
                            p_delta = p2b_next - p2b_start
                            off_delta_str = f"Δ ${p_delta:+.2f}"
                            
                            # Compare Action (Kraken) vs Outcome (Poly)
                            audit_completion_elapsed = int(time.time() - self.market_data["start_ts"])
                            if official_winner == buf["pulse_result"]:
                                self.log_msg(f"[bold green]✅ SYNC MATCH:[/] T+{audit_completion_elapsed}s - Bot {buf['pulse_result']} | Poly {official_winner} ({off_delta_str})", level="SYS")
                                sync_status = "Match"
                            else:
                                # DIRECTIONAL MISMATCH
                                if official_winner == "TIE":
                                    self.log_msg(f"[bold cyan]⚖️ SYNC TIE:[/] T+{audit_completion_elapsed}s - Bot {buf['pulse_result']} | Poly TIE ({off_delta_str})", level="SYS")
                                    sync_status = "Tie (Mismatch)"
                                else:
                                    self.log_msg(f"[bold yellow]⚠️ SYNC MISMATCH:[/] T+{audit_completion_elapsed}s - Bot {buf['pulse_result']} | Poly {official_winner} ({off_delta_str})", level="STATS")
                                    sync_status = "Mismatch"

                            # --- FINANCIAL RECONCILIATION (PnL Correction) ---
                            # DISABLED: Trust pulse_result over official resolution
                            # Logic: If Directional Mismatch, reverse local error.
                            # User observation: pulse_result is usually correct when Polymarket shows mismatch
                            if False:  # official_winner != buf["pulse_result"] and official_winner != "TIE":
                                is_l = self.query_one("#cb_live").value
                                # Calculate what correct payout SHOULD have been
                                shares_up = buf.get("shares", {}).get("UP", 0)
                                shares_dn = buf.get("shares", {}).get("DOWN", 0)
                                correct_payout = shares_up if official_winner == "UP" else shares_dn
                                
                                # The 'logged_pnl' already includes incorrect payout.
                                actual_payout = shares_up if buf["pulse_result"] == "UP" else shares_dn
                                recon_amt = correct_payout - actual_payout
                                
                                if recon_amt != 0:
                                    self._add_risk_revenue(recon_amt)
                                    self.session_pnl += recon_amt
                                    
                                    # Adjust win count
                                    if recon_amt > 0: # Crediting
                                        self.session_win_count += 1
                                    else: # Reversing
                                        self.session_win_count = max(0, self.session_win_count - 1)
                                        
                                    action_verb = "Crediting" if recon_amt > 0 else "Reversing"
                                    self.log_msg(f"[bold cyan]⚖️ RECONCILE:[/] {action_verb} ${abs(recon_amt):.2f} due to Mismatch. (New Bal: ${self.risk_manager.risk_bankroll:.2f})", level="MONEY")

                            # 4. Finalized Settlement Row (HTML Log)
                            # ----------------------------------------
                            try:
                                timestamp_str = datetime.now().strftime("%H:%M:%S")
                                pm_url = f"https://polymarket.com/event/{audit_slug}"
                                row_class = "match" if sync_status == "Match" else "discrepancy"
                                if official_winner == "TIE": row_class = "result_tie"
                                
                                # Calculate new fields from audit buffer
                                # Entry timing: calculate when entry occurred after window start
                                entry_time = 0
                                entry_price = 0
                                primary_scanner = "N/A"
                                
                                # Calculate window_invested for this HTML log entry
                                window_invested = sum(info.get("cost", 0) for info in self.window_bets.values())
                                
                                # Find the earliest/primary trade for this window
                                for trade_id, trade_info in self.window_bets.items():
                                    if not trade_info.get("closed"):
                                        entry_time = max(entry_time, int(time.time() - buf.get("window_id", 0)))
                                        entry_price = trade_info.get("entry", 0)
                                        primary_scanner = trade_info.get("algorithm", "Unknown")
                                        break  # Use first/primary trade
                                
                                risk_percent = (window_invested / self.risk_manager.risk_bankroll * 100) if self.risk_manager.risk_bankroll > 0 else 0
                                
                                with open(self.html_log_file, "a", encoding="utf-8") as f:
                                    is_l = self.query_one("#cb_live").value
                                    main_bal = self.live_broker.balance if is_l else self.sim_broker.balance
                                    logged_pnl = buf.get("pnl", 0.0)
                                    
                                    f.write(f"<tr class='{row_class}'>")
                                    f.write(f"<td>{timestamp_str}</td>")
                                    f.write(f"<td><a href='{pm_url}' target='_blank'>{audit_slug}</a></td>")
                                    f.write(f"<td>${p2b_start:,.2f}</td>") # Bot Strike
                                    f.write(f"<td>${p2b_next:,.2f} ({audit_src})</td>") # Poly Strike
                                    f.write(f"<td>{p_delta:+.2f}</td>") # Strike Drift
                                    f.write(f"<td>${buf.get('close_price', 0):,.2f}</td>") # Settlement Price
                                    f.write(f"<td><span class='{official_winner}'>{official_winner}</span></td>") # Resolution
                                    f.write(f"<td><span class='{buf['pulse_result']}'>{buf['pulse_result']}</span></td>") # Pulse Result
                                    f.write(f"<td>{sync_status}</td>")
                                    
                                    # NEW HIGH-IMPACT FIELDS
                                    risk_class = "risk-low" if risk_percent < 5 else ("risk-medium" if risk_percent < 15 else "risk-high")
                                    f.write(f"<td>${buf.get('entry_price', 0):,.2f}</td>") # Entry Price
                                    f.write(f"<td><span class='value {risk_class}'>{risk_percent:.1f}%</span></td>") # Risk % 
                                    f.write(f"<td><span class='value scanner'>{primary_scanner}</span></td>") # Scanner Name
                                    f.write(f"<td><span class='value entry-time'>{entry_time}s</span></td>") # Entry Timing
                                    
                                    f.write(f"<td>{logged_pnl:+.2f}</td>")
                                    f.write(f"<td>${main_bal:,.2f}</td>") # Simulated/Live Balance
                                    graph_fn = buf.get("graph_filename", "")
                                    if graph_fn:
                                        f.write(f"<td><img src='graphs/{graph_fn}' class='graph-img' onclick='window.open(this.src)'></td>")
                                    else:
                                        f.write(f"<td>N/A</td>")
                                    f.write(f"</tr>\n")
                                    
                                    # Parallel FTP Upload
                                    if self.log_settings.get("verification_html", True):
                                        self.ftp_manager.upload_html_log(self.html_log_file)
                                        
                                    # Push metrics to dashboard
                                    try:
                                        self.ftp_manager.push_session_stats(
                                            pnl=getattr(self, "session_pnl", 0.0),
                                            trades=getattr(self, "session_total_trades", 0),
                                            status="ACTIVE",
                                            interval=f"{self.config.MARKET_FREQ}M"
                                        )
                                    except: pass
                            except Exception as e:
                                self.log_msg(f"[red]HTML Log Error: {e}[/]", level="ERROR")
                        else:
                            self.log_msg(f"[dim]Audit Deferred: Could not establish Strike continuity.[/]", level="SYS")
                    except Exception as e:
                        if getattr(self, "app_active", False):
                            self.log_msg(f"[red]Audit Process Error: {e}[/]", level="ERROR")

                asyncio.create_task(_perform_official_audit())

            # [NEW] Capture current window strike if not set (for first window after boot)
            if not self.market_data.get("window_strike") and poly:
                self.market_data["window_strike"] = poly.get("p2b")
            # ----------------------------------------
            c60, l60, h60, _ = candles
            
            # Update ATR 5m
            if h60 and l60 and c60:
                self.market_data_manager.atr_5m = calculate_atr(h60, l60, c60, period=5)
            
            d = {"c60":c60, "l60":l60, "h60":h60, "cur":cur, "opn":opn, "poly":poly}
            
            self.market_data.update({
                "btc_price": d["cur"], "btc_open": d["opn"],
                "up_price": d["poly"]["up_price"], "down_price": d["poly"]["down_price"],
                "up_bid": d["poly"]["up_bid"], "down_bid": d["poly"]["down_bid"],
                "up_ask": d["poly"]["up_ask"], "down_ask": d["poly"]["down_ask"],
                "up_id": d["poly"]["up_id"], "down_id": d["poly"]["down_id"]
            })
            # Sync btc_open into MarketDataManager so next volume refresh can filter around it
            self.market_data_manager.market_data["btc_open"] = d["opn"]
            
            # Push to Lean Chart
            try: self.query_one("#pulse_lean_chart").push_value(elapsed, d["poly"]["up_price"])
            except: pass
            
            rsi = calculate_rsi(d["c60"])
            self.market_data['rsi'] = rsi # Store for manual access
            _, _, lbb = calculate_bb(d["c60"])
            ph = self.market_data_manager.price_history
            fbb = calculate_bb([p['price'] for p in ph[-20:]]) if len(ph) >= 20 else (0,0,0)

            # --- Momentum Analytics (v5.9.4) ---
            cur_btc = d["cur"]
            if self.mom_analytics["window_low"] is None or cur_btc < self.mom_analytics["window_low"]:
                self.mom_analytics["window_low"] = cur_btc
            if self.mom_analytics["window_high"] is None or cur_btc > self.mom_analytics["window_high"]:
                self.mom_analytics["window_high"] = cur_btc

            if elapsed == 5 and self.mom_analytics["gap_5s"] is None:
                self.mom_analytics["gap_5s"] = d["poly"]["up_ask"] - d["poly"]["down_ask"]
                self.mom_analytics["btc_5s"] = d["cur"]
            elif elapsed == 10 and self.mom_analytics["gap_10s"] is None:
                self.mom_analytics["gap_10s"] = d["poly"]["up_ask"] - d["poly"]["down_ask"]
                self.mom_analytics["btc_10s"] = d["cur"]
            elif elapsed == 15 and self.mom_analytics["gap_15s"] is None:
                self.mom_analytics["gap_15s"] = d["poly"]["up_ask"] - d["poly"]["down_ask"]
                self.mom_analytics["btc_15s"] = d["cur"]
                self.mom_analytics["up_bid_15s"] = d["poly"]["up_bid"]
                self.mom_analytics["down_bid_15s"] = d["poly"]["down_bid"]
                # Capture spread at 15s entry mark (standardized for UP side)
                u_ask, u_bid = d["poly"]["up_ask"], d["poly"]["up_bid"]
                if u_ask > 0 and u_bid > 0:
                    self.mom_analytics["spread_15s"] = u_ask - u_bid

            # Monitor Milestones: 55c, 60c, 65c
            u_bid, d_bid = d["poly"]["up_bid"], d["poly"]["down_bid"]
            for threshold in [0.55, 0.60, 0.65]:
                key_s = f"first_{int(threshold*100)}c_side"
                key_t = f"first_{int(threshold*100)}c_time"
                if self.mom_analytics[key_s] is None:
                    if u_bid >= threshold:
                        self.mom_analytics[key_s], self.mom_analytics[key_t] = "UP", elapsed
                    elif d_bid >= threshold:
                        self.mom_analytics[key_s], self.mom_analytics[key_t] = "DOWN", elapsed
            # -----------------------------------

            tick_signals = {}  # Collect scanner signals this tick for CSV analytics

            # --- Bounce Entry: Per-Tick Monitor ---
            if self.bounce_pending and not self.mid_window_lockout:
                for _bname, _binfo in list(self.bounce_pending.items()):
                    _bsd  = _binfo["side"]
                    _btgt = _binfo["target_level"]
                    _bdip = _binfo["dip_depth"]
                    _bcur = self.market_data["up_ask"] if _bsd == "UP" else self.market_data["down_ask"]

                    if not _binfo["has_dipped"]:
                        if _bcur < (_btgt - _bdip):
                            _binfo["has_dipped"] = True
                            self.log_msg(f"BOUNCE {_bname} | Dip confirmed at {_bcur*100:.1f}¢ — watching for recovery to {_btgt*100:.1f}¢", level="SCAN")
                    else:
                        if _bcur >= _btgt:
                            # Recovery confirmed — execute
                            _bbs = _binfo["bs"]
                            if self.risk_manager.risk_bankroll >= _bbs:
                                _is_l = self.query_one("#cb_live").value
                                _ok, _msg, _act_sh, _act_pr = self.trade_executor.execute_buy(
                                    _is_l, _bsd, _bbs, _bcur,
                                    d["poly"]["up_id" if _bsd == "UP" else "down_id"],
                                    context={}, reason=f"Bounce:{_binfo['signal']}"
                                )
                                if _ok:
                                    self._handle_successful_buy(_bname, _bsd, _bbs, _act_sh, _act_pr, _is_l)
                                    self.session_total_trades += 1
                                    self.log_msg(f"[bold green]BOUNCE EXEC {_bname}[/]: {_msg} ({_binfo['signal']})", level="TRADE")
                                else:
                                    self.log_msg(f"[bold red]BOUNCE FAIL {_bname}[/]: {_msg}")
                            del self.bounce_pending[_bname]
            # --- Trend / Safety Logic (v5.9.10) ---
            cur_trend = self.market_data_manager.trend_1h
            safety_mode = getattr(self, "exec_safety_mode", "global_lock")
            
            # Default multipliers
            mult = 1.0
            cool_mult = 1.0
            
            if safety_mode == "original":
                # Legacy behavior: No trend scaling, simple duplicate check
                pass 
            else:
                # Modern behavior: scale by trend efficiency
                t_cfg = self.trend_efficiency.get(cur_trend, {"mult": 1.0, "lock": "side_lock", "cool": 1.0})
                mult = t_cfg.get("mult", 1.0)
                cool_mult = t_cfg.get("cool", 1.0)
                # Override safety mode if trend dictates it (for backward compat with legacy features)
                safety_mode = t_cfg.get("lock", safety_mode)

            # --- Execution Safeguards ---
            cool_dur = 45 * cool_mult
            is_cooling = (time.time() - self.last_sl_event_time < cool_dur)
            
            if not self.mid_window_lockout and not is_initial_lockout:
                if is_cooling:
                    pass # In post-SL cooling period
                else:
                    active_bets = [info for info in self.window_bets.values() if not info.get("closed")]
                    for name, info in list(self.pending_bets.items()):
                        sd = info["side"]
                        # Recalculate cost to include any new executions this tick
                        total_window_cost = sum(info.get("cost", 0) for info in self.window_bets.values())
                        bs = info["bs"] * mult
                        
                        # Decide if this bet is blocked by our safety mode
                        is_blocked = False
                        if safety_mode == "original":
                            # Legacy check is just: already have a bet for this scanner/side?
                            # This is already handled at the point of adding to pending_bets.
                            pass
                        elif safety_mode == "global_lock":
                            if len(active_bets) > 0: is_blocked = True
                        elif safety_mode == "side_lock":
                            if any(ab["side"] == sd for ab in active_bets): is_blocked = True
                        elif safety_mode == "risk_cap":
                            current_cost = sum(ab["cost"] for ab in active_bets)
                            if current_cost + bs >= self.total_risk_cap: is_blocked = True
                        elif safety_mode == "dynamic":
                            atr = getattr(self.market_data_manager, "atr_5m", 0)
                            bias = self.market_data.get("bias_guess", "NEUTRAL")
                            if atr > 40 or bias == "CHOP":
                                if len(active_bets) > 0: is_blocked = True 
                            else:
                                if any(ab["side"] == sd for ab in active_bets): is_blocked = True
                        
                        # --- UNIVERSAL WINDOW CAP ENFORCEMENT (v5.9.9) ---
                        # Strictly enforce self.total_risk_cap regardless of safety mode.
                        if not is_blocked:
                            remaining_cap = max(0, getattr(self, "total_risk_cap", 30.0) - total_window_cost)
                            if bs > remaining_cap:
                                bs = remaining_cap
                                if bs < 1.00:
                                    is_blocked = True
                        
                        if is_blocked:
                            continue 
                        
                        if mult != 1.0:
                             wid = self.market_data.get("start_ts", 0)
                             if self.logged_trend_wid != wid:
                                 self.log_msg(f"Trend {cur_trend}: Applying {mult}x Mult -> ${bs:.2f}", level="SYS")
                                 self.logged_trend_wid = wid

                        res = info["res"]
                        pr = self.market_data["up_ask"] if sd == "UP" else self.market_data["down_ask"]
                        
                        # Use unified scaling logic (Pass info to ensure logging latches work)
                        ok_final, final_bs, final_skeptic = self._refant_finalize_bet(name, sd, bs, pr, res, info=info)
                        
                        # [FEATURE] Global Window Investment Cap enforcement for Pending Bets
                        remaining_cap = max(0, getattr(self, "total_risk_cap", 30.0) - total_window_cost)
                        if final_bs > remaining_cap:
                            final_bs = remaining_cap
                            if final_bs < 1.00:
                                suppress_key = f"CAP_REACHED_{name}"
                                if suppress_key not in self.skipped_logs:
                                    self.log_msg(f"SKIPPED {name} | Window Risk Cap Reached (${total_window_cost:.2f}/$30)", level="SCAN")
                                    self.skipped_logs.add(suppress_key)
                                continue
                        
                        if ok_final:
                            is_l = self.query_one("#cb_live").value
                            
                            # Final Min Bet Check before launching execution
                            if is_l and final_bs < self.config.MIN_BET:
                                if not info.get("min_bet_logged"):
                                    self.log_msg(f"SKIPPED {name} | Final bet ${final_bs:.2f} < Min ${self.config.MIN_BET:.2f}", level="SCAN")
                                    info["min_bet_logged"] = True
                                continue

                            # Final Bankroll Check
                            if self.risk_manager.risk_bankroll < final_bs:
                                continue
                                
                            is_l = self.query_one("#cb_live").value
                            ctx = {
                                'signal_price': d["cur"], 
                                'rsi': rsi, 
                                'trend': self.market_data_manager.trend_1h, 
                                'risk_bal': self.risk_manager.risk_bankroll
                            }
                            
                            ok, msg, act_shares, act_price = self.trade_executor.execute_buy(
                                is_l, sd, final_bs, pr, 
                                d["poly"]["up_id" if sd=="UP" else "down_id"], 
                                context=ctx, 
                                reason=f"Pending: {res}"
                            )
                            if ok:
                                self._handle_successful_buy(name, sd, final_bs, act_shares, act_price, is_l)
                                self.session_total_trades += 1
                                
                                short_res = str(res).replace("BET_UP_", "").replace("BET_DOWN_", "").replace("Leader @ 10s:", "Ldr:").replace(" UP ", " ").replace(" DOWN ", " ")
                                prefix = name[:3].upper()
                                self.log_msg(f"[bold green]EXEC {name}[/]: {msg} ({prefix}|{short_res})")
                            else:
                                self.log_msg(f"[bold red]FAIL {name}[/]: {msg}")
                                
                            # Cleanup pending state regardless of result
                            del self.pending_bets[name]
                            try:
                                lbl = self.query_one(f"#lbl_{name[:3].lower()}")
                                lbl.remove_class("blinking")
                            except: pass
            # --------------------------------
            # Build unified context for all scanners
            context = {
                "elapsed": elapsed,
                "up_bid": d["poly"]["up_bid"],
                "down_bid": d["poly"]["down_bid"],
                "up_ask": d["poly"]["up_ask"],
                "down_ask": d["poly"]["down_ask"],
                "atr_5m": getattr(self.market_data_manager, "atr_5m", 0),
                "trend_1h": self.market_data_manager.trend_1h,
                "odds_score": round((d["poly"]["up_bid"] - d["poly"]["down_bid"]) * 100, 1),
                "rsi_1m": rsi,
                "velocity": (d["cur"] - getattr(self.mom_analytics, "btc_pre_60s", 0)) if getattr(self.mom_analytics, "btc_pre_60s", None) is not None else 0,
                "window_analytics": self.mom_analytics,
                "history_objs": ph, # List of dicts: {'price': p, 'elapsed': e}
                "open_price": d["opn"],
                "prev_window_color": "GREEN" if d["cur"] > d["opn"] else "RED", # Technically current window color, but matching older logic
                "closes_60m": d["c60"],
                "current_price": d["cur"],
                "bb_lower": lbb,
                "window_seconds": self.config.WINDOW_SECONDS,
                "phase1_duration": self.config.PHASE1_DURATION,
                "swing_low": min(d["l60"]) if d["l60"] else 0,
                "last_window": {}, # Kept empty for now to match PostPump signature
                "fast_bb": fbb,
                "vol_up": self.market_data.get("vol_up", 0),
                "vol_dn": self.market_data.get("vol_dn", 0),
                "btc_open": d["opn"],
                "btc_price": d["cur"],
                # --- [NEW] Inter-Window Totality Context ---
                "last_window_ohlc": getattr(self, "last_window_data", {}).get("ohlc"),
                "last_window_poc": getattr(self, "last_window_data", {}).get("poc"),
                "last_settlement_drift": getattr(self, "last_window_data", {}).get("drift"),
                "current_loss_streak": getattr(self, "current_loss_streak", 0),
                "odds_delta": (float(d["poly"].get("up_bid", 0.5)) - float(d["poly"].get("down_bid", 0.5))) - getattr(self, "last_odds_base", 0.0),
                "btc_pct_delta": (d["cur"] - d["opn"]) / d["opn"] if d["opn"] > 0 else 0
            }

            # 1. Process All Scanners to find signals
            total_window_cost = sum(info.get("cost", 0) for info in self.window_bets.values())
            for name, sc in self.scanners.items():
                if not self.query_one(scanner_map[name]).value: continue
                
                # --- [NEW] HDO Halt Guard ---
                if self.hdo_fired_in_window:
                    if "HDO_HALT_GLOBAL" not in self.skipped_logs:
                        self.log_msg("HALT Scanners | Window hedged - no further trades allowed.", level="SCAN")
                        self.skipped_logs.add("HDO_HALT_GLOBAL")
                    continue
                # ----------------------------
                
                # Dynamic Advanced Settings injection (primarily for Momentum)
                if hasattr(sc, "adv_settings"):
                    sc.adv_settings = self.mom_adv_settings
                if hasattr(sc, "buy_mode"):
                    sc.buy_mode = self.mom_buy_mode
                
                # In PRE/ADV mode at T-15s, let _do_prebuy thread be the sole caller of
                # get_signal so it reads the NEXT window context and the latch isn't consumed here.
                if name == "Momentum" and self.mom_buy_mode in ["PRE", "ADV"] and elapsed >= (self.config.WINDOW_SECONDS - 15):
                    continue

                # Check Signal
                res = sc.get_signal(context)
                
                tick_signals[name] = str(res)  # Capture for CSV analytics
                if res == "WAIT": continue
                if res == "NONE":
                    reason = getattr(sc, "last_skip_reason", None)
                    if reason:
                        # Clean reason of dynamic numbers/BTC counts for better suppression
                        import re
                        clean_reason = re.sub(r'\d+\.?\d*', 'X', reason)
                        suppress_key = f"SKIP_{name}_{clean_reason}"
                        if suppress_key not in self.skipped_logs:
                            self.log_msg(f"SKIP {name} | {reason}", level="SCAN")
                            self.skipped_logs.add(suppress_key)
                    continue
                        
                if "BET_" in str(res):
                    sd = "UP" if "UP" in str(res) else "DOWN"
                    # Robust Duplicate Check: Match algorithm name and side
                    already_have = any(
                        info.get("algorithm") == name and info.get("side") == sd and not info.get("closed")
                        for info in self.window_bets.values()
                    )
                    
                    if already_have: continue

                    # 1b. Mid-Round Lockout: skip execution if booted mid-window or in first 10s
                    if is_initial_lockout or self.mid_window_lockout:
                        if f"LOCKOUT_{name}" not in self.skipped_logs:
                            reason = "mid-round boot" if self.mid_window_lockout else "initial stabilization"
                            self.log_msg(f"[dim]LOCKOUT {name} | Signal held ({reason}) — waiting for clean window[/]", level="SCAN")
                            self.skipped_logs.add(f"LOCKOUT_{name}")
                        continue

                    # --- [NEW] LATE-WINDOW LOCKOUT (LWL) ---
                    window_secs = self.config.WINDOW_SECONDS
                    if elapsed > (window_secs - self.lw_lockout):
                        if f"LWL_{name}" not in self.skipped_logs:
                            self.log_msg(f"[bold yellow]LOCKOUT {name}[/]: {elapsed}s into window | Entry Blocked (LWL < {self.lw_lockout}s)", level="SCAN")
                            self.skipped_logs.add(f"LWL_{name}")
                        continue

                    # --- [NEW] SENTIMENT GUARD ---
                    # Only apply in the second half of the window
                    if elapsed > (window_secs / 2):
                        odds_score = context.get("odds_score", 0)
                        guard_thresh = self.sentiment_guard
                        
                        is_sentiment_blocked = False
                        if sd == "UP" and odds_score < -guard_thresh:
                            is_sentiment_blocked = True
                        elif sd == "DOWN" and odds_score > guard_thresh:
                            is_sentiment_blocked = True
                            
                        if is_sentiment_blocked:
                            guard_key = f"GUARD_{name}_{sd}"
                            if guard_key not in self.skipped_logs:
                                sentiment_str = "Bullish" if odds_score > 0 else "Bearish"
                                self.log_msg(f"[bold yellow]GUARD {name}[/]: Blocked {sd} entry vs strong {sentiment_str} Sentiment ({odds_score:+.1f}c)", level="SCAN")
                                self.skipped_logs.add(guard_key)
                            continue
                    # ----------------------------
                    # 1c. PRE mode: Momentum only enters via pre-buy, never mid-window (silent)
                    if name in ["Momentum", "MM2"] and self.mom_buy_mode == "PRE":
                        continue
                    # 2. 1-Trade-Max Guard
                    if self.query_one("#cb_one_trade").value and self.window_bets: continue
                    
                    # 3. Strong Only Filter
                    if self.query_one("#cb_strong").value:
                        strong_keywords = {"STRONG", "CONFIRMED", "HEAVY", "MAX", "90", "PULSE"}
                        if not any(k in str(res).upper() for k in strong_keywords):
                            if f"SKIP_STRONG_{name}" not in self.skipped_logs:
                                self.log_msg(f"SKIP {name} | Strong Only active (Sig: {res})", level="SCAN")
                                self.skipped_logs.add(f"SKIP_STRONG_{name}")
                            continue

                    # 4. Minimum Difference Filter
                    try: min_diff = float(self.query_one("#inp_min_diff").value)
                    except: min_diff = 0
                    if abs(d["cur"] - d["opn"]) < min_diff:
                        if f"SKIP_DIFF_{name}" not in self.skipped_logs:
                            self.log_msg(f"SKIP {name} | Diff ${abs(d['cur']-d['opn']):.2f} < Min ${min_diff:.2f}", level="SCAN")
                            self.skipped_logs.add(f"SKIP_DIFF_{name}")
                        continue

                    # 5. Bet Sizing (Unified Risk Mode)
                    try:
                        ui_amount = float(self.query_one("#inp_amount").value)
                        is_pct = self.query_one("#rs_bet_mode").pressed_button and self.query_one("#rs_bet_mode").pressed_button.id == "rb_pct"
                        if is_pct:
                            # Percentage of Anchor Bankroll
                            bs = self.risk_manager.window_start_bankroll * (ui_amount / 100.0)
                        else:
                            # Fixed Amount
                            bs = ui_amount
                    except:
                        bs = self.risk_manager.window_start_bankroll * 0.10 if self.risk_manager.window_start_bankroll > 0 else 1.00

                    # --- Apply Multipliers (Penalties & Weights) ---
                    # Trend Penalty (Going against 1H Trend)
                    t_dir = "UP" if "UP" in str(res) else "DOWN"
                    t1h = self.market_data_manager.trend_1h
                    if t1h != 'NEUTRAL' and t_dir not in t1h:
                        penalty = getattr(self, "penalty_percentage", 0.10)
                        bs *= (1.0 - penalty)
                    
                    # Consec Loss Penalty
                    port = self.portfolios.get(name)
                    if port and port.consecutive_losses >= 2:
                        bs *= 0.7
                        
                    # Scanner Weight
                    weight = self.scanner_weights.get(name[:3].upper(), 1.0)
                    bs = bs * weight

                    # Final Safety Clamp (Bankroll & Max Cap)
                    bs = min(bs, TradingConfig.MAX_BET_SESSION_CAP)
                    
                    # [FEATURE] Global Window Investment Cap ($30 Limit enforcement)
                    remaining_cap = max(0, getattr(self, "total_risk_cap", 30.0) - total_window_cost)
                    if bs > remaining_cap:
                        bs = remaining_cap
                        if bs < 1.00: # Below min bet
                           if f"SKIP_CAP_{name}" not in self.skipped_logs:
                               self.log_msg(f"SKIPPED {name} | Window Risk Cap Reached (${total_window_cost:.2f}/$30)", level="SCAN")
                               self.skipped_logs.add(f"SKIP_CAP_{name}")
                           continue
                    
                    if bs > self.risk_manager.risk_bankroll:
                        bs = self.risk_manager.risk_bankroll
                    
                    if bs > 0:
                        sd = "UP" if "UP" in str(res) else "DOWN"
                        pr = self.market_data["up_ask"] if sd == "UP" else self.market_data["down_ask"]
                        
                        # 8. Unified Finalization (Skepticism & Conviction)
                        ok_final, final_bs, skepticism_penalty = self._refant_finalize_bet(name, sd, bs, pr, res)
                        
                        if not ok_final:
                            # If blocked by price filters, park it if it's not a hard max-price block
                            filter_reason = skepticism_penalty # skepticism_penalty is the reason string if ok_final is False
                            if isinstance(filter_reason, str) and "Max" in filter_reason:
                                if f"SKIP_MAX_{name}" not in self.skipped_logs:
                                    self.log_msg(f"SKIPPED: [{name.upper()}] | Reason: {filter_reason}", level="SCAN")
                                    self.skipped_logs.add(f"SKIP_MAX_{name}")
                            elif name not in self.pending_bets:
                                self.pending_bets[name] = {"side": sd, "bs": bs, "res": res}
                                try: self.query_one(f"#lbl_{name[:3].lower()}").add_class("blinking")
                                except: pass
                            else:
                                # Update values but keep latch flags (mult_logged, skeptic_logged, etc.)
                                self.pending_bets[name].update({"side": sd, "bs": bs, "res": res})
                            continue

                        # --- Execution ---
                        if pr and 0.01 < pr < 0.99:
                            is_l = self.query_one("#cb_live").value
                            
                            # Final Min Bet Check before launching execution
                            if is_l and final_bs < self.config.MIN_BET:
                                if f"SKIP_MIN_{name}" not in self.skipped_logs:
                                    self.log_msg(f"SKIPPED {name} | Final bet ${final_bs:.2f} < Min ${self.config.MIN_BET:.2f}", level="SCAN")
                                    self.skipped_logs.add(f"SKIP_MIN_{name}")
                                continue

                            # Log reasoning for Momentum mid-window entries
                            if name == "Momentum":
                                _res_reason = str(res).split("|")[1] if "|" in str(res) else str(res)
                                _atr_now = getattr(self.market_data_manager, "atr_5m", 0)
                                _s = self.mom_adv_settings
                                if self.mom_buy_mode == "ADV":
                                    _tier = "Stable" if _atr_now <= _s.get("atr_low", 20) else ("Chaos" if _atr_now >= _s.get("atr_high", 40) else "Neutral")
                                    _offset = _s.get("stable_offset", 0) if _tier == "Stable" else (_s.get("chaos_offset", 0) if _tier == "Chaos" else 0)
                                    _sc = self.scanners.get("Momentum")
                                    _base_t = int(getattr(_sc, "base_threshold", 0.6) * 100) if _sc else 60
                                    self.log_msg(f"[dim]MOM [bold]ADV[/] entry: {_res_reason} | ATR={_atr_now:.1f} Tier=[bold]{_tier}[/] base={_base_t}¢ offset={_offset:+}¢ → thresh={_base_t + _offset}¢[/]", level="SCAN")
                                else:
                                    self.log_msg(f"[dim]MOM entry: {_res_reason} | ATR={_atr_now:.1f}[/]", level="SCAN")

                            # --- Bounce Entry Fork ---
                            dip_threshold = getattr(self, "bounce_dip_cents", 0.5) / 100.0
                            live_ask = self.market_data["up_ask"] if sd == "UP" else self.market_data["down_ask"]
                            
                            if self.bounce_mode and name not in self.bounce_pending and live_ask > (pr + dip_threshold):
                                self.bounce_pending[name] = {
                                    "side": sd, "target_level": pr, "dip_depth": dip_threshold,
                                    "has_dipped": False, "signal": str(res), "bs": final_bs
                                }
                                self.log_msg(f"BOUNCE {name} {sd} | Parked. Waiting for retest of {pr*100:.1f}¢", level="SCAN")
                            else:
                                ok, msg, act_shares, act_price = self.trade_executor.execute_buy(
                                    is_l, sd, final_bs, pr, 
                                    d["poly"]["up_id" if sd=="UP" else "down_id"], 
                                    context={'rsi':rsi,'trend':self.market_data_manager.trend_1h}, 
                                    reason=res
                                )
                                if ok:
                                    self._handle_successful_buy(name, sd, final_bs, act_shares, act_price, is_l)
                                    self.session_total_trades += 1
                                    
                                    short_res = str(res).replace("BET_UP_", "").replace("BET_DOWN_", "").replace("Leader @ 10s:", "Ldr:").replace(" UP ", " ").replace(" DOWN ", " ")
                                    prefix = name[:3].upper()
                                    self.log_msg(f"{msg} ({prefix}|{short_res})", level="TRADE")
                                else:
                                    self.log_msg(f"Fail {name}: {msg}", level="ERROR")

            # --- Update market_data with live analytics for CSV logging ---
            # BTC Range: intra-window price range from tick history
            _ph = self.market_data_manager.price_history
            if _ph:
                _prices = [p['price'] for p in _ph]
                self.market_data['btc_dyn_rng'] = max(_prices) - min(_prices)

            # Polymarket implied-probability skew (cents, positive = UP-favoured)
            self.market_data['odds_score'] = round((self.market_data['up_bid'] - self.market_data['down_bid']) * 100, 1)

            # Trend strings from market_data_manager
            self.market_data['trend_1h'] = self.market_data_manager.trend_1h
            self.market_data['trend_1h'] = self.market_data_manager.trend_1h

            # ATR & RSI
            self.market_data['atr_5m'] = self.market_data_manager.atr_5m
            self.market_data['rsi_1m'] = rsi

            # Scanner signal aggregation
            _up_sigs = sum(1 for v in tick_signals.values() if 'UP' in v)
            _dn_sigs = sum(1 for v in tick_signals.values() if 'DOWN' in v)
            self.market_data['active_scanners'] = _up_sigs + _dn_sigs
            self.market_data['master_score'] = _up_sigs - _dn_sigs
            self.market_data['master_status'] = 'BUY_UP' if _up_sigs > _dn_sigs else ('BUY_DN' if _dn_sigs > _up_sigs else 'NEUTRAL')

            # Individual key-scanner flags
            self.market_data['sling_signal'] = tick_signals.get('Slingshot', 'OFF')
            self.market_data['cobra_signal'] = tick_signals.get('Cobra', 'OFF')
            self.market_data['coiled_cobra_signal'] = tick_signals.get('CoiledCobra', 'OFF')
            self.market_data['flag_signal'] = tick_signals.get('BullFlag', 'OFF')
            # -----------------------------------------------------------------

            # Removed premature briefing call - now handled in deferred audit block
            # if is_new_window:
            #     self.generate_window_briefing()

            await self._check_tpsl()
            await self._check_hdo()
            await self._check_whale_shield()
            self.update_balance_ui(); self.update_sell_buttons()
            self.query_one("#p_up").update(f"{self.market_data['up_ask']*100:.1f}¢")
            self.query_one("#p_down").update(f"{self.market_data['down_ask']*100:.1f}¢")
            self.query_one("#p_btc").update(f"${self.market_data['btc_price']:,.2f}")
            self.query_one("#p_trend").update(f"Trend 1H: {self.market_data_manager.trend_1h}")
            self.query_one("#p_atr").update(f"ATR 5m: ${self.market_data_manager.atr_5m:.2f}")
            self.query_one("#p_btc_open").update(f"Open: ${self.market_data['btc_open']:,.2f}")
            df = self.market_data['btc_price'] - self.market_data['btc_open']
            self.query_one("#p_btc_diff").update(f"Diff: {'+' if df>=0 else '-'}${abs(df):.2f}")
            self.query_one("#p_trend").update(f"Trend 1H: {self.market_data_manager.trend_1h}")
            
            # --- Update Exposure Dashboard ---
            exp_up_cost = 0.0; exp_up_win = 0.0
            exp_dn_cost = 0.0; exp_dn_win = 0.0
            for bid, info in self.window_bets.items():
                if info.get("closed"): continue
                if info["side"] == "UP":
                    exp_up_cost += info["cost"]
                    exp_up_win += info["shares"] # shares * $1 payout
                else:
                    exp_dn_cost += info["cost"]
                    exp_dn_win += info["shares"]
            
            self.query_one("#lbl_owned_up").update(f"UP OWNED: ${exp_up_cost:.0f}/${exp_up_win:.0f}")
            self.query_one("#lbl_owned_dn").update(f"DN OWNED: ${exp_dn_cost:.0f}/${exp_dn_win:.0f}")
            # ---------------------------------
            
            # Update Volume UI (BTC quantity near window open price)
            v_up = self.market_data.get("vol_up", 0)
            v_dn = self.market_data.get("vol_dn", 0)
            cur_btc = self.market_data.get("btc_price", 0)
            def fmt_v(v_btc, price):
                if v_btc >= 100: return f"{v_btc:.0f}B"
                return f"{v_btc:.1f}B"
            self.query_one("#lbl_vol_up").update(f"V-UP: {fmt_v(v_up, cur_btc)}")
            self.query_one("#lbl_vol_dn").update(f"V-DN: {fmt_v(v_dn, cur_btc)}")

        except Exception as e: self.log_msg(f"[red]Loop Err: {e}[/]")

    def _parse_time_tp_config(self):
        """Parse time-based TP configuration from input field.
        Format: "90c@90" = 90¢ when ≤90 seconds remaining
        Format: "85c@1:30" = 85¢ when ≤90 seconds remaining (1:30 format)
        """
        try:
            time_tp_input = self.query_one("#inp_time_tp").value
            if not time_tp_input or "@" not in time_tp_input:
                return None
            
            # Clean up the input - remove extra spaces
            time_tp_input = time_tp_input.strip()
            if not time_tp_input or "@" not in time_tp_input:
                return None
                
            price_str, time_str = time_tp_input.split("@")
            
            # Clean up individual parts
            price_str = price_str.strip()
            time_str = time_str.strip()
            
            # Parse price (e.g., "90c" -> 0.90)
            if price_str.endswith("c"):
                price_str = price_str[:-1].strip()  # Remove 'c' and any spaces
                if not price_str:
                    self.log_msg(f"[dim]Time TP config error: Empty price value[/]")
                    return None
                target_price = float(price_str) / 100
            else:
                if not price_str:
                    self.log_msg(f"[dim]Time TP config error: Empty price value[/]")
                    return None
                target_price = float(price_str)
                
            # Parse time (e.g., "90" -> 90, "1:30" -> 90)
            if not time_str:
                self.log_msg(f"[dim]Time TP config error: Empty time value[/]")
                return None
                
            if ":" in time_str:
                time_parts = time_str.split(":")
                if len(time_parts) != 2:
                    self.log_msg(f"[dim]Time TP config error: Invalid time format '{time_str}'[/]")
                    return None
                try:
                    minutes = int(time_parts[0].strip())
                    seconds = int(time_parts[1].strip())
                    max_time_seconds = minutes * 60 + seconds
                except ValueError:
                    self.log_msg(f"[dim]Time TP config error: Invalid time values '{time_str}'[/]")
                    return None
            else:
                try:
                    max_time_seconds = int(time_str)
                except ValueError:
                    self.log_msg(f"[dim]Time TP config error: Invalid time value '{time_str}'[/]")
                    return None
                
            return target_price, max_time_seconds
            
        except Exception as e:
            self.log_msg(f"[dim]Time TP config error: {e}[/]")
            return None

    async def _check_tpsl(self):
        is_tp_active = self.query_one("#cb_tp_active").value
        try: use_tranche = self.query_one("#cb_tranche").value
        except: use_tranche = False
        try: time_tp_active = self.query_one("#cb_time_tp").value
        except: time_tp_active = False

        for bid, info in list(self.window_bets.items()):
            if not isinstance(info, dict): continue
            if info.get("closed"): continue
            side = info["side"]; ent = info["entry"]; cur = self.market_data["up_price"] if side=="UP" else self.market_data["down_price"]
            roi = (cur-ent)/ent; reason = None
            
            # Use specific tranche targets if available and enabled, else fallback to global
            tp = info.get("target_tp", self.committed_tp) if use_tranche else self.committed_tp
            sl = info.get("target_sl", self.committed_sl) if use_tranche else self.committed_sl
            has_limit_order = bool(info.get("limit_order_id"))
            
            # 1. Universal Max Profit (99c Guaranteed Win Exit)
            if cur >= 0.99 and not has_limit_order: 
                reason = f"MAX: {ent*100:.1f} -> {cur*100:.1f}¢ (+{roi*100:.1f}%)"
            # 2. Time-based TP Check (NEW!)
            elif time_tp_active and not has_limit_order:
                time_tp_config = self._parse_time_tp_config()
                if time_tp_config:
                    target_price, max_time_seconds = time_tp_config
                    elapsed = int(time.time() - self.market_data.get("start_ts", 0))
                    time_remaining = 300 - elapsed  # 5 minutes = 300 seconds
                    
                    if time_remaining <= max_time_seconds and cur >= target_price:
                        reason = f"TIME_TP: {ent*100:.1f} -> {cur*100:.1f}¢ (+{roi*100:.1f}%) @ {time_remaining}s left"
            # 3. UI-configurable TP/SL Check
            elif is_tp_active:
                if cur >= tp and not has_limit_order: 
                    reason = f"TP: {ent*100:.1f} -> {cur*100:.1f}¢ (+{roi*100:.1f}%)"
                elif roi <= -sl: 
                    reason = f"SL: {ent*100:.1f} -> {cur*100:.1f}¢ ({roi*100:.1f}%)"
                
            if reason:
                is_l = self.query_one("#cb_live").value
                
                # If a Limit Order was resting but we hit SL (or another emergency trigger), we MUST cancel it first.
                if is_l and has_limit_order:
                    self.trade_executor.live.cancel_limit_order(info["limit_order_id"])
                    self.log_msg(f"[dim]Cancelled resting Limit Order {info['limit_order_id'][-6:]} due to {reason.split('|')[0]}[/]")
                    
                cbid = self.market_data["up_bid"] if side=="UP" else self.market_data["down_bid"]
                # For Market dumps, always undercut the bid slightly to guarantee execution
                lp = cbid if not is_l else max(0.02, cbid-0.02)
                
                # Use act_shares instead of completely dumping if Tranche is Active
                dump_sz = info["shares"]
                if use_tranche:
                    ok, msg, realized_rev = await asyncio.to_thread(self.trade_executor.execute_sell, is_l, side, self.market_data["up_id" if side=="UP" else "down_id"], lp, cbid, reason=reason, size=dump_sz)
                else:
                    # Global Dump (but still passing size for individual ticket accounting)
                    ok, msg, realized_rev = await asyncio.to_thread(self.trade_executor.execute_sell, is_l, side, self.market_data["up_id" if side=="UP" else "down_id"], lp, cbid, reason=reason, size=dump_sz)
                if ok:
                    info["closed"] = True
                    realized_loss = info["cost"] - realized_rev
                    if realized_rev > 0: self._add_risk_revenue(realized_rev)
                    
                    if realized_rev >= info["cost"]:
                        self.session_win_count += 1 # TP/Max Profit hit
                        self.log_msg(f"{reason} | [bold green]WIN[/] | Closed {side} @ {cur*100:.1f}c", level="MONEY")
                    else:
                        self.log_msg(f"{reason} | [bold red]LOSS[/] | Closed {side} @ {cur*100:.1f}c", level="MONEY")
                        if "SL HIT" in reason:
                            self.last_sl_event_time = time.time()
                    
                    # --- SL+ RECOVERY LOGIC ---
                    # Guard: never chain recovery on a recovery bet to prevent infinite loops
                    is_recovery_bet = bid.startswith("SL+_Recovery")
                    if reason.startswith("SL HIT") and self.sl_plus_mode and realized_loss > 0 and not is_recovery_bet:
                        # Anti-Whipsaw: Disable recovery in High Volatility + Chop Bias
                        atr = getattr(self.market_data_manager, "atr_5m", 0)
                        bias = self.market_data.get("bias_guess", "NEUTRAL")
                        if atr > 40 and (bias == "CHOP" or bias == "NEUTRAL"):
                            self.log_msg(f"[dim]RECOVERY SKIPPED: High Vol Chop (ATR={atr:.1f} | Bias={bias})[/]", level="SYS")
                        else:
                            opp_side = "DOWN" if side == "UP" else "UP"
                            opp_p = self.market_data["up_ask" if opp_side == "UP" else "down_ask"]
                            if 0.05 < opp_p < 0.90:
                                # Recovery = original cost, capped only as absolute safety floor (must have at least $1 left after)
                                rec_cost = info["cost"]
                                if rec_cost > self.risk_manager.risk_bankroll - 1.0:
                                    rec_cost = max(0, self.risk_manager.risk_bankroll - 1.0)
                                    self.log_msg(f"[yellow]SL+ RECOVERY CAP:[/][dim] Original ${info['cost']:.2f} capped at available bankroll (${rec_cost:.2f})[/]")
                                
                                if rec_cost >= 0.10:
                                    self.log_msg(f"[bold cyan]SL+ RECOVERY:[/][dim] Loss ${realized_loss:.2f} -> Buying ${rec_cost:.2f} {opp_side} @ {opp_p*100:.1f}¢[/]")
                                    ok_rec, msg_rec, rec_shares, rec_price = await asyncio.to_thread(self.trade_executor.execute_buy, is_l, opp_side, rec_cost, opp_p, self.market_data["up_id" if opp_side=="UP" else "down_id"], context={}, reason="SL+_Recovery")
                                    if ok_rec:
                                        self.pending_bets.clear() # Mutual Exclusion: Clear scanner bets when recovery fires
                                        self._handle_successful_buy("Recovery", opp_side, rec_cost, rec_shares, rec_price, is_l)
                                        self.log_msg(f"[bold green]RECOVERY EXECUTED:[/] {msg_rec}")
                                        self.update_balance_ui() # Refresh bankroll display
                                    else:
                                        self.log_msg(f"[bold red]RECOVERY FAILED:[/] {msg_rec}")

    async def _check_hdo(self):
        """
        Hedge Direction Opposite evaluates if we need to enter an offset trade to protect portfolio delta.
        v5.9.5: Refactored for single-fire per window and net exposure hedging.
        """
        if self.hdo_fired_in_window: return
        
        # Check if HDO is active via weights / existence
        hdo_scanner = self.scanners.get("HDO")
        if not hdo_scanner: return
        
        hdo_weight = self.scanner_weights.get("HDO", 0.0)
        if hdo_weight <= 0: return # Consider weight 0 as inactive
        
        # Check if actually enabled in UI
        if not self.query_one("#cb_hdo").value: return
        
        hdo_threshold = getattr(hdo_scanner, "trigger_threshold", 0.59)
        is_l = self.query_one("#cb_live").value

        # 1. Calculate Total Net Exposure for the Window
        # We need to know the total dollar amount invested in UP vs DOWN.
        net_exposure = {"UP": 0.0, "DOWN": 0.0}
        for info in self.window_bets.values():
            if not isinstance(info, dict) or info.get("closed"): continue
            if info.get("algorithm") == "HDO": continue 
            
            side = info["side"]
            cost = info["cost"]
            net_exposure[side] += cost

        # 2. Check if either side's opposite is threatening
        sides_to_check = []
        if net_exposure["DOWN"] > net_exposure["UP"]:
            sides_to_check.append(("DOWN", net_exposure["DOWN"] - net_exposure["UP"]))
        elif net_exposure["UP"] > net_exposure["DOWN"]:
            sides_to_check.append(("UP", net_exposure["UP"] - net_exposure["DOWN"]))

        for threatened_side, net_amt in sides_to_check:
            opp_side = "UP" if threatened_side == "DOWN" else "DOWN"
            opp_ask = self.market_data["up_ask"] if opp_side == "UP" else self.market_data["down_ask"]

            if opp_ask >= hdo_threshold:
                # threshold crossed! We execute ONE HEDGE for the ENTIRE net position.
                self.hdo_fired_in_window = True # Latch immediately
                
                self.log_msg(f"[bold magenta]🚨 HDO TRIGGERED:[/] Net {threatened_side} exposure of ${net_amt:.2f} threatened. {opp_side} ask crossed {hdo_threshold*100:.1f}¢!", level="ADMIN")
                
                # Formula: We want to buy enough shares such that profit covers net_amt
                target_shares = net_amt / (1.00 - opp_ask)
                hedge_bet_size = target_shares * opp_ask
                
                # Apply HDO Scanner Weight
                hdo_weight = self.scanner_weights.get("HDO", 1.0)
                hedge_bet_size *= hdo_weight

                # Final safety caps
                if hedge_bet_size > self.risk_manager.risk_bankroll:
                    hedge_bet_size = self.risk_manager.risk_bankroll
                    self.log_msg(f"[yellow]HDO CAP:[/] Venture ${hedge_bet_size:.2f} max (Full Bankroll)", level="ADMIN")
                
                if hedge_bet_size >= 0.50:
                    self.log_msg(f"[bold magenta]HDO EXECUTION:[/] Hedging ${net_amt:.2f} {threatened_side} w/ ${hedge_bet_size:.2f} {opp_side} @ {opp_ask*100:.1f}¢", level="ADMIN")
                    
                    ok_hedge, msg_hedge, hedge_shares, hedge_price = await asyncio.to_thread(
                        self.trade_executor.execute_buy, is_l, opp_side, hedge_bet_size, opp_ask, 
                        self.market_data["up_id" if opp_side=="UP" else "down_id"], 
                        context={}, reason="HDO_Hedge_Total"
                    )
                    
                    if ok_hedge:
                        self._handle_successful_buy("HDO", opp_side, hedge_bet_size, hedge_shares, hedge_price, is_l)
                        self.log_msg(f"[bold green]HDO HALT:[/] Multi-trade hedge complete. All scanning suspended for window.", level="ADMIN")
                        self.update_balance_ui()
                    else:
                        self.log_msg(f"[bold red]HDO FAILED:[/] {msg_hedge}", level="ERROR")
                        self.hdo_fired_in_window = False # UNLATCH to allow retry
                return 

    async def _check_whale_shield(self):
        """Periodic check for Whale Shield emergency escape near end of window."""
        try:
            if not self.query_one("#cb_whale").value: return
            if self.last_second_exit_triggered: return # Already fired or window ended
            
            # Use current UI-configured values
            s_time_limit = getattr(self, "shield_time", 45)
            s_reach = getattr(self, "shield_reach", 5) / 100.0
            
            rem = max(0, self.config.WINDOW_SECONDS - int(time.time() - self.market_data["start_ts"]))
            
            if rem > s_time_limit or rem <= 0: return # Too early or already over (settlement handles end)
            
            # Check if we actually HAVE open positions to save API calls in Live
            has_open = any(not info.get("closed") for info in self.window_bets.values())
            if not has_open: return
            
            up_p = self.market_data.get("up_bid", 0.5)
            if abs(up_p - 0.50) < s_reach:
                self.log_msg(f"🛡️ WHALE SHIELD: Market too tight ({up_p*100:.1f}¢) @ T-{rem}s. Escaping.", level="MONEY")
                await self.trigger_sell_all("UP")
                await self.trigger_sell_all("DOWN")
                self.last_second_exit_triggered = True # Latch
        except Exception as e:
            self.log_msg(f"Whale Shield Err: {e}", level="ERROR")

    async def _run_last_second_exit(self, ui_is_live):
        # We find all uniquely opened trades by their side and whether they were actually LIVE or SIM
        # We group by (side, is_live) to avoid triple-logging when multiple algorithms are active on the same side.
        open_bets_grouped = set()
        for info in self.window_bets.values():
            if not info.get("closed"):
                open_bets_grouped.add((info["side"], info.get("is_live", False)))
        
        # Fallback for SIM mode manual/legacy shares not in tracked bets
        if not open_bets_grouped and not ui_is_live:
            if self.sim_broker.shares["UP"] > 0: open_bets_grouped.add(("UP", False))
            if self.sim_broker.shares["DOWN"] > 0: open_bets_grouped.add(("DOWN", False))
        
        for side, is_live in open_bets_grouped:
            tid = self.market_data["up_id" if side=="UP" else "down_id"]
            cbid = self.market_data["up_bid"] if side=="UP" else self.market_data["down_bid"]

            # Safety check: If position is currently WINNING (by delta) but Bid is low (< 30¢), 
            # do NOT panic sell at a discount. The settlement Oracle will give us the full 100¢.
            p2b = self.market_data.get("p2b", 0)
            btc = self.market_data.get("btc_price", 0)
            is_winning = (btc > p2b) if side == "UP" else (btc < p2b)
            if is_winning and cbid < 0.30:
                self.log_msg(f"[bold cyan]🛡️ SAFETY SKIP {side}:[/] Currently winning but Bid {cbid*100:.0f}¢ is low. Waiting for Settlement (100¢).", level="MONEY")
                continue

            # LIVE: Skip if position has clearly lost (bid < 10¢ with no triggered SL).
            if is_live and cbid < 0.10:
                self.log_msg(f"[dim]⏱ SKIP FINAL EXIT {side} — position at {cbid*100:.1f}¢, clearly lost. Letting expire.[/]")
                continue

            # For LIVE: User requested strict resting limit order at $0.99
            # For SIM: Perform "True Selling" at the current bid
            lp = 0.99 if is_live else cbid
            
            # CANCEL ALL RESTING TRANCHE LIMIT ORDERS FOR THIS SIDE BEFORE MARKET SELL
            if is_live:
                try: use_tranche = self.query_one("#cb_tranche").value
                except: use_tranche = False
                if use_tranche:
                    for info in self.window_bets.values():
                        if info.get("side") == side and info.get("limit_order_id") and not info.get("closed"):
                            self.trade_executor.live.cancel_limit_order(info["limit_order_id"])
                            self.log_msg(f"[dim]Cancelled resting Limit Order {info['limit_order_id'][-6:]} for End-of-Window Dump[/]")

            # Execute synchronously in a background thread to prevent UI lockup 
            ok, msg, revenue = await asyncio.to_thread(self.trade_executor.execute_sell, is_live, side, tid, lp, cbid, "Last Second Exit")
            if ok:
                self.log_msg(f"[bold {'red' if is_live else 'green'}]⏱ FINAL EXIT {side}: {msg}[/]")
                # Mark all sub-tickets in this window as closed
                for info in self.window_bets.values(): 
                    if info.get("side") == side: info["closed"] = True
                
                # Update Risk Bankroll with realized revenue
                if revenue > 0: 
                    self._add_risk_revenue(revenue)
            else:
                self.log_msg(f"[bold red]⏱ FINAL EXIT {side} FAILED:[/] {msg}")

    async def update_timer(self):
        if not getattr(self, "app_active", False): return
        # Update session runtime regardless of market data status
        run = int(time.time() - self.app_start_time)
        win_count = getattr(self, "session_windows_settled", 0)
        self.query_one("#lbl_runtime").update(f" | RUN: {run//3600:02d}:{(run%3600)//60:02d}:{run%60:02d} | Win: #{win_count}")

        if not self.market_data["start_ts"]: return
        
        rem = max(0, self.config.WINDOW_SECONDS - int(time.time() - self.market_data["start_ts"]))
        self.time_rem_str = f"{rem//60:02d}:{rem%60:02d}"
        self.query_one("#lbl_timer_big").update(self.time_rem_str)
        
        # Update window start time in human-readable format
        from datetime import datetime
        start_dt = datetime.fromtimestamp(self.market_data["start_ts"])
        self.query_one("#lbl_window_start").update(start_dt.strftime("%H:%M:%S"))
        
        # Safety Exit at T-5s (User requested: virtual selling should occur before end)
        # Linked to #cb_whale setting to prevent unauthorized panic exits.
        if rem <= 5 and not self.last_second_exit_triggered and self.query_one("#cb_whale").value:
            self.last_second_exit_triggered = True
            await self._run_last_second_exit(self.query_one("#cb_live").value)

        # --- ADV MOM Analytics: 60s Pre-Open Velocity ---
        if rem == 60 and self.mom_analytics["btc_pre_60s"] is None:
            self.mom_analytics["btc_pre_60s"] = self.market_data.get("btc_price", 0)

        # --- NEXT WINDOW PREVIEW ---
        # 20 seconds before end, fetch the NEXT window's UP/DOWN prices and log them.
        # Next slug = btc-updown-5m-{current_start_ts + 300}
        if rem <= 20 and not self.next_window_preview_triggered and self.market_data["start_ts"] > 0:
            self.next_window_preview_triggered = True
            next_ts = self.market_data["start_ts"] + self.config.WINDOW_SECONDS
            next_slug = f"btc-updown-{self.config.MARKET_FREQ}m-{next_ts}"
            def _fetch_next():
                if not getattr(self, "app_active", False): return
                try:
                    # Initialize local variables to prevent UnboundLocalError
                    if not getattr(self, "app_active", False): return
                    d = self.market_data_manager.fetch_polymarket(next_slug)
                    if not getattr(self, "app_active", False): return
                    up_bid  = d.get("up_bid",  0)
                    dn_bid  = d.get("down_bid", 0)
                    up_ask  = d.get("up_ask",  0)
                    dn_ask  = d.get("down_ask", 0)
                    if up_bid > 0 or dn_bid > 0:
                        fmt_msg = (
                            f"NEXT: "
                            f"UP {up_bid*100:.1f}/{up_ask*100:.1f}c | "
                            f"DN {dn_bid*100:.1f}/{dn_ask*100:.1f}c"
                        ).replace(".0/", "/").replace(".0c", "c")
                        self.safe_call(self.log_msg, fmt_msg)
                    else:
                        self.safe_call(self.log_msg, f"[dim]🔭 Next window not yet available ({next_slug})[/]")
                except Exception as e:
                    self.safe_call(self.log_msg, f"[dim]🔭 Next window fetch failed: {e}[/]")
            threading.Thread(target=_fetch_next, daemon=True).start()
        # ---------------------------

        # --- PRE-BUY NEXT WINDOW (rem <= 15, MOM Pre-Buy or Hybrid mode) ---
        if (rem <= 15 and not self.pre_buy_triggered
                and self.mom_buy_mode in ["PRE", "HYBRID", "ADV"]
                and self.market_data["start_ts"] > 0
                and self.query_one("#cb_mom").value):
            self.pre_buy_triggered = True
            next_ts   = self.market_data["start_ts"] + self.config.WINDOW_SECONDS
            next_slug = f"btc-updown-{self.config.MARKET_FREQ}m-{next_ts}"
            is_live   = self.query_one("#cb_live").value
            try: ui_amt = float(self.query_one("#inp_amount").value)
            except: ui_amt = 1.0
            is_pct = self.query_one("#rs_bet_mode").pressed_button and self.query_one("#rs_bet_mode").pressed_button.id == "rb_pct"
            trend = self.market_data_manager.trend_1h  # "UP" / "DOWN" / "NEUTRAL"

            self.log_msg(f"[dim]🚀 PRE-BUY initiated at T-{rem:.0f}s (mode={self.mom_buy_mode}) — fetching next window...[/]")

            def _do_prebuy():
                if not getattr(self, "app_active", False): return
                try:
                    # Initialize local variables to prevent UnboundLocalError
                    if not getattr(self, "app_active", False): return
                    d = self.market_data_manager.fetch_polymarket(next_slug)
                    if not getattr(self, "app_active", False): return
                    up_ask = d.get("up_ask", 0)
                    dn_ask = d.get("down_ask", 0)
                    if up_ask <= 0 and dn_ask <= 0:
                        self.safe_call(self.log_msg, "[dim]🚀 PRE-BUY skipped — next window prices unavailable[/]")
                        return
                    
                    # Bet Sizing Logic explicitly for Pre-Buy
                    if is_pct:
                        pre_bs = self.risk_manager.window_start_bankroll * (ui_amt / 100.0)
                    else:
                        pre_bs = ui_amt

                    # Calculate BTC Velocity and RSI
                    btc_open = self.market_data.get("btc_open", 0)
                    btc_pre_60s = self.mom_analytics.get("btc_pre_60s")
                    velocity = (btc_open - btc_pre_60s) if btc_open and btc_pre_60s else 0
                    
                    rsi_1m = 50.0
                    try:
                        closes, _, _, _ = self.market_data_manager.fetch_candles_60m()
                        if closes:
                            try:
                                from .market import calculate_rsi
                            except ImportError:
                                from market import calculate_rsi
                            rsi_1m = calculate_rsi(closes, period=14)
                    except:
                        pass

                    # Build Context for Scanners
                    context = {
                        "elapsed": 285, # Hardcoded T-15s for pre-buys
                        "up_bid": self.market_data.get("up_bid", 0),
                        "down_bid": self.market_data.get("down_bid", 0),
                        "up_ask": up_ask,
                        "down_ask": dn_ask,
                        "atr_5m": getattr(self.market_data_manager, "atr_5m", None) or self.market_data.get("atr_5m", 0),
                        "trend_1h": self.market_data_manager.trend_1h,
                        "odds_score": round((self.market_data.get("up_bid", 0) - self.market_data.get("down_bid", 0)) * 100, 1),
                        "rsi_1m": rsi_1m,
                        "velocity": velocity,
                        "window_analytics": self.mom_analytics
                    }
                    
                    # Log Context
                    price_diff = up_ask - dn_ask
                    _atr = context["atr_5m"]
                    _atr_floor = self.scanners.get("Momentum") and self.scanners["Momentum"].adv_settings.get("atr_floor", 25.0) or 25.0
                    if self.mom_analytics["pre_15s_gap"] is None:
                        self.mom_analytics["pre_15s_gap"] = price_diff
                        self.mom_analytics["btc_pre_15s"] = self.market_data.get("btc_price", 0)
                    self.safe_call(self.log_msg, f"[dim]DEBUG PRE-BUY: UP ask={up_ask*100:.1f}¢, DN ask={dn_ask*100:.1f}¢, diff={price_diff*100:.1f}¢, abs={abs(price_diff)*100:.1f}¢, ATR={_atr:.1f} (floor={_atr_floor:.1f})[/]")

                    # In suspended (mid-round lockout) mode: show prices but skip all scanner/execution logic
                    if self.mid_window_lockout:
                        return

                    any_pre_buy_fired = False
                    
                    manual_side = getattr(self, "manual_pre_buy_queue", None)
                    if manual_side:
                        self.manual_pre_buy_queue = None
                        class _ManualScan:
                            def get_signal(self, ctx): return f"PRE_BUY_{manual_side}|Manual Admin Override"
                        scanner_items = [("Manual", _ManualScan())]
                    else:
                        scanner_items = self.scanners.items()
                        
                    for algo_id, scanner in scanner_items:
                        if algo_id != "Manual":
                            # Only run scanners that are enabled in the UI
                            try:
                                # Special handling for Momentum since it has different checkbox structure
                                if algo_id.lower() == "momentum":
                                    checkbox_id = "#cb_mom"
                                else:
                                    checkbox_id = f"#cb_{algo_id.lower()}"
                                    
                                checkbox_value = self.query_one(checkbox_id).value
                                if not checkbox_value:
                                    continue
                            except Exception as e:
                                # If checkbox not found, skip this scanner
                                continue

                        # Inject current runtime settings into scanner before calling
                        if hasattr(scanner, "buy_mode"):
                            scanner.buy_mode = self.mom_buy_mode
                        if hasattr(scanner, "adv_settings"):
                            scanner.adv_settings = self.mom_adv_settings

                        # Clear any stale BET_ signal so the pre-buy block isn't bypassed
                        # (in PRE mode mid-window BET_ signals are blocked from executing
                        # but still stored on the scanner — they'd short-circuit get_signal)
                        if hasattr(scanner, "triggered_signal") and scanner.triggered_signal:
                            if "BET_" in str(scanner.triggered_signal):
                                scanner.triggered_signal = None
                                if hasattr(scanner, "pre_buy_triggered"):
                                    scanner.pre_buy_triggered = False

                        if not getattr(self, "app_active", False): return
                        signal = scanner.get_signal(context)
                        if getattr(scanner, "last_skip_reason", None):
                            self.safe_call(self.log_msg, f"[dim]{algo_id} PRE-BUY skipped: {scanner.last_skip_reason}[/]")
                            scanner.last_skip_reason = None # Clear

                        if signal.startswith("PRE_BUY_"):
                            any_pre_buy_fired = True
                            # Parsed format: PRE_BUY_UP|Reason
                            parts = signal.split("|")
                            action = parts[0]
                            reason = parts[1] if len(parts) > 1 else "Scanner Signal"
                            
                            side = "UP" if "UP" in action else "DOWN"
                            price = up_ask if side == "UP" else dn_ask
                            
                            token_id = d.get("up_id" if side == "UP" else "down_id")
                            
                            # Use variables cached from outside the thread
                            if is_pct:
                                pre_bs = self.risk_manager.window_start_bankroll * (ui_amt / 100.0)
                            else:
                                pre_bs = ui_amt
                                
                            weight = self.scanner_weights.get(algo_id[:3].upper(), 1.0)
                            pre_bs = pre_bs * weight
                            
                            # Apply Confidence Tiers
                            t4 = self.market_data_manager.trend_1h
                            trend_bad = (t4 != 'NEUTRAL' and side not in t4)
                            if trend_bad:
                                pre_bs = 1.00 # Drop to minimum bet on low confidence
                            if pre_bs > self.risk_manager.risk_bankroll: pre_bs = self.risk_manager.risk_bankroll
                                
                            # Enforce Global Window Cap for Pre-Buy
                            # (Note: total_window_cost is usually 0 here since it's the very start of a window boot)
                            # But we check anyway for consistency.
                            total_window_cost = sum(info.get("cost", 0) for info in self.window_bets.values())
                            remaining_cap = max(0, getattr(self, "total_risk_cap", 30.0) - total_window_cost)
                            if pre_bs > remaining_cap:
                                pre_bs = remaining_cap
                                if pre_bs < 1.00:
                                    self.safe_call(self.log_msg, f"[yellow]PRE-BUY ABORTED:[/] Risk Cap Reached (${total_window_cost:.2f}/$30)")
                                    return

                            if pre_bs < 1.00: pre_bs = 1.00 # hard floor for execution

                            self.safe_call(self.log_msg, f"[dim]{algo_id} PRE-BUY Trigger: {side} ({reason})[/]")

                            if not getattr(self, "app_active", False): return
                            try:
                                ok, msg, act_shares, act_price = self.trade_executor.execute_buy(
                                    is_live, side, pre_bs, price, token_id,
                                    context={}, reason=f"{algo_id}_PreBuy_{reason}"
                                )
                                if ok:
                                    self.session_total_trades += 1
                                    self.risk_manager.register_bet(pre_bs)
                                    # SET IMMEDIATELY to avoid race condition with window start promotion
                                    self.pre_buy_pending = {"side": side, "entry": act_price, "cost": pre_bs, "shares": act_shares, "algorithm": algo_id, "slug": next_slug, "reason": reason}
                                    self.safe_call(self.log_msg, f"[bold green]🚀 PRE-BUY EXECUTED:[/] {side} @ {act_price*100:.1f}¢ | ${pre_bs:.2f} committed. {reason}. Holding for next window ({next_slug})[/]")
                                    self.safe_call(self.update_balance_ui)
                                else:
                                    self.safe_call(self.log_msg, f"[bold red]🚀 PRE-BUY FAILED:[/] {msg}")
                            except Exception as e:
                                import traceback
                                err_info = traceback.format_exc()
                                self.safe_call(self.log_msg, f"[bold red]🚀 PRE-BUY THREAD CRASHED:[/] {e}\n{err_info}", level="ERROR")
                    
                    if not any_pre_buy_fired:
                        self.safe_call(self.log_msg, f"[dim]🚀 PRE-BUY: No scanner fired a signal (mode={self.mom_buy_mode})[/]")

                    # Always print detailed PBN analysis if generated during this run, regardless of execution
                    for scanner_name in ["Momentum", "MM2"]:
                        if scanner_name in self.scanners and hasattr(self.scanners[scanner_name], 'pbn_analysis') and self.scanners[scanner_name].pbn_analysis:
                            analysis = self.scanners[scanner_name].pbn_analysis
                            self.safe_call(self.log_msg, f"[DEBUG] Found {scanner_name} PBN analysis with {len(analysis.get('factors', []))} factors")
                            
                            # Use safe dictionary fallbacks
                            d_decision = analysis.get('decision') or 'SKIP'
                            d_conf = analysis.get('confidence') or 'NONE'
                            d_score = analysis.get('net_score', 0)
                            d_up = analysis.get('up_score', 0)
                            d_dn = analysis.get('down_score', 0)
                            d_reason = analysis.get('reason', 'None')
                            d_factors = analysis.get('factors', [])

                            self.safe_call(self.log_msg, f"[bold cyan]🧠 PBN MULTI-FACTOR ANALYSIS:[/]")
                            self.safe_call(self.log_msg, f"[dim]  Decision: {d_decision} | Confidence: {d_conf} | Score: {d_score:+d}[/]")
                            self.safe_call(self.log_msg, f"[dim]  UP Score: {d_up} | DOWN Score: {d_dn}[/]")
                            if d_factors:
                                self.safe_call(self.log_msg, f"[dim]  Factors:[/]")
                                for factor in d_factors:
                                    self.safe_call(self.log_msg, f"[dim]    • {factor}[/]")
                            self.safe_call(self.log_msg, f"[dim]  Final Reason: {d_reason}[/]")
                            self.safe_call(self.log_msg, f"")
                            
                            # Clear it so it doesn't print on subsequent aborted runs
                            self.scanners[scanner_name].pbn_analysis = None
                    
                except Exception as e:
                    import traceback
                    tb = traceback.format_exc()
                    self.safe_call(self.log_msg, f"[bold red]🚀 PRE-BUY THREAD CRASH:[/]\n{tb}", level="ERROR")

            threading.Thread(target=_do_prebuy, daemon=True).start()
        # ----------------------------------------------------------
            
        # Settlement Trigger removed from timer logic. 
        # Settlement now fires at T=0 inside fetch_market_loop.

    def _check_bankroll_exhaustion(self, net_pnl=0):
        """After each settlement, freeze the bot if it can no longer afford another bet."""
        try:
            from .ui_modals import BankrollExhaustedModal
        except ImportError:
            from ui_modals import BankrollExhaustedModal
        if self.halted: return

        br = self.risk_manager.risk_bankroll
        try: min_bet = float(self.query_one("#inp_amount").value)
        except: min_bet = 1.0
        hard_floor = 1.0  # Absolute minimum to even consider a bet

        # Only freeze if a bet was actually placed this window (we lost) AND
        # the bankroll can no longer cover the minimum bet size.
        had_bet = bool(self.window_bets) and net_pnl < 0
        cannot_afford = br < max(min_bet, hard_floor)

        if had_bet and cannot_afford:
            self.halted = True
            is_live = self.query_one("#cb_live").value
            mode_str = "LIVE" if is_live else "SIM"

            # Final CSV snapshot
            self.dump_state_log()

            final_msg = (
                f"🔴 BOT FROZEN [{mode_str}] | Bankroll: ${br:.2f} | "
                f"Min Bet: ${min_bet:.2f} | Cannot place another trade. All scanning stopped."
            )
            self.log_msg(f"[bold red]{final_msg}[/]")

            # Write final line to console log file
            try:
                from datetime import datetime as _dt
                with open(self.console_log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*60}\nFINAL LOG — {_dt.now().strftime('%Y-%m-%d %H:%M:%S')}\n{final_msg}\n{'='*60}\n")
            except: pass

            # Show frozen modal (must run on UI thread)
            self.push_screen(BankrollExhaustedModal(br, min_bet, mode_str))

    def trigger_settlement(self, settlement_slug=None, settlement_strike=None):
        if self.market_data["start_ts"] == 0: return

        # 1. Poly-Decisive Logic (v5.9.4)
        # If token price is > 0.90, that side is the definitive winner regardless of BTC sync issues.
        up_bid = self.market_data.get("up_bid", 0)
        dn_bid = self.market_data.get("down_bid", 0)
        btc_p = self.market_data.get("btc_price", 0)
        if settlement_strike:
            btc_o = float(settlement_strike)
            delta = btc_p - btc_o
            delta_str = f"Δ ${delta:+.2f} (vs Strike)"
        else:
            btc_o = self.market_data.get("btc_open", 0)
            delta = btc_p - btc_o
            delta_str = f"Δ ${delta:+.2f} (vs Open)"

        if up_bid >= 0.90:
            winner = "UP"
            reason = f"Decisive ({delta_str})"
        elif dn_bid >= 0.90:
            winner = "DOWN"
            reason = f"Decisive ({delta_str})"
        else:
            winner = "UP" if btc_p >= btc_o else "DOWN"
            reason = f"BTC Move ({delta_str})"

        # Capture Inter-Window Totality Data for Intel Scanners
        hist = self.market_data_manager.price_history
        if hist:
            prices = [p['price'] for p in hist]
            vol_up = self.market_data.get("vol_up", 0)
            vol_dn = self.market_data.get("vol_dn", 0)
            
            # Simple VPOC: If UP volume dominates, POC is toward high; if DN, toward low.
            # (Better VPC would use a full price/volume profile, but this is a solid heuristic)
            poc = max(prices) if vol_up > vol_dn else (min(prices) if vol_dn > vol_up else sum(prices)/len(prices))
            
            self.last_window_data = {
                "ohlc": {"open": btc_o, "high": max(prices), "low": min(prices), "close": btc_p},
                "poc": poc,
                "drift": (up_bid - dn_bid) if abs(up_bid - dn_bid) > 0.10 else 0, # Significant basis drift
                "win": winner
            }
        
        # Deferring settlement log for audit
        # self.log_msg(f"SETTLEMENT: {winner} ({reason.capitalize()})", level="RSLT")
        
        # 2. Performance Reporting (v5.9.5 Unified Fix)
        # Calculate performance from local trackers to ensure Accuracy/Revenue is 100% correct in both SIM/LIVE.
        current_slug = f"btc-updown-{self.config.MARKET_FREQ}m-{self.market_data.get('start_ts', 0)}"
        
        # window_invested must include ALL trades (active and closed) to compute correct PnL
        window_invested = sum(info.get("cost", 0) for info in self.window_bets.values())
        
        # Validate for potential calculation errors
        if window_invested <= 0:
            self.log_msg(f"[yellow]WARNING: Window invested is ${window_invested:.2f} - checking trade data[/]", level="STATS")
            for trade_id, info in self.window_bets.items():
                cost = info.get("cost", 0)
                entry = info.get("entry", 0)
                self.log_msg(f"  Trade {trade_id}: cost=${cost:.2f}, entry=${entry:.4f}, closed={info.get('closed', False)}", level="STATS")
        
        # settlement_pay only calculates revenue from trades STILL OPEN at the final second
        active_bets = [info for info in self.window_bets.values() if not info.get("closed")]
        settlement_pay = 0
        for info in active_bets:
            if info.get("side") == winner:
                cost = info.get("cost", 0)
                entry = info.get("entry", 0)
                if entry > 0:
                    shares = cost / entry
                    settlement_pay += shares
                else:
                    self.log_msg(f"[red]ERROR: Trade has entry price of ${entry:.4f} - cost=${cost:.2f}[/]", level="ERROR")
        
        total_window_revenue = settlement_pay + self.window_realized_revenue
        net_pnl = total_window_revenue - window_invested
        
        # Check for infinity or NaN issues
        if not (-1000000 <= net_pnl <= 1000000) or net_pnl != net_pnl:  # NaN check
            self.log_msg(f"[red]CRITICAL ERROR: PnL calculation issue - net_pnl={net_pnl}[/]", level="ERROR")
            self.log_msg(f"  settlement_pay={settlement_pay}, window_realized_revenue={self.window_realized_revenue}, window_invested={window_invested}", level="ERROR")
            net_pnl = 0  # Fallback to prevent corruption
        
        self.session_pnl += net_pnl
        
        # --- [NEW] Session Streak Tracker ---
        if window_invested > 0:
            if net_pnl < 0: # Losing window
                self.current_loss_streak = getattr(self, "current_loss_streak", 0) + 1
            else: # Winning or Break-even window
                self.current_loss_streak = 0
        
        # --- [NEW] Odds Base Tracker (for next window) ---
        self.last_odds_base = (up_bid - dn_bid)
        
        # Payout for broker balance / risk refilling (shares at $1.00)
        payout = settlement_pay
        # Note: self.sim_broker.settle_window handles redundant local SimBroker math 
        self.sim_broker.settle_window(winner) 
        
        # REFILL RISK BANKROLL! (v5.9.6 Fix)
        # Note: payout (settlement_pay) should ONLY include revenue from active trades.
        # realized_revenue is already in the bankroll.
        self.risk_manager.register_settlement(payout, 0, grow=self.grow_riskbankroll)
        self.update_balance_ui()
        
        # Accuracy: Count settlement winners
        for info in self.window_bets.values():
            if not info.get("closed") and info.get("side") == winner and (info.get("slug") == current_slug or not info.get("slug")):
                self.session_win_count += 1
        
        self.session_windows_settled += 1

        # Accuracy Calculation for Log
        acc_val = (self.session_win_count / self.session_total_trades * 100) if self.session_total_trades > 0 else 0
        is_live = self.query_one("#cb_live").value
        main_bal = self.live_broker.balance if is_live else self.sim_broker.balance
        
        # 3. Immediate Logging (v5.9.8)
        self.log_msg(f"SETTLEMENT: {winner} ({reason.capitalize()})", level="RSLT")
        
        # Enhanced PnL breakdown for debugging
        active_bets_count = len([info for info in self.window_bets.values() if not info.get("closed")])
        closed_bets_count = len([info for info in self.window_bets.values() if info.get("closed")])
        total_bets_count = len(self.window_bets)
        
        # Log individual trades for clarity
        if self.window_bets:
            trade_details = []
            for trade_id, info in self.window_bets.items():
                side = info.get("side", "??")
                cost = info.get("cost", 0)
                entry = info.get("entry", 0)
                closed = info.get("closed", False)
                status = "CLOSED" if closed else "ACTIVE"
                if entry > 0:
                    shares = cost / entry
                    trade_details.append(f"{side}(${cost:.2f}@{entry*100:.1f}¢,{shares:.1f}shares,{status})")
                else:
                    trade_details.append(f"{side}(${cost:.2f}@0.0¢,ERROR,{status})")
            
            self.log_msg(f"TRADES: Active:{active_bets_count} Closed:{closed_bets_count} Total:{total_bets_count}", level="STATS")
            self.log_msg(f"TRADE DETAIL: {' | '.join(trade_details[:4])}", level="STATS")
            if len(trade_details) > 4:
                self.log_msg(f"MORE TRADES: +{len(trade_details)-4} additional trades", level="STATS")
        else:
            self.log_msg(f"TRADES: No trades this window", level="STATS")
        
        self.log_msg(f"PNL BREAKDOWN: Invested=${window_invested:.2f} | Revenue=${total_window_revenue:.2f} | Net=${net_pnl:+.2f}", level="STATS")
        self.log_msg(f"PNL: {'+' if net_pnl >= 0 else ''}${net_pnl:.2f} | Rev: ${total_window_revenue:.2f} | Ses: {'+' if self.session_pnl >= 0 else ''}${self.session_pnl:.2f} | Eq: ${main_bal:.1f} | Acc: {acc_val:.1f}%", level="STATS")

        # HTML Verification row is now written at T+15 after official audit
        # to ensure the most accurate data (Polymarket result + finalized delta)
        # is documented in the verification table.

        if self.session_windows_settled > 1:
            acc_val = (self.session_win_count / self.session_total_trades * 100) if self.session_total_trades > 0 else 0
            acc_str = f"{acc_val:.1f}%"
        else:
            acc_str = "N/A"

        upt = int(time.time() - self.app_start_time)
        upt_str = f"{upt//3600:02d}:{(upt%3600)//60:02d}:{upt%60:02d}"
        self.log_msg(f"PULSE: {upt_str} | Trd: {self.session_total_trades} | Acc: {acc_str}", level="ADMIN")
        
        # 4. Store for Audit at T=15 in NEXT window
        is_l = self.query_one("#cb_live").value
        pre_settle_bal = self.live_broker.balance if is_l else self.sim_broker.balance
        
        # Use a unique filename for the graph
        start_ts = self.market_data.get("start_ts", 0)
        graph_filename = f"graph_{start_ts}.png"
        
        self.audit_buffer = {
            "window_id": start_ts,
            "slug": settlement_slug or self.market_data.get("slug"),
            "pulse_result": winner,
            "strike_o": btc_o, # Use the validated baseline from above
            "open_price": self.market_data.get("btc_open", 0),
            "close_price": btc_p,
            "pnl": net_pnl,
            "graph_filename": graph_filename,
            "shares": {
                "UP": sum(info.get("cost", 0)/info.get("entry", 0.5) for info in self.window_bets.values() if info.get("side") == "UP"),
                "DOWN": sum(info.get("cost", 0)/info.get("entry", 0.5) for info in self.window_bets.values() if info.get("side") == "DOWN")
            }
        }
        
        
        # [FIXED] Removed redundant _add_risk_revenue(payout) call as it is already handled 
        # by risk_manager.register_settlement above.

        # --- BANKROLL EXHAUSTION CHECK ---
        self._check_bankroll_exhaustion(net_pnl=net_pnl)
        if self.halted: return

        # 5. [REMOVED] Bankroll Refill Logic
        # Bankrolls now organically shrink during standard sessions. Refills
        # should only happen when a trade wins and explicitly returns funds via _add_risk_revenue.

        # --- TRIGGER GRAPH SAVE ---
        try:
            log_dir = os.path.dirname(self.sim_broker.log_file)
            graphs_dir = os.path.join(log_dir, "graphs")
            os.makedirs(graphs_dir, exist_ok=True)
            
            graph_path = os.path.join(graphs_dir, graph_filename)
            try:
                chart = self.query_one("#pulse_lean_chart")
                if chart.save_graph_image(graph_path):
                    self.log_msg(f"[dim]Saved window graph to graphs/{os.path.basename(graph_path)}[/]")
                    # Parallel FTP Upload
                    if self.log_settings.get("verification_html", True):
                        self.ftp_manager.upload_graph(graph_path, graph_filename)
                else:
                    self.log_msg(f"[red]Chart save logic failed for graphs/{os.path.basename(graph_path)}[/]")
            except Exception as e:
                self.log_msg(f"[red]Chart query error: {e}[/]")
        except Exception as e:
            self.log_msg(f"[red]Graph save path error: {e}[/]")

        self.risk_manager.reset_window(); self.last_second_exit_triggered = False
        self.update_balance_ui(); self.window_bets.clear(); self.window_realized_revenue = 0.0
        for s in self.scanners.values(): s.reset()
        self.market_data_manager.reset_history()

        # --- Write Momentum Analytics (v5.9.4) (Conditional if enabled) ---
        if not getattr(self, "log_settings", {}).get("momentum_csv", True):
            return

        try:
            ma = self.mom_analytics
            btc_open = self.market_data.get("btc_open", 0)
            btc_pre_60 = ma.get("btc_pre_60s")
            velocity = (btc_open - btc_pre_60) if btc_open and btc_pre_60 else 0
            
            dd_up = (btc_open - ma["window_low"]) if btc_open and ma["window_low"] else 0
            dd_dn = (ma["window_high"] - btc_open) if btc_open and ma["window_high"] else 0

            # 1m RSI and Volume
            rsi_1m, vol_1m = 50.0, 0.0
            try:
                closes, _, _, raw = self.market_data_manager.fetch_candles_60m()
                if closes:
                    try:
                        from .market import calculate_rsi
                    except ImportError:
                        from market import calculate_rsi
                    rsi_1m = calculate_rsi(closes, period=14)
                    if len(raw) >= 2:
                        vol_1m = float(raw[-2][5]) # Index 5 is volume
            except: pass

            line = (
                f"{self.market_data['start_ts']},"
                f"{ma['pre_15s_gap'] if ma['pre_15s_gap'] is not None else ''},"
                f"{ma['btc_pre_15s'] if ma['btc_pre_15s'] is not None else ''},"
                f"{ma['btc_pre_60s'] if ma['btc_pre_60s'] is not None else ''},"
                f"{velocity:.2f},"
                f"{ma['gap_5s'] if ma['gap_5s'] is not None else ''},"
                f"{ma['btc_5s'] if ma['btc_5s'] is not None else ''},"
                f"{ma['gap_10s'] if ma['gap_10s'] is not None else ''},"
                f"{ma['btc_10s'] if ma['btc_10s'] is not None else ''},"
                f"{ma['gap_15s'] if ma['gap_15s'] is not None else ''},"
                f"{ma['btc_15s'] if ma['btc_15s'] is not None else ''},"
                f"{ma['spread_15s'] if ma['spread_15s'] is not None else ''},"
                f"{ma['up_bid_15s'] if ma['up_bid_15s'] is not None else ''},"
                f"{ma['down_bid_15s'] if ma['down_bid_15s'] is not None else ''},"
                f"{ma['first_55c_side'] or ''},{ma['first_55c_time'] if ma['first_55c_time'] is not None else ''},"
                f"{ma['first_60c_side'] or ''},{ma['first_60c_time'] if ma['first_60c_time'] is not None else ''},"
                f"{ma['first_65c_side'] or ''},{ma['first_65c_time'] if ma['first_65c_time'] is not None else ''},"
                f"{rsi_1m:.2f},{vol_1m:.0f},"
                f"{dd_up:.2f},{dd_dn:.2f},"
                f"{self.market_data_manager.atr_5m:.2f},"
                f"{btc_open:.2f},"
                f"{self.market_data.get('btc_price', 0):.2f},"
                f"{winner}"
            )
            with open(self.mom_adv_log_file, 'a') as f:
                f.write(line + "\n")
        except Exception as e:
            self.log_msg(f"[yellow]MOM Analytics Log Error: {e}[/]")

        self.mom_analytics = self._reset_mom_analytics()

        self.log_msg("────────────────── WINDOW END ──────────────────", level="ADMIN")
        self.log_msg("") # Whitespace after window end

    def _add_risk_revenue(self, amount):
        """Adds revenue back to the usable bankroll with strict wallet clamping."""
        if not self.risk_initialized: return
        
        is_live = self.query_one("#cb_live").value
        main_bal = self.live_broker.balance if is_live else self.sim_broker.balance

        # 1. Add revenue to current bankroll
        self.risk_manager.risk_bankroll += amount
        self.window_realized_revenue += amount  # track for settlement log

        # 2. Allow compounding if grow_riskbankroll is True.
        # Otherwise, clamp risk_bankroll back down to the target ceiling.
        if getattr(self, "grow_riskbankroll", False):
            if self.risk_manager.risk_bankroll > self.risk_manager.target_bankroll:
                old_target = self.risk_manager.target_bankroll
                self.risk_manager.target_bankroll = self.risk_manager.risk_bankroll
                if is_live:
                    self.log_msg(f"[bold green]Compounding:[/] Bankroll Target Ceiling rose from {old_target:.2f} -> {self.risk_manager.target_bankroll:.2f}")
        else:
            if self.risk_manager.risk_bankroll > self.risk_manager.target_bankroll:
                self.risk_manager.risk_bankroll = self.risk_manager.target_bankroll

        # 3. Always cap by actual wallet balance (live balance updates via API)
        if is_live:
            self.live_broker.update_balance()
            main_bal = self.live_broker.balance
        if self.risk_manager.risk_bankroll > main_bal:
            self.risk_manager.risk_bankroll = main_bal
            if is_live and self.risk_manager.target_bankroll > main_bal:
                self.risk_manager.target_bankroll = main_bal
           
        self.update_balance_ui()

    async def trigger_buy(self, side):
        if hasattr(self, "_last_manual_buy") and time.time() - self._last_manual_buy < 2.0:
            return self.log_msg("[yellow]Manual Buy Debounce Active...[/]")
        self._last_manual_buy = time.time()
        
        try: val = float(self.query_one("#inp_amount").value)
        except: return self.log_msg("[red]Invalid Amount[/]")
        if self.risk_initialized and val > self.risk_manager.risk_bankroll + 0.01: return self.log_msg("[red]Insuff Risk Cap[/]")
        is_l = self.query_one("#cb_live").value
        pr = self.market_data["up_ask" if side=="UP" else "down_ask"]
        if is_l and pr >= 0.98: return self.log_msg("[red]Price too high[/]")
        tid = self.market_data["up_id" if side=="UP" else "down_id"]
        
        # Manual Context
        ctx = {
            'signal_price': self.market_data.get('btc_price', 0),
            'rsi': self.market_data.get('rsi', 0),
            'trend': self.market_data_manager.trend_1h,
            'risk_bal': self.risk_manager.risk_bankroll
        }
        
        ok, msg, act_shares, act_price = self.trade_executor.execute_buy(is_l, side, val, pr or 0.5, tid, context=ctx, reason="Manual")
        if ok:
            self.session_total_trades += 1 # Manual Buy
            self.log_msg(f"[bold {'red' if is_l else 'green'}]{msg}[/]")
            self._handle_successful_buy("Manual", side, val, act_shares, act_price, is_l)
        else:
            self.log_msg(f"[bold red]MANUAL BUY FAILED:[/] {msg}")
            
        self.update_balance_ui(); self.update_sell_buttons()

    async def trigger_sell_all(self, side):
        is_l = self.query_one("#cb_live").value
        tid = self.market_data["up_id" if side=="UP" else "down_id"]
        # Use simple ternary for bid to avoid confusion
        cbid = self.market_data["up_bid"] if side=="UP" else self.market_data["down_bid"]
        lp = cbid if not is_l else max(0.02, cbid-0.02)
        
        # Cancel resting limit orders
        if is_l:
            try: use_tranche = self.query_one("#cb_tranche").value
            except: use_tranche = False
            if use_tranche:
                for info in self.window_bets.values():
                    if info.get("side") == side and info.get("limit_order_id") and not info.get("closed"):
                        self.trade_executor.live.cancel_limit_order(info["limit_order_id"])
                        self.log_msg(f"[dim]Cancelled resting Limit Order {info['limit_order_id'][-6:]} for Manual Dump[/]")

        # Debug shares in sim mode
        if not is_l:
            s_shares = self.sim_broker.shares.get(side, 0.0)
            if s_shares <= 0:
                self.log_msg(f"[dim]Admin:[/] Manual Sell {side} requested but local shares = {s_shares:.2f}")

        ok, msg, revenue = self.trade_executor.execute_sell(is_l, side, tid, lp, cbid, reason="Manual")
        if ok:
            self.log_msg(f"[bold {'red' if is_l else 'green'}]{msg}[/]")
            if revenue > 0:
                self._add_risk_revenue(revenue)
                # Count as win if realized revenue exceeds total cost of that side
                side_cost = sum(info["cost"] for info in self.window_bets.values() if info.get("side") == side and not info.get("closed"))
                if revenue > side_cost:
                    self.session_win_count += 1
            # Mark window_bets as closed so settlement refill doesn't double-count
            for info in self.window_bets.values():
                if info.get("side") == side and not info.get("closed"):
                    info["closed"] = True
        else:
            self.log_msg(f"[bold red]MANUAL SELL FAILED:[/] {msg}")
            
        self.update_balance_ui(); self.update_sell_buttons()

    def generate_window_briefing(self):
        """Generates a 3-line start-of-window macroscopic analysis and directional guess."""
        try:
            md = self.market_data
            
            # Trend and RSI
            trend_1h = md.get("trend_1h", "NEUTRAL")
            rsi_1m = md.get("rsi_1m", getattr(self.market_data_manager, "rsi_1m", 50))
            
            if trend_1h in ["S-UP", "M-UP", "W-UP"]:
                trend_str = f"[bold green]BULLISH[/] ({trend_1h})"
            elif trend_1h in ["S-DOWN", "M-DOWN", "W-DOWN"]:
                trend_str = f"[bold red]BEARISH[/] ({trend_1h})"
            else:
                trend_str = f"[bold yellow]NEUTRAL[/] ({trend_1h})"
                
            if rsi_1m > 70:
                rsi_str = f"[bold red]Overbought ({rsi_1m:.0f})[/]"
            elif rsi_1m < 30:
                rsi_str = f"[bold green]Oversold ({rsi_1m:.0f})[/]"
            else:
                rsi_str = f"[dim]Neutral ({rsi_1m:.0f})[/]"
                
            # Context
            atr = md.get("atr_5m", 0)
            if atr > 40: vol_str = f"[bold red]HIGH[/] (ATR={atr:.0f})"
            elif atr < 20: vol_str = f"[bold green]LOW[/] (ATR={atr:.0f})"
            else: vol_str = f"[bold yellow]MODERATE[/] (ATR={atr:.0f})"
            
            btc_vel = getattr(self.market_data_manager, "btc_velocity", 0)
            if btc_vel > 20: btc_str = f"Spiking [bold green]UP (+${btc_vel:.0f})[/]"
            elif btc_vel < -20: btc_str = f"Dropping [bold red]DN (${btc_vel:.0f})[/]"
            else: btc_str = f"Stable (${btc_vel:.0f})"
            
            # Market
            odds = md.get("odds_score", 0)
            if odds > 5: odds_str = f"[bold green]favors UP (+{odds:.1f}¢)[/]"
            elif odds < -5: odds_str = f"[bold red]favors DOWN ({odds:.1f}¢)[/]"
            else: odds_str = f"balanced ({odds:.1f}¢)"
            
            up_ask = md.get("up_ask", 0)
            dn_ask = md.get("down_ask", 0)
            imb = (up_ask - dn_ask) * 100
            
            if imb > 2: imb_str = f"[bold red]UP premium (+{imb:.1f}¢)[/]"
            elif imb < -2: imb_str = f"[bold green]DN premium ({imb:.1f}¢)[/]"
            else: imb_str = f"balanced spread ({imb:.1f}¢)"
            
            # Guess scoring
            up_score, dn_score = 0, 0
            if "UP" in trend_1h: up_score += 1
            if "DOWN" in trend_1h: dn_score += 1
            if rsi_1m < 30: up_score += 1
            if rsi_1m > 70: dn_score += 1
            if odds > 5: up_score += 1
            if odds < -5: dn_score += 1
            if imb < -2: up_score += 1
            if imb > 2: dn_score += 1
            
            net = up_score - dn_score
            md["net_guess_score"] = net
            if net >= 2: guess = "[bold green]UP[/]"
            elif net <= -2: guess = "[bold red]DOWN[/]"
            else: guess = "[bold yellow]NEUTRAL / CHOP[/]"

            self.log_msg("\n[bold purple]📊 WINDOW BRIEFING (T-05:00)[/]")
            self.log_msg(f"[bold purple]1. Trend:[/] 1H is {trend_str}, 1m RSI is {rsi_str}.")
            self.log_msg(f"[bold purple]2. Context:[/] BTC is {btc_str}, Volatility is {vol_str}.")
            self.log_msg(f"[bold purple]3. Market:[/] Odds {odds_str}, Ask is {imb_str}.")
            self.log_msg(f"[bold purple]🔮 MY GUESS:[/] {guess}")
            self.log_msg("[bold purple]────────────────────────────[/]")
        except Exception as e:
            self.log_msg(f"[dim]Briefing Error: {e}[/]")
