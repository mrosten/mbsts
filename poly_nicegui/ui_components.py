from nicegui import ui, app
from store import state
from datetime import datetime

# Global UI References for cross-component communication
ui_refs = {}

def header():
    with ui.header().classes('items-center justify-between bg-slate-900 text-white'):
        with ui.row().classes('items-center gap-2'):
            ui.label('🚀 Polymarket Turbo Trader v2').classes('text-lg font-bold')
            ui.label('NiceGUI Edition').classes('text-xs opacity-70')
            
        ui.button('SHUTDOWN', on_click=app.shutdown, color='red').classes('text-xs px-2 py-1 font-bold')

def analysis_card():
    with ui.card().classes('w-full bg-slate-800 text-white p-4 gap-2'):
        ui.label('📊 Market Analysis').classes('text-xl font-bold mb-2')
        
        # Recommendation Banner
        with ui.row().classes('w-full p-4 rounded-lg mb-4 items-center justify-center') as banner:
            banner.style('border-left: 5px solid #gray')
            banner_label = ui.label('Waiting for analysis...').classes('text-lg font-bold')
            
        def update_banner():
            try:
                res = state.analysis_results
                # print(f"DEBUG: update_banner called. Res keys: {res.keys() if res else 'None'}")
                if not res: return
                
                rec = res.get('recommendation', 'N/A')
                color = "gray"
                if "BETTING UP" in rec: color = "#22c55e" # green-500
                elif "BETTING DOWN" in rec: color = "#ef4444" # red-500
                elif "INADVISABLE" in rec: color = "#f97316" # orange-500
                
                banner.style(f'background-color: #1e293b; border-left: 5px solid {color}')
                banner_label.text = rec
                banner_label.style(f'color: {color}')
                
                # Detailed Reasoning
                reasoning_markdown.content = res.get('reasoning', '')
            except Exception:
                # UI Element deleted or disconnected
                pass
            
        with ui.expansion('Detailed Reasoning', icon='psychology', value=True).classes('w-full bg-slate-700 rounded'):
            reasoning_markdown = ui.markdown('Waiting for analysis...').classes('text-sm p-2 opacity-90')

        # Metrics Grid
        with ui.grid(columns=6).classes('w-full gap-4'):
             with ui.column().classes('bg-slate-700 p-2 rounded'):
                 ui.label('Time Left').classes('text-xs opacity-70')
                 time_left_label = ui.label('00:00').classes('text-lg font-bold text-blue-400')
                 
             with ui.column().classes('bg-slate-700 p-2 rounded'):
                 ui.label('Price to Beat').classes('text-xs opacity-70')
                 strike_label = ui.label('$0.00').classes('text-lg font-bold text-yellow-400')
                 
             with ui.column().classes('bg-slate-700 p-2 rounded'):
                 ui.label('Live BTC').classes('text-xs opacity-70')
                 live_btc_label = ui.label('$0.00').classes('text-lg font-bold')
                 
             with ui.column().classes('bg-slate-700 p-2 rounded'):
                 ui.label('Divergence').classes('text-xs opacity-70')
                 diff_label = ui.label('$0.00').classes('text-lg font-bold')
                 
             with ui.column().classes('bg-slate-700 p-2 rounded'):
                 ui.label('RSI (14)').classes('text-xs opacity-70')
                 rsi_label = ui.label('0.0').classes('text-lg')
                 
             with ui.column().classes('bg-slate-700 p-2 rounded'):
                 ui.label('Volatility').classes('text-xs opacity-70')
                 vol_label = ui.label('N/A').classes('text-lg')

        def update_metrics():
            try:
                res = state.analysis_results
                if not res: return
                
                # Time Left (Dynamic)
                end_ts = res.get('end_ts')
                if end_ts:
                    seconds = max(0, end_ts - datetime.now().timestamp())
                    mins, secs = divmod(int(seconds), 60)
                    time_left_label.text = f"{mins:02}:{secs:02}"
                    if seconds < 30: time_left_label.classes('text-red-600 animate-pulse') # Critical
                    elif seconds < 300: time_left_label.classes('text-orange-500').classes(remove='text-blue-400') # Convergence
                    else: time_left_label.classes('text-blue-400').classes(remove='text-red-500 text-orange-500')
                else:
                    time_left_label.text = "--:--"
                
                # Strike / Price to Beat
                strike = res.get('strike_price', 0)
                strike_label.text = f"${strike:,.2f}"
                
                # Live BTC
                curr = state.market_data.get('btc_price', 0)
                if curr > 0: curr += state.btc_offset # Apply User Offset
                live_btc_label.text = f"${curr:,.2f}"
                
                # Color Live BTC
                if curr > 0 and strike > 0:
                    diff = curr - strike
                    
                    # Better: simple diff color
                    color = "#22c55e" if diff > 0 else "#ef4444"
                    live_btc_label.style(f'color: {color}')
                    diff_label.style(f'color: {color}')
                    diff_label.text = f"{diff:+.2f}"
                else:
                    diff_label.text = "$0.00"
                
                rsi_label.text = f"{res.get('rsi', 0):.1f}"
                vol_label.text = res.get('vol_status', 'N/A')
            except Exception:
                pass
            
        # Refresher
        ui.timer(1.0, update_banner)
        ui.timer(1.0, update_metrics)

def trading_controls():
    with ui.card().classes('w-full bg-slate-800 text-white p-4 mt-4'):
        with ui.row().classes('w-full justify-between items-center mb-2'):
            ui.label('⚡ Quick Trade').classes('text-xl font-bold')
            last_update_label = ui.label('').classes('text-xs opacity-50')
        
        # Live Prices
        with ui.grid(columns=2).classes('w-full gap-4 mb-4'):
             with ui.column().classes('bg-slate-700 p-2 rounded items-center'):
                 up_price_label = ui.label('Loading...').classes('text-2xl font-bold text-green-400')
                 up_name_label = ui.label('UP').classes('text-xs opacity-70')
                 
             with ui.column().classes('bg-slate-700 p-2 rounded items-center'):
                 down_price_label = ui.label('Loading...').classes('text-2xl font-bold text-red-400')
                 down_name_label = ui.label('DOWN').classes('text-xs opacity-70')

        def update_prices():
            try:
                data = state.market_data
                if not data: return
                
                up_price_label.text = f"${data.get('up_price', 0):.3f}"
                up_name_label.text = f"BUY {data.get('up_label', 'UP').upper()}"
                
                down_price_label.text = f"${data.get('down_price', 0):.3f}"
                down_name_label.text = f"BUY {data.get('down_label', 'DOWN').upper()}"
                
                last_update_label.text = f"Updated: {datetime.now().strftime('%H:%M:%S')}"
            except Exception:
                pass
            
        # Timers (UI Updates Only)
        # Fetching is now handled by store.background_loop
        t_ui = ui.timer(1.0, update_prices)
        
        # Refresh Rate & Offset Adjuster
        def set_rate(e):
            new_rate = float(e.value)
            state.set_refresh_rate(new_rate) # Update background loop speed immediately
            ui.notify(f"Fetch rate set to {new_rate}s")
            
        def set_offset(e):
            state.btc_offset = float(e.value)
            
        # 1. Side Selection (Lever)
        side_toggle = ui.toggle(['UP', 'DOWN'], value='UP').props('spread toggle-color=blue-600').classes('w-full font-bold text-lg mb-2')
            
        # 2. Controls
        with ui.row().classes('w-full gap-4 items-center mb-2'):
            shares_input = ui.number(label='Shares', value=5.0, min=1.0, step=1.0).props('dark outlined').classes('w-32')
            ui.select([2, 5, 10, 30, 60], value=2, label='Refresh (s)', on_change=set_rate).props('dark outlined').classes('w-24')
            ui.number(label='BTC Offset', value=-86.0, step=1.0, on_change=set_offset).props('dark outlined').classes('w-24')
            
        # 3. Action Button
        async def execute_trade():
            side = side_toggle.value.lower()
            await state.place_trade(side, shares_input.value)
            
        buy_btn = ui.button('EXECUTE TRADE', color='blue', on_click=execute_trade).classes('w-full h-14 text-xl font-bold')
        
        # Bind Color to Toggle
        def update_colors():
            if side_toggle.value == 'UP':
                side_toggle.props('toggle-color=green')
                buy_btn.props('color=green')
            else:
                side_toggle.props('toggle-color=red')
                buy_btn.props('color=red')
        
        side_toggle.on_value_change(update_colors)
        
        side_toggle.on_value_change(update_colors)
        
        # Combined Handler
        def on_lever_change(e):
            # 1. Update Colors
            update_colors()
            
            # 2. Update Global State
            val = side_toggle.value.upper()
            state.trading_side = val
            print(f"DEBUG: Lever set to {val}. Synced to Store.")
                    
        side_toggle.on_value_change(on_lever_change)
        
        update_colors() # Init

        update_colors() # Init
        
def strategy_controls():
    with ui.expansion('🤖 Auto-Strategies', icon='smart_toy').classes('w-full bg-slate-800 text-white p-4 mt-4 rounded'):
        with ui.column().classes('w-full gap-4'):
             
             # 1. Reversion Master
             with ui.row().classes('w-full justify-between items-center bg-slate-700 p-2 rounded'):
                 with ui.column():
                     ui.label('Reversion Master').classes('font-bold text-blue-400')
                     ui.label('Buy Low/Sell High in Range').classes('text-xs opacity-70')
                 
                 # rev_toggle = ui.switch().props('color=blue').on_value_change(lambda e: state.safe_notify(f"Reversion: {e.value}"))
                 # Bind directly to state
                 rev_toggle = ui.switch().props('color=blue').bind_value(state, 'strategy_reversion_active')
                 
             # 2. Trend Surfer
             with ui.row().classes('w-full justify-between items-center bg-slate-700 p-2 rounded'):
                 with ui.column():
                     ui.label('Trend Surfer').classes('font-bold text-purple-400')
                     ui.label('Follow SuperTrend Momentum').classes('text-xs opacity-70')
                 
                 # Bind directly to state
                 trend_toggle = ui.switch().props('color=purple').bind_value(state, 'strategy_trend_active')
                 
             # 3. Bracket Bot
             with ui.row().classes('w-full justify-between items-center bg-slate-700 p-2 rounded'):
                 with ui.column():
                     ui.label('Bracket Bot').classes('font-bold text-yellow-400')
                     ui.label('Auto Set TP/SL on Entry').classes('text-xs opacity-70')
                 
                 # Bind directly to state
                 bracket_toggle = ui.switch().props('color=yellow').bind_value(state, 'strategy_bracket_active')

             # Bracket Settings
             with ui.grid(columns=2).classes('w-full gap-4'):
                 tp_input = ui.number(label='Take Profit %', value=20, min=1, max=100, suffix='%').props('dark outlined')
                 sl_input = ui.number(label='Stop Loss %', value=10, min=1, max=100, suffix='%').props('dark outlined')
                 
                 def update_bracket_params():
                     state.bracket_tp_pct = tp_input.value / 100.0
                     state.bracket_sl_pct = sl_input.value / 100.0
                     # ui.notify("Bracket Params Updated")
                     
                 tp_input.on('update:model-value', update_bracket_params)
                 sl_input.on('update:model-value', update_bracket_params)

def stop_loss_manager():
    # Dynamic Border Card
    card = ui.card().classes('w-full bg-slate-800 text-white p-4 mt-4 border-l-4 border-slate-600')
    
    with card:
        # Row 1: Header
        with ui.row().classes('w-full justify-between items-center mb-2'):
            ui.label('🛡️ Stop Loss').classes('text-xl font-bold')
            sl_status_label = ui.label('INACTIVE').classes('text-sm font-bold text-gray-500')

        # Row 2: Trigger (Read Only info) & Action
        with ui.row().classes('w-full items-center gap-4 mb-2'):
             # Trigger Input (Read Only Display)
             sl_input = ui.number(label='Trigger ($)', value=0.00, format='%.2f').props('readonly dark outlined').classes('w-32')
             
             # Smart Action Button
             action_btn = ui.button('ACTIVATE', on_click=lambda: toggle_sl()).classes('flex-grow font-bold transition-colors')

        # Row 3: Trailing Settings & Mode
        with ui.row().classes('w-full items-center gap-4'):
             trail_switch = ui.switch('Auto-Trail').bind_value(state, 'sl_trailing').props('color=blue dense')
             
             # Dist Input
             dist_input = ui.number(label='Dist ($)', step=0.05, min=0.05, format='%.2f').props('dark outlined dense w-24').bind_value(state, 'sl_trail_dist')
             
        # Row 4: Auto-Arm Toggle
        with ui.row().classes('w-full justify-center mt-2'):
             ui.toggle(['MANUAL', 'AUTO ARM']).bind_value(state, 'sl_auto_arm').props('toggle-color=purple')

        def toggle_sl():
            if state.sl_active:
                state.cancel_stop_loss()
            else:
                # Use current calculated value from input
                state.set_stop_loss(sl_input.value)

        def update_sl_status():
            # 1. Determine Target Side
            target = state.sl_side.upper() if state.sl_active else state.trading_side
            
            # 2. Update Border Color
            color_class = 'border-green-500' if target == 'UP' else 'border-red-500'
            card.classes(remove='border-slate-600 border-green-500 border-red-500')
            card.classes(add=color_class)

            # 3. Update Inputs State
            if not state.sl_trailing:
                dist_input.disable()
            else:
                dist_input.enable()

            # 4. Content & Button State
            if state.sl_active:
                sl_status_label.text = f"ON @ ${state.sl_trigger_price:.2f}"
                sl_status_label.classes('text-green-400').classes(remove='text-gray-500')
                
                action_btn.text = "CANCEL STOP LOSS"
                action_btn.props('color=red')
                
            else:
                sl_status_label.text = "INACTIVE"
                sl_status_label.classes('text-gray-500').classes(remove='text-green-400')
                
                # Auto-Arm State Override?
                if state.sl_auto_arm:
                    action_btn.text = f"AUTO-ARM ENABLED ({target})"
                    action_btn.props('color=purple')
                    # We still allow manual click to force it? Yes.
                else:
                    action_btn.text = f"ACTIVATE ({target})"
                    action_btn.props('color=green')
                
                # Validation
                s = target.lower()
                price = state.market_data.get(f"{s}_price", 0)
                
                # Auto-Calculate Trigger Preview
                dist = state.sl_trail_dist
                rec_price = max(0.01, round(price - dist, 2)) if price > 0 else 0.00
                sl_input.value = rec_price
                
                if price <= 0:
                    action_btn.disable()
                    action_btn.props('label="WAITING..." color=grey')
                else:
                    action_btn.enable()
                
        ui.timer(0.5, update_sl_status)
