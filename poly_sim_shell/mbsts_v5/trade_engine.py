import time
import asyncio
import threading
import concurrent.futures
from datetime import datetime, timezone

from .config import TradingConfig
from .market import calculate_rsi, calculate_bb, calculate_atr


class TradeEngineMixin:
    """
    Mixin class containing all trade execution, settlement, TP/SL,
    pre-buy, and timer logic for SniperApp.
    
    All methods reference `self` which is the SniperApp instance at runtime.
    """

    async def fetch_market_loop(self):
        if self.halted: return  # Bot frozen — bankroll exhausted
        try:
            now = datetime.now(timezone.utc); floor = (now.minute // 5) * 5
            ts_start = int(now.replace(minute=floor, second=0, microsecond=0).timestamp())
            
            # Map scanner names to their UI checkbox IDs
            scanner_map = {name: f"#cb_{name.lower()}" for name in self.scanners}
            
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
                
                self.market_data["start_ts"] = ts_start # Latch immediately to prevent double-trigger
                self.sim_broker.promote_prebuy()  # Move any pre-buy shares/costs to current window
                now_ts = time.time()
                wall_time = datetime.fromtimestamp(now_ts).strftime('%H:%M:%S')
                self.log_msg(f"[{wall_time}] ════════ NEW WINDOW #{ts_start} STARTING ════════", level="ADMIN")
                
                self.window_settled = False # reset latch for new window
                self.last_second_exit_triggered = False # reset latch for late exits
                self.next_window_preview_triggered = False # reset next-window preview latch
                self.pre_buy_triggered = False # reset pre-buy latch for new window
                self.window_realized_revenue = 0.0 # reset revenue tracker for new window
                
                # Transfer any pre-buy position into window_bets so TP/SL monitors it
                if self.pre_buy_pending:
                    sd = self.pre_buy_pending.get("side", "??")
                    key = f"Momentum_PreBuy_{time.time()}"
                    self.window_bets[key] = self.pre_buy_pending
                    # Note: Shares are promoted by sim_broker.promote_prebuy() above.
                    self.pre_buy_pending = None
                    self.log_msg(f"[bold cyan]🚀 PRE-BUY {sd} transferred to new window — now under TP/SL monitoring[/]")

                self.skipped_logs.clear() # reset the spam preventer
                self.pending_bets.clear() # discard any stale pending bets from last window
                for sc in self.scanners.values(): sc.reset() # reset all scanner signals/timers
                
                if self.mid_window_lockout:
                    self.mid_window_lockout = False
                    self.log_msg("[bold green]Lockout Lifted. Clean Window Started. Trading Enabled.[/]")

            # Calculate correct elapsed time using the actual window start
            elapsed = int(now.timestamp()) - ts_start
            # Moved self.market_data["start_ts"] = ts_start up to the is_new_window block for race safety
            
            # Mid-Window Safety Lockout Activation (If booting the bot deeply into a round)
            if is_first_tick and elapsed > 10:
                self.mid_window_lockout = True
                self.log_msg(f"[bold yellow]Booted Mid-Round ({elapsed}s elapsed). Waiting for next clean window to start trading...[/]")
                
            # Initial 10-second Lockout (prevents instant execution before APIs stabilize)
            is_initial_lockout = elapsed < 10
            slug = f"btc-updown-5m-{ts_start}"
            
            # Fetch Kraken Open Price instantly to avoid API lag from other services
            cur = await asyncio.to_thread(self.market_data_manager.fetch_current_price)
            opn = await asyncio.to_thread(self.market_data_manager.update_history, cur, ts_start, elapsed)
            
            if is_new_window:
                if self.query_one("#cb_live").value:
                    self.live_broker.update_balance()
                
                # Check for active positions inherited (like pre-buys)
                active_str = ""
                open_bets = [info for info in self.window_bets.values() if not info.get("closed")]
                if open_bets:
                    unique_sides = sorted(list(set(info["side"] for info in open_bets)))
                    active_str = f" | [bold green]Active: {', '.join(unique_sides)}[/]"
                
                self.log_msg(f"NEW WINDOW STARTED | Open: [bold white]${opn:,.2f}[/]{active_str}")

            def gather_rest():
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                    f1 = executor.submit(self.market_data_manager.update_4h_trend)
                    f2 = executor.submit(self.market_data_manager.update_1h_trend)
                    f3 = executor.submit(self.market_data_manager.fetch_candles_60m)
                    f4 = executor.submit(self.market_data_manager.fetch_polymarket, slug)
                    f1.result() # trend is just an internal state update
                    f2.result() # 1h trend is just an internal state update
                    return f3.result(), f4.result()

            candles, poly = await asyncio.to_thread(gather_rest)
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

            scanner_map = {"NPattern":"#cb_npa","Fakeout":"#cb_fak","Momentum":"#cb_mom","RSI":"#cb_rsi","TrapCandle":"#cb_tra","MidGame":"#cb_mid","LateReversal":"#cb_lat","BullFlag":"#cb_sta","PostPump":"#cb_pos","StepClimber":"#cb_ste","Slingshot":"#cb_sli","MinOne":"#cb_min","Liquidity":"#cb_liq","Cobra":"#cb_cob","Mesa":"#cb_mes","MeanReversion":"#cb_mea","GrindSnap":"#cb_gri","VolCheck":"#cb_vol","Moshe":"#cb_mos","ZScore":"#cb_zsc"}
                        # --- Check Pending Bets First ---
            if not self.mid_window_lockout and not is_initial_lockout:
                try: min_pr = float(self.query_one("#inp_min_price").value)
                except: min_pr = 0.01
                try: max_pr = float(self.query_one("#inp_max_price").value)
                except: max_pr = 0.99
                
                for name, info in list(self.pending_bets.items()):
                    # Re-check price logic
                    sd = info["side"]
                    bs = info["bs"]
                    res = info["res"]
                    pr = self.market_data["up_ask"] if sd == "UP" else self.market_data["down_ask"]
                    
                    if min_pr <= pr <= max_pr:
                        # Execution criteria met! But first, check we have enough bankroll.
                        if self.risk_manager.risk_bankroll < bs:
                            # Not enough risk bankroll - skip without logging spam
                            continue
                        is_l = self.query_one("#cb_live").value
                        ctx = {'signal_price': d["cur"], 'rsi': rsi, 'trend': self.market_data_manager.trend_4h, 'risk_bal': self.risk_manager.risk_bankroll}
                        
                        ok, msg = self.trade_executor.execute_buy(is_l, sd, bs, pr, d["poly"]["up_id" if sd=="UP" else "down_id"], context=ctx, reason=f"Pending: {res}")
                        if ok:
                            self.window_bets[f"{name}_{time.time()}"] = {"side":sd,"entry":pr,"cost":bs}
                            self.risk_manager.register_bet(bs); self.portfolios[name].record_trade(sd, pr, bs, bs/pr)
                            self.log_msg(f"[bold green]EXECUTED PENDING {name}[/]: {msg}")
                        else:
                            self.log_msg(f"[bold red]FAILED PENDING {name}[/]: {msg}")
                            
                        # Cleanup pending state regardless of result
                        del self.pending_bets[name]
                        try:
                            lbl = self.query_one(f"#lbl_{name[:3].lower()}")
                            lbl.remove_class("blinking")
                        except: pass
            # --------------------------------

                for name, sc in self.scanners.items():
                    if not self.query_one(scanner_map[name]).value: continue
                    
                    # 1. Check Signal
                    res = sc.get_signal(d) if hasattr(sc, "get_signal") else "WAIT"
                    # Backward compatibility for scanners without get_signal() wrapper
                    if res == "WAIT" and name == "NPattern": res = sc.analyze(ph, d["opn"])
                    elif res == "WAIT" and name == "Fakeout": res = sc.analyze(ph, d["opn"], "GREEN" if d["cur"] > d["opn"] else "RED")
                    elif res == "WAIT" and name == "Momentum":
                        base_t = getattr(sc, "base_threshold", sc.threshold)
                        if self.mom_buy_mode == "ADV":
                            atr = getattr(self.market_data_manager, "atr_5m", 0)
                            adj = 0
                            if atr <= self.mom_adv_settings["atr_low"]: adj = self.mom_adv_settings["stable_offset"] / 100.0
                            elif atr >= self.mom_adv_settings["atr_high"]: adj = self.mom_adv_settings["chaos_offset"] / 100.0
                            sc.threshold = base_t + adj
                        else:
                            # Standard mode uses the base directly. No UI querying here!
                            sc.threshold = base_t
                        res = sc.analyze(elapsed, d["poly"]["up_bid"], d["poly"]["down_bid"])
                    elif res == "WAIT" and name == "RSI": res = sc.analyze(rsi, d["cur"], lbb, 300-elapsed)
                    elif res == "WAIT" and name == "TrapCandle": res = sc.analyze(ph, d["opn"])
                    elif res == "WAIT" and name == "MidGame": res = sc.analyze(ph, d["opn"], elapsed, self.market_data_manager.trend_4h)
                    elif res == "WAIT" and name == "LateReversal": res = sc.analyze(ph, d["opn"], elapsed)
                    elif res == "WAIT" and name == "BullFlag": res = sc.analyze(d["c60"])
                    elif res == "WAIT" and name == "PostPump": res = sc.analyze(d["cur"], d["opn"], {})
                    elif res == "WAIT" and name == "StepClimber": res = sc.analyze(d["c60"])
                    elif res == "WAIT" and name == "Slingshot": res = sc.analyze(d["c60"])
                    elif res == "WAIT" and name == "MinOne": res = sc.analyze(ph, elapsed)
                    elif res == "WAIT" and name == "Liquidity": res = sc.analyze(d["cur"], min(d["l60"]) if d["l60"] else 0, d["opn"])
                    elif res == "WAIT" and name == "Cobra": res = sc.analyze(d["c60"], d["cur"], elapsed)
                    elif res == "WAIT" and name == "Mesa": res = sc.analyze(ph, d["opn"], elapsed)
                    elif res == "WAIT" and name == "MeanReversion": res = sc.analyze(ph, fbb, self.market_data_manager.trend_4h)
                    elif res == "WAIT" and name == "GrindSnap": res = sc.analyze(ph, elapsed)
                    elif res == "WAIT" and name == "VolCheck": res = sc.analyze(d["c60"], d["cur"], d["opn"], elapsed, d["poly"]["up_bid"], d["poly"]["down_bid"])
                    elif res == "WAIT" and name == "Moshe": res = sc.analyze(elapsed, d["cur"], d["opn"], self.market_data_manager.trend_4h, d["poly"]["up_bid"], d["poly"]["down_bid"])
                    elif res == "WAIT" and name == "ZScore": res = sc.analyze(ph, d["opn"], elapsed)

                    if res == "WAIT": continue
                    if res == "NONE":
                        reason = getattr(sc, "last_skip_reason", None)
                        if reason and f"SKIP_{name}_{reason}" not in self.skipped_logs:
                            self.log_msg(f"SKIP {name} | {reason}", level="SCAN")
                            self.skipped_logs.add(f"SKIP_{name}_{reason}")
                        continue
                        
                    if "BET_" in str(res) and not any(k.startswith(f"{name}_") for k in self.window_bets):
                        # 2. 1-Trade-Max Guard
                        if self.query_one("#cb_one_trade").value and self.window_bets: continue
                        
                        # 3. Strong Only Filter
                        if self.query_one("#cb_strong").value:
                            strong_keywords = {"STRONG", "CONFIRMED", "HEAVY", "MAX", "90", "SNIPER"}
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

                        # 5. Bet Sizing
                        bs = self.risk_manager.calculate_bet_size(str(res), self.portfolios[name].balance, self.portfolios[name].consecutive_losses, {'trend_4h':self.market_data_manager.trend_4h, 'direction':"UP" if "UP" in str(res) else "DOWN"})
                        if "MOM" in str(res):
                            if getattr(self, "mom_buy_mode", "STD") != "STD":
                                continue
                            try: bs = float(self.query_one("#inp_amount").value)
                            except: bs = self.portfolios[name].balance * 0.12
                        
                        weight = self.scanner_weights.get(name[:3].upper(), 1.0)
                        bs = bs * weight

                        # 6. Whale Protect
                        if self.query_one("#cb_whale").value:
                            max_whale = self.risk_manager.risk_bankroll * 0.25
                            if bs > max_whale:
                                self.log_msg(f"Whale Protect cap {name} ${bs:.2f} -> ${max_whale:.2f}", level="ADMIN")
                                bs = max_whale
                        
                        if bs > 0:
                            sd = "UP" if "UP" in str(res) else "DOWN"
                            pr = self.market_data["up_ask"] if sd == "UP" else self.market_data["down_ask"]
                            
                            # 7. Price Bounds
                            try: min_pr = float(self.query_one("#inp_min_price").value)
                            except: min_pr = 0.01
                            try: max_pr = float(self.query_one("#inp_max_price").value)
                            except: max_pr = 0.99
                            
                            if pr < min_pr or pr > max_pr:
                                if pr < min_pr and name not in self.pending_bets:
                                    self.pending_bets[name] = {"side": sd, "bs": bs, "res": res}
                                    try: self.query_one(f"#lbl_{name[:3].lower()}").add_class("blinking")
                                    except: pass
                                    self.log_msg(f"QUEUED {name} {sd} | Wait for {min_pr*100:.1f}c (Now {pr*100:.1f}c)", level="SCAN")
                                elif pr > max_pr:
                                    if f"SKIP_MAX_{name}" not in self.skipped_logs:
                                        self.log_msg(f"SKIP {name} | Price {pr*100:.1f}c > Max {max_pr*100:.1f}c", level="SCAN")
                                        self.skipped_logs.add(f"SKIP_MAX_{name}")
                                continue

                            # 8. Moshe Override
                            if "MOSHE_90" in str(res):
                                pr = 0.86; moshe_scanner = self.scanners.get("Moshe")
                                bs = getattr(moshe_scanner, "bet_size", 1.00)
                                if bs > self.risk_manager.risk_bankroll: bs = self.risk_manager.risk_bankroll
                                if bs <= 0.05: continue
                                self.log_msg(f"MOSHE 0.86 Override | Payout Opt: 0.99", level="ADMIN")

                            if pr and 0.01 < pr < 0.99:
                                ok, msg = self.trade_executor.execute_buy(self.query_one("#cb_live").value, sd, bs, pr, d["poly"]["up_id" if sd=="UP" else "down_id"], context={'rsi':rsi,'trend':self.market_data_manager.trend_4h}, reason=res)
                                if ok:
                                    self.window_bets[f"{name}_{time.time()}"] = {"side":sd,"entry":pr,"cost":bs,"algorithm":name}
                                    self.risk_manager.register_bet(bs); self.portfolios[name].record_trade(sd, pr, bs, bs/pr)
                                    self.session_total_trades += 1
                                    self.log_msg(f"BUY {name} {sd} @ {pr*100:.1f}c | {msg}", level="TRADE")
                                else:
                                    self.log_msg(f"BUY FAILED {name}: {msg}", level="ERROR")                            

            await self._check_tpsl()
            self.update_balance_ui(); self.update_sell_buttons()
            self.query_one("#p_up").update(f"{self.market_data['up_ask']*100:.1f}¢")
            self.query_one("#p_down").update(f"{self.market_data['down_ask']*100:.1f}¢")
            self.query_one("#p_btc").update(f"${self.market_data['btc_price']:,.2f}")
            self.query_one("#p_trend").update(f"Trend 1H: {self.market_data_manager.trend_4h}")
            self.query_one("#p_atr").update(f"ATR 5m: ${self.market_data_manager.atr_5m:.2f}")
            self.query_one("#p_btc_open").update(f"Open: ${self.market_data['btc_open']:,.2f}")
            df = self.market_data['btc_price'] - self.market_data['btc_open']
            self.query_one("#p_btc_diff").update(f"Diff: {'+' if df>=0 else '-'}${abs(df):.2f}")
            self.query_one("#p_trend").update(f"Trend 1H: {self.market_data_manager.trend_4h}")

        except Exception as e: self.log_msg(f"[red]Loop Err: {e}[/]")

    async def _check_tpsl(self):
        is_tp_active = self.query_one("#cb_tp_active").value
        tp = self.committed_tp
        sl = self.committed_sl
        for bid, info in list(self.window_bets.items()):
            if not isinstance(info, dict): continue
            if info.get("closed"): continue
            side = info["side"]; ent = info["entry"]; cur = self.market_data["up_price"] if side=="UP" else self.market_data["down_price"]
            roi = (cur-ent)/ent; reason = None
            
            # 1. Universal Max Profit (99c Guaranteed Win Exit)
            if cur >= 0.99: 
                reason = f"MAX PROFIT (99¢) | Ent: {ent*100:.1f}¢ -> {cur*100:.1f}¢ (+{roi*100:.1f}%)"
            # 2. UI-configurable TP/SL Check
            # TP is a PRICE threshold (TP 80 = sell at 80¢). Binary options cap at 99¢,
            # so ROI-based TP from a 62¢ entry would require 111¢ — never reachable.
            # SL stays ROI-based (SL 40 = cut loss when down 40% from entry).
            elif is_tp_active:
                if cur >= tp: reason = f"TP HIT | Ent: {ent*100:.1f}¢ -> {cur*100:.1f}¢ (+{roi*100:.1f}%)"
                elif roi <= -sl: reason = f"SL HIT | Ent: {ent*100:.1f}¢ -> {cur*100:.1f}¢ ({roi*100:.1f}%)"
                
            if reason:
                is_l = self.query_one("#cb_live").value
                cbid = self.market_data["up_bid"] if side=="UP" else self.market_data["down_bid"]
                lp = cbid if not is_l else max(0.02, cbid-0.02)
                ok, msg, realized_rev = await asyncio.to_thread(self.trade_executor.execute_sell, is_l, side, self.market_data["up_id" if side=="UP" else "down_id"], lp, cbid, reason=reason)
                if ok:
                    info["closed"] = True
                    realized_loss = info["cost"] - realized_rev
                    if realized_rev > 0: self._add_risk_revenue(realized_rev)
                    
                    if realized_rev > info["cost"]:
                        self.session_win_count += 1 # TP/Max Profit hit
                        self.log_msg(f"{reason} | [bold green]WIN[/] | Closed {side} @ {cur*100:.1f}c", level="MONEY")
                    else:
                        self.log_msg(f"{reason} | [bold red]LOSS[/] | Closed {side} @ {cur*100:.1f}c", level="MONEY")
                    
                    # --- SL+ RECOVERY LOGIC ---
                    # Guard: never chain recovery on a recovery bet to prevent infinite loops
                    is_recovery_bet = bid.startswith("SL+_Recovery")
                    if reason.startswith("SL HIT") and self.sl_plus_mode and realized_loss > 0 and not is_recovery_bet:
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
                                ok_rec, msg_rec = await asyncio.to_thread(self.trade_executor.execute_buy, is_l, opp_side, rec_cost, opp_p, self.market_data["up_id" if opp_side=="UP" else "down_id"], context={}, reason="SL+_Recovery")
                                if ok_rec:
                                    self.window_bets[f"SL+_Recovery_{time.time()}"] = {"side":opp_side,"entry":opp_p,"cost":rec_cost}
                                    self.risk_manager.register_bet(rec_cost)
                                    self.log_msg(f"[bold green]RECOVERY EXECUTED:[/] {msg_rec}")
                                    self.update_balance_ui() # Refresh bankroll display
                                else:
                                    self.log_msg(f"[bold red]RECOVERY FAILED:[/] {msg_rec}")

    async def _run_last_second_exit(self, is_live):
        # if not is_live: return # REMOVED: We want Sim Logic for Hypothetical Logging
        sides = set()
        if is_live: sides.update(info["side"] for info in self.window_bets.values() if not info.get("closed"))
        else:
            if self.sim_broker.shares["UP"] > 0: sides.add("UP")
            if self.sim_broker.shares["DOWN"] > 0: sides.add("DOWN")
        
        for side in sides:
            # Emergency Whale Shield (v5.9)
            if self.mom_buy_mode == "ADV":
                adv = self.mom_adv_settings
                rem = TradingConfig.WINDOW_SECONDS - (time.time() - self.market_data["start_ts"])
                if rem <= adv["shield_time"]:
                    up_p = self.market_data.get("up_price", 0.5)
                    reach = adv["shield_reach"] / 100.0
                    if abs(up_p - 0.50) <= reach:
                        self.log_msg(f"🛡️ WHALE SHIELD: Market too tight ({up_p*100:.1f}¢). Emergency Exit.", level="MONEY")
                        await self.trigger_sell_all("UP")
                        await self.trigger_sell_all("DOWN")
                        self.last_second_exit_triggered = True
                        return

            tid = self.market_data["up_id" if side=="UP" else "down_id"]
            cbid = self.market_data["up_bid"] if side=="UP" else self.market_data["down_bid"]

            # Standard TP/SL Exit logic
            if not is_live:
                # SIM HYPOTHETICAL LOGGING
                # Calculate exact shares from window_bets for THIS window
                shares = sum((info["cost"]/info.get("entry", 0.5)) for info in self.window_bets.values() if info["side"] == side and not info.get("closed"))
                if shares > 0:
                    revenue = shares * cbid
                    # "If we were live we would sell X shares of winning side at 99c right now..."
                    self.log_msg(f"[bold magenta]SIM INFO: Live would sell {shares:.2f} {side} @ {cbid*100:.1f}¢ (Value: ${revenue:.2f})[/]")
                continue # Skip actual execution for Sim, let it expire/settle at $1.00

            # LIVE: Skip if position has clearly lost (bid < 10¢ with no triggered SL).
            # At this point with seconds left, anything under 10¢ will expire worthless —
            # attempting a sell just generates PolyApiException / "Size too small" errors.
            if cbid < 0.10:
                self.log_msg(f"[dim]⏱ SKIP FINAL EXIT {side} — position at {cbid*100:.1f}¢, clearly lost. Letting expire.[/]")
                continue

            # For LIVE: User requested strict resting limit order at $0.99
            lp = 0.99 if is_live else 0.0
            
            
            # Execute synchronously in a background thread to prevent UI lockup 
            ok, msg, _ = await asyncio.to_thread(self.trade_executor.execute_sell, is_live, side, tid, lp, cbid, "Last Second Exit")
            if ok:
                self.log_msg(f"[bold {'red' if is_live else 'green'}]⏱ FINAL EXIT {side}: {msg}[/]")
                for info in self.window_bets.values(): 
                    if info["side"] == side: info["closed"] = True
                try:
                    # Parse revenue from LIVE msg: "Total: $3.45)" OR SIM msg: "for $3.45 ("
                    if "Total: $" in msg:
                        revenue = float(msg.split("Total: $")[1].split(")")[0])
                    elif " for $" in msg:
                        revenue = float(msg.split(" for $")[1].split(" ")[0])
                    else:
                        revenue = 0.0
                    if revenue > 0: self._add_risk_revenue(revenue)
                except: pass
            else:
                self.log_msg(f"[bold red]⏱ FINAL EXIT {side} FAILED:[/] {msg}")

    async def update_timer(self):
        # Update session runtime regardless of market data status
        run = int(time.time() - self.app_start_time)
        self.query_one("#lbl_runtime").update(f" | RUN: {run//3600:02d}:{(run%3600)//60:02d}:{run%60:02d}")

        if not self.market_data["start_ts"]: return
        
        rem = max(0, TradingConfig.WINDOW_SECONDS - int(time.time() - self.market_data["start_ts"]))
        self.time_rem_str = f"{rem//60:02d}:{rem%60:02d}"
        self.query_one("#lbl_timer_big").update(self.time_rem_str)
        if rem <= 1 and not self.last_second_exit_triggered:
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
            next_ts = self.market_data["start_ts"] + TradingConfig.WINDOW_SECONDS
            next_slug = f"btc-updown-5m-{next_ts}"
            def _fetch_next():
                try:
                    d = self.market_data_manager.fetch_polymarket(next_slug)
                    up_bid  = d.get("up_bid",  0)
                    dn_bid  = d.get("down_bid", 0)
                    up_ask  = d.get("up_ask",  0)
                    dn_ask  = d.get("down_ask", 0)
                    if up_bid > 0 or dn_bid > 0:
                        self.call_from_thread(
                            self.log_msg,
                            f"NEXT WINDOW ({next_slug}): "
                            f"UP bid=[dim]{up_bid*100:.1f}¢[/] ask=[bold green]{up_ask*100:.1f}¢[/]  "
                            f"DN bid=[dim]{dn_bid*100:.1f}¢[/] ask=[bold red]{dn_ask*100:.1f}¢[/]"
                        )
                    else:
                        self.call_from_thread(self.log_msg, f"[dim]🔭 Next window not yet available ({next_slug})[/]")
                except Exception as e:
                    self.call_from_thread(self.log_msg, f"[dim]🔭 Next window fetch failed: {e}[/]")
            threading.Thread(target=_fetch_next, daemon=True).start()
        # ---------------------------

        # --- PRE-BUY NEXT WINDOW (rem <= 15, MOM Pre-Buy or Hybrid mode) ---
        if (rem <= 15 and not self.pre_buy_triggered
                and self.mom_buy_mode in ["PRE", "HYBRID"]
                and self.market_data["start_ts"] > 0
                and self.query_one("#cb_mom").value):
            self.pre_buy_triggered = True
            next_ts   = self.market_data["start_ts"] + TradingConfig.WINDOW_SECONDS
            next_slug = f"btc-updown-5m-{next_ts}"
            is_live   = self.query_one("#cb_live").value
            try: bet_size = float(self.query_one("#inp_amount").value)
            except: bet_size = 1.0
            trend = self.market_data_manager.trend_4h  # "UP" / "DOWN" / "NEUTRAL"

            def _do_prebuy():
                try:
                    d = self.market_data_manager.fetch_polymarket(next_slug)
                    up_ask = d.get("up_ask", 0)
                    dn_ask = d.get("down_ask", 0)
                    if up_ask <= 0 and dn_ask <= 0:
                        self.call_from_thread(self.log_msg, "[dim]🚀 PRE-BUY skipped — next window prices unavailable[/]")
                        return

                    # Calculate BTC Velocity and RSI for enhanced decision making
                    btc_open = self.market_data.get("btc_open", 0)
                    btc_pre_60s = self.mom_analytics.get("btc_pre_60s")
                    velocity = (btc_open - btc_pre_60s) if btc_open and btc_pre_60s else 0
                    
                    # Calculate 1m RSI
                    rsi_1m = 50.0
                    try:
                        closes, _, _, _ = self.market_data_manager.fetch_candles_60m()
                        if closes:
                            from .market import calculate_rsi
                            rsi_1m = calculate_rsi(closes, period=14)
                    except:
                        pass

                    # Capture exact 15s pre-window gap and BTC price for analytics
                    price_diff = up_ask - dn_ask
                    if self.mom_analytics["pre_15s_gap"] is None:
                        self.mom_analytics["pre_15s_gap"] = price_diff
                        self.mom_analytics["btc_pre_15s"] = self.market_data.get("btc_price", 0)
                    
                    # Debug: Log price difference calculation
                    self.call_from_thread(self.log_msg, f"[dim]DEBUG PRE-BUY: UP ask={up_ask*100:.1f}¢, DN ask={dn_ask*100:.1f}¢, diff={price_diff*100:.1f}¢, abs={abs(price_diff)*100:.1f}¢[/]")
                    
                    # Enhanced Decision Logic with Priority System:
                    # Priority 1: Velocity Reversion (Significantly negative velocity -> UP bet for mean reversion)
                    # Priority 2: RSI Trend (High RSI > 70 -> UP bet for trend continuation)
                    # Priority 3: Price Gap (Follow lead or reverse based on gap size)
                    
                    decision_reason = None
                    side = None
                    price = None
                    
                    if self.mom_buy_mode == "ADV":
                        atr = getattr(self.main_app.market_data_manager, "atr_5m", 0)
                        adv = self.main_app.mom_adv_settings
                        if atr >= adv["atr_high"] and adv["auto_stn_chaos"]:
                            self.call_from_thread(self.log_msg, f"[dim]PRE-BUY chaos skip (ATR:{atr:.1f}) -> Forcing STN[/]")
                            return
                    
                    # Priority 1: Velocity Reversion Check
                    if velocity <= -300:  # Increased threshold for more reliable signals
                        side = "UP"
                        price = up_ask
                        decision_reason = f"Velocity Reversion (BTC moved {velocity:.0f} down in 60s)"
                        self.call_from_thread(self.log_msg, f"[dim]PRE-BUY velocity reversion -> {side} ({velocity:.0f} move)[/]")
                    
                    # Priority 2: RSI Momentum Check (only if velocity didn't trigger)
                    elif side is None and rsi_1m > 70:
                        # Add trend context check with 1h trend strength levels
                        trend_1h = self.market_data_manager.trend_1h
                        
                        if trend_1h in ["S-DOWN", "M-DOWN", "W-DOWN"]:
                            # Skip RSI momentum signals during downtrends (insufficient data)
                            decision_reason = f"RSI Momentum skipped (RSI: {rsi_1m:.1f} > 70 but 1h trend is {trend_1h})"
                            self.call_from_thread(self.log_msg, f"[dim]PRE-BUY RSI momentum skipped (RSI: {rsi_1m:.1f}) - {trend_1h} detected[/]")
                            # Don't set side/price, let it fall through to price gap logic
                        else:
                            # Allow RSI momentum in uptrends or sideways markets
                            side = "UP"
                            price = up_ask
                            decision_reason = f"RSI Momentum (RSI: {rsi_1m:.1f} > 70, 1h Trend: {trend_1h})"
                            self.call_from_thread(self.log_msg, f"[dim]PRE-BUY RSI momentum -> {side} (RSI: {rsi_1m:.1f}, 1h Trend: {trend_1h})[/]")
                    
                    # Priority 3: Price Gap Logic (enhanced based on log analysis)
                    elif side is None:
                        # Enhanced gap logic: Consider market context before following lead
                        cur_up = self.market_data.get("up_price", 0.5)
                        cur_dn = self.market_data.get("down_price", 0.5)
                        winner = "UP" if cur_up >= cur_dn else "DOWN"
                        
                        # If strong velocity signal exists, prioritize it over gap following
                        if velocity <= -300:
                            # Strong negative velocity overrides gap following
                            side = "UP"
                            price = up_ask
                            decision_reason = f"Velocity Override (gap:{abs(price_diff)*100:.1f}¢, vel:{velocity:.0f})"
                            self.call_from_thread(self.log_msg, f"[dim]PRE-BUY velocity override -> {side} (gap:{abs(price_diff)*100:.1f}¢, vel:{velocity:.0f})[/]")
                        elif abs(price_diff) >= 0.03:  # Large gap (3¢+) - follow lead
                            side, price = ("UP", up_ask) if up_ask > dn_ask else ("DOWN", dn_ask)
                            if self.mom_buy_mode == "HYBRID":
                                decision_reason = f"Hybrid Lead ({abs(price_diff)*100:.1f}¢ gap)"
                                self.call_from_thread(self.log_msg, f"[dim]PRE-BUY hybrid lead ({abs(price_diff)*100:.1f}¢ gap) -> {side}[/]")
                            else:
                                decision_reason = f"Follow Lead ({abs(price_diff)*100:.1f}¢ gap)"
                                self.call_from_thread(self.log_msg, f"[dim]PRE-BUY follow lead ({abs(price_diff)*100:.1f}¢ gap) -> {side}[/]")
                        else:
                            # Small gaps (0¢-2¢) - make decision based on other factors
                            atr = getattr(self.market_data_manager, "atr_5m", 0)
                            trend_1h = self.market_data_manager.trend_1h
                            
                            # Decision logic for small gaps based on market factors
                            if trend_1h in ["S-DOWN", "M-DOWN"] and velocity < -100:
                                # Strong/Medium downtrend with some negative velocity -> UP (mean reversion)
                                side = "UP"
                                price = up_ask
                                decision_reason = f"Small Gap Mean Reversion (gap:{abs(price_diff)*100:.1f}¢, 1h trend:{trend_1h}, vel:{velocity:.0f})"
                            elif trend_1h in ["S-UP", "M-UP"] and rsi_1m < 60:
                                # Strong/Medium uptrend with low RSI -> UP (trend continuation)
                                side = "UP"
                                price = up_ask
                                decision_reason = f"Small Gap Trend Follow (gap:{abs(price_diff)*100:.1f}¢, 1h trend:{trend_1h}, rsi:{rsi_1m:.1f})"
                            elif atr > 100:
                                # High volatility ATR -> follow current winner
                                side = winner
                                price = up_ask if side == "UP" else dn_ask
                                decision_reason = f"Small Gap Volatility Follow (gap:{abs(price_diff)*100:.1f}¢, atr:{atr:.1f})"
                            else:
                                # Default: reversal for small gaps
                                side = "DOWN" if winner == "UP" else "UP"
                                price = up_ask if side == "UP" else dn_ask
                                decision_reason = f"Small Gap Reversal (gap:{abs(price_diff)*100:.1f}¢, winner:{winner})"
                            
                            self.call_from_thread(self.log_msg, f"[dim]PRE-BUY small gap decision -> {side} ({decision_reason})[/]")
                            
                            # Reversal: Identify who is winning CURRENTLY (proxy for "just won")
                            # and pick the opposite for the next window.
                            cur_up = self.market_data.get("up_price", 0.5)
                            cur_dn = self.market_data.get("down_price", 0.5)
                            winner = "UP" if cur_up >= cur_dn else "DOWN"
                            side = "DOWN" if winner == "UP" else "UP"
                            price = up_ask if side == "UP" else dn_ask
                            decision_reason = f"Reversal (gap:{abs(price_diff)*100:.1f}¢ | Winner:{winner})"
                            self.call_from_thread(self.log_msg, f"[dim]PRE-BUY reversal (gap:{abs(price_diff)*100:.1f}¢ | Winner:{winner}) -> {side}[/]")
                    
                    # ADV mode special handling for small gaps
                    if self.mom_buy_mode == "ADV" and side is None:
                        self.call_from_thread(self.log_msg, f"[dim]PRE-BUY adv skip (gap:{abs(price_diff)*100:.1f}¢) -> Deferring[/]")
                        return

                    # Execute the trade if we have a decision
                    if side and price:
                        token_id = d.get("up_id" if side == "UP" else "down_id")
                        ok, msg = self.trade_executor.execute_buy(
                            is_live, side, bet_size, price, token_id,
                            context={}, reason=f"PreBuy_{decision_reason}"
                        )
                        if ok:
                            pending = {"side": side, "entry": price, "cost": bet_size, "algorithm": "BullFlag"}
                            self.session_total_trades += 1 # Pre-Buy Trade
                            def _commit(p=pending, s=side, pr=price, m=msg, bs=bet_size):
                                self.pre_buy_pending = p
                                self.risk_manager.register_bet(bs)
                                self.log_msg(
                                    f"PRE-BUY NEXT {s} @ {pr*100:.1f}¢[dim] — "
                                    f"${bs:.2f} committed. {decision_reason}. Holding for next window ({next_slug})[/]"
                                )
                                self.update_balance_ui()
                            self.call_from_thread(_commit)
                        else:
                            self.call_from_thread(self.log_msg, f"[bold red]🚀 PRE-BUY FAILED:[/] {msg}")
                except Exception as e:
                    self.call_from_thread(self.log_msg, f"[dim]🚀 PRE-BUY error: {e}[/]")

            threading.Thread(target=_do_prebuy, daemon=True).start()
        # ----------------------------------------------------------
            
        # Trigger Settlement precisely on the exact dot of the 59th second
        if rem <= 1 and not self.window_settled:
            self.window_settled = True
            self.trigger_settlement()

    def _check_bankroll_exhaustion(self):
        """After each settlement, freeze the bot if it can no longer afford another bet."""
        from .ui_modals import BankrollExhaustedModal
        if self.halted: return

        br = self.risk_manager.risk_bankroll
        try: min_bet = float(self.query_one("#inp_amount").value)
        except: min_bet = 1.0
        hard_floor = 1.0  # Absolute minimum to even consider a bet

        # Only freeze if a bet was actually placed this window (we lost) AND
        # the bankroll can no longer cover the minimum bet size.
        had_bet = bool(self.window_bets)
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

    def trigger_settlement(self):
        if self.market_data["start_ts"] == 0: return

        # 1. Poly-Decisive Logic (v5.9.4)
        # If token price is > 0.90, that side is the definitive winner regardless of BTC sync issues.
        up_bid = self.market_data.get("up_bid", 0)
        dn_bid = self.market_data.get("down_bid", 0)
        btc_p = self.market_data.get("btc_price", 0)
        btc_o = self.market_data.get("btc_open", 0)
        
        if up_bid >= 0.90:
            winner = "UP"
            reason = "UP side won decisively"
        elif dn_bid >= 0.90:
            winner = "DOWN"
            reason = "DOWN side won decisively"
        else:
            winner = "UP" if btc_p >= btc_o else "DOWN"
            reason = f"BTC Move (${btc_p:,.2f} vs Open ${btc_o:,.2f})"

        self.log_msg(f"SETTLED: [bold white]{winner}[/] | [dim]{reason}[/]", level="MONEY")
        payout, net_pnl = self.sim_broker.settle_window(winner)
        
        # BullFlag Research Logging - Log trades with settings
        for info in self.window_bets.values():
            if not info.get("closed") and info.get("algorithm") == "BullFlag":
                bullflag_scanner = self.scanners.get("BullFlag")
                if bullflag_scanner and hasattr(bullflag_scanner, 'log_research_trade'):
                    # Get current market data for research logging
                    rsi_1m = getattr(self.market_data_manager, 'rsi_1m', 0)
                    btc_velocity = getattr(self.market_data_manager, 'btc_velocity', 0)
                    atr_5m = getattr(self.market_data_manager, 'atr_5m', 0)
                    
                    # Log the trade with research data
                    result = "WIN" if info.get("side") == winner else "LOSS"
                    bullflag_scanner.log_research_trade(
                        info.get("entry", 0),  # Entry price stored when signal triggered
                        self.market_data.get("btc_price", 0),  # Exit price at settlement
                        result,
                        self.market_data.get("start_ts", 0),  # Window ID
                        rsi_1m,
                        btc_velocity,
                        atr_5m
                    )
        
        for p in self.portfolios.values(): p.settle_window(winner, self.market_data["btc_price"], self.market_data["btc_open"])
        
        is_live = self.query_one("#cb_live").value
        # Accuracy: Count settlement winners
        for info in self.window_bets.values():
            if not info.get("closed") and info.get("side") == winner:
                self.session_win_count += 1
        
        self.session_windows_settled += 1
        if self.session_windows_settled > 1:
            acc_val = (self.session_win_count / self.session_total_trades * 100) if self.session_total_trades > 0 else 0
            acc_str = f"{acc_val:.1f}%"
        else:
            acc_str = "N/A"

        upt = int(time.time() - self.app_start_time)
        upt_str = f"{upt//3600:02d}:{(upt%3600)//60:02d}:{upt%60:02d}"
        self.log_msg(f"PULSE | RUN: {upt_str} | Session Trades: {self.session_total_trades} | Accuracy: {acc_str}", level="ADMIN")
        
        self._add_risk_revenue(payout)

        # --- BANKROLL EXHAUSTION CHECK ---
        self._check_bankroll_exhaustion()
        if self.halted: return

        # --- LIVE SETTLEMENT REFILL ---
        if is_live:
            live_win_payout = 0.0
            for info in self.window_bets.values():
                if info.get("closed"): continue
                if info["side"] != winner: continue
                entry = info.get("entry", 0)
                cost  = info.get("cost", 0)
                if entry > 0 and cost > 0:
                    shares = cost / entry
                    live_win_payout += shares * 1.00  # Settles at $1.00/share
            if live_win_payout > 0:
                self.log_msg(f"LIVE Settlement Refill: +${live_win_payout:.2f} (winning shares x $1.00)", level="MONEY")
                self._add_risk_revenue(live_win_payout)

        self.risk_manager.reset_window(); self.last_second_exit_triggered = False
        self.update_balance_ui(); self.window_bets.clear()
        for s in self.scanners.values(): s.reset()
        self.market_data_manager.reset_history()

        # --- Write Momentum Analytics (v5.9.4) ---
        try:
            import os
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
                    from .market import calculate_rsi
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

        # 2. In LIVE mode: allow target_bankroll to grow with wins so the bankroll
        #    compounds. Without this, every win was silently clamped back to the
        #    initial target set at session start.
        #    In SIM mode: keep the hard clamp so the sim can't exceed its theoretical cap.
        if is_live:
            if self.risk_manager.risk_bankroll > self.risk_manager.target_bankroll:
                self.risk_manager.target_bankroll = self.risk_manager.risk_bankroll
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
            'trend': self.market_data_manager.trend_4h,
            'risk_bal': self.risk_manager.risk_bankroll
        }
        
        ok, msg = self.trade_executor.execute_buy(is_l, side, val, pr or 0.5, tid, context=ctx, reason="Manual")
        if ok:
            self.session_total_trades += 1 # Manual Buy
            self.log_msg(f"[bold {'red' if is_l else 'green'}]{msg}[/]")
            if self.risk_initialized: self.risk_manager.register_bet(val)
            self.window_bets[f"Manual_{time.time()}"] = {"side":side,"entry":pr or 0.5,"cost":val}
        else:
            self.log_msg(f"[bold red]MANUAL BUY FAILED:[/] {msg}")
            
        self.update_balance_ui(); self.update_sell_buttons()

    async def trigger_sell_all(self, side):
        is_l = self.query_one("#cb_live").value
        tid = self.market_data["up_id" if side=="UP" else "down_id"]
        # Use simple ternary for bid to avoid confusion
        cbid = self.market_data["up_bid"] if side=="UP" else self.market_data["down_bid"]
        lp = cbid if not is_l else max(0.02, cbid-0.05)
        
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
