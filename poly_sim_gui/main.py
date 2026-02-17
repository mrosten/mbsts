from nicegui import ui, app
from datetime import datetime, timezone
import asyncio
from simulation import simulation

# --- Helper ---
def format_currency(val):
    return f"${val:,.2f}"

async def main_loop():
    # Update Simulation
    await simulation.update_loop()
    
    # --- PRO TICKER UI UPDATES ---
    
    # Clocks
    now_utc = datetime.now(timezone.utc)
    jlm = now_utc + simulation.OFFSET_JERUSALEM
    et = now_utc + simulation.OFFSET_ET
    clock_jlm.set_text(f"JLM: {jlm.strftime('%H:%M:%S')}")
    clock_et.set_text(f"ET:  {et.strftime('%H:%M:%S')}")
    
    # Countdown & Link
    countdown_label.set_text(f"Next Market In: {simulation.ui_countdown}")
    
    # Color code countdown
    if simulation.ui_countdown != "00:00" and int(simulation.ui_countdown.split(":")[1]) < 60 and int(simulation.ui_countdown.split(":")[0]) == 0:
         # Simplified color logic: Red if last minute (00:XX)
         countdown_label.classes('text-red-500', remove='text-green-400')
    else:
         countdown_label.classes('text-green-400', remove='text-red-500')
         
    link_label.set_text(f"Current Market Ends: {simulation.ui_end_time} JLM")
    
    # The Link
    market_link.set_text(simulation.market_url)
    market_link.props(f'href={simulation.market_url}')
    
    # Market Info (BTC & Open)
    btc_price = simulation.market_data.get("btc_price", 0)
    open_p = simulation.market_data.get("open_price", 0)
    market_info_label.set_text(f"BTC: ${btc_price:,.2f} | OPEN: ${open_p:,.2f}")
    
    # Option Prices
    up_price = simulation.market_data.get("up_price", 0)
    down_price = simulation.market_data.get("down_price", 0)
    option_prices_label.set_text(f"UP: ${up_price:.3f}   |   DOWN: ${down_price:.3f}")
    
    # Color code options
    if up_price > down_price:
        option_prices_label.classes('text-green-400', remove='text-red-400 text-gray-400')
    elif down_price > up_price:
        option_prices_label.classes('text-red-400', remove='text-green-400 text-gray-400')
    else:
        option_prices_label.classes('text-gray-400', remove='text-green-400 text-red-400')
    
    # Strategy Dashboard Update
    balance_label.set_text(format_currency(simulation.balance))
    
    if simulation.active_trade:
        t = simulation.active_trade
        current_price = simulation.market_data["up_price"] if t["side"] == "UP" else simulation.market_data["down_price"]
        val = t["shares"] * current_price
        pnl = val - t["cost"]
        pnl_color = "text-green-400" if pnl >= 0 else "text-red-400"
        
        position_label.set_text(f"{t['side']} | {t['shares']} sh @ {t['entry_price']:.2f}")
        pnl_label.set_text(f"PnL: {format_currency(pnl)}")
        pnl_label.classes(pnl_color, remove="text-green-400 text-red-400")
    else:
        position_label.set_text("No Active Position")
        pnl_label.set_text("")
        
    # Logs
    log_content = "\n".join(simulation.logs[-20:])
    log_text.set_content(f"```\n{log_content}\n```")

# --- UI LAYOUT (Matching ProTicker Style) ---

with ui.card().classes('w-full max-w-4xl mx-auto bg-slate-900 text-white p-8 items-center text-center'):
    ui.label('BTC 15m Ticker & Sim').classes('text-2xl font-bold text-blue-400 mb-2')
    
    # Clocks
    with ui.row().classes('gap-8 justify-center w-full'):
        clock_et = ui.label('ET:  --:--:--').classes('text-xl font-mono text-gray-300')
        clock_jlm = ui.label('JLM: --:--:--').classes('text-xl font-mono text-yellow-200')
        
    ui.separator().classes('bg-gray-700 w-full my-4')
    
    # Countdown
    countdown_label = ui.label('Next Market In: --:--').classes('text-4xl font-bold font-mono text-green-400 my-2')
    link_label = ui.label('Current Market Ends: --:--').classes('text-sm text-gray-400')
    
    # Link
    market_link = ui.link('Loading Link...', '#').classes('text-lg text-blue-300 font-bold hover:text-blue-100 break-all mb-4')

    # Market Data
    ui.label('Live Data').classes('text-xs text-gray-500 uppercase tracking-widest mt-4')
    market_info_label = ui.label('BTC: -- | Opening: --').classes('text-2xl font-mono text-white font-bold bg-slate-800 p-2 rounded mb-2')
    option_prices_label = ui.label('UP: -- | DOWN: --').classes('text-xl font-mono font-bold border border-gray-700 p-2 rounded')

    ui.separator().classes('bg-gray-700 w-full my-6')

    # --- SIMULATION SECTION ---
    ui.label('Simulation Dashboard').classes('text-xl font-bold text-purple-300 mb-4')
    
    with ui.grid(columns=2).classes('w-full gap-4 text-left'):
        # Balance Card
        with ui.column().classes('bg-slate-800 p-4 rounded border border-gray-700 items-center'):
            ui.label('Balance').classes('text-sm text-gray-400 uppercase')
            balance_label = ui.label('$50.00').classes('text-4xl font-bold text-green-400')
            
        # Position Card
        with ui.column().classes('bg-slate-800 p-4 rounded border border-gray-700 items-center'):
            ui.label('Active Trade').classes('text-sm text-gray-400 uppercase')
            position_label = ui.label('None').classes('text-xl font-bold')
            pnl_label = ui.label('').classes('text-xl font-mono font-bold')

    # Controls
    with ui.expansion('Simulation Settings', icon='settings').classes('w-full bg-slate-800 rounded mt-4 text-left'):
        with ui.column().classes('p-4'):
            ui.number('Start Balance', value=50.0, on_change=lambda e: setattr(simulation, 'balance', e.value)).classes('text-white w-full')
            ui.number('Trade Size', value=5.5, on_change=lambda e: setattr(simulation, 'trade_size', e.value)).classes('text-white w-full')
            
            # Offset Controls
            with ui.row().classes('items-center w-full gap-4'):
                 ui.number('BTC Offset', value=-86.0).bind_value(simulation, 'btc_offset').classes('text-white flex-grow')
                 ui.switch('Auto-Sync (CoinGecko)').bind_value(simulation, 'auto_offset').classes('text-green-400')

    # Action Buttons
    with ui.row().classes('gap-4 mt-6'):
        ui.button('Start Simulation', on_click=simulation.start_simulation, color='green').classes('px-8 py-2 text-lg')
        ui.button('Stop', on_click=simulation.stop_simulation, color='red').classes('px-8 py-2 text-lg')

    # Logs
    with ui.expansion('Logs', icon='list').classes('w-full bg-black mt-4').props('expanded'):
        log_text = ui.markdown('').classes('w-full h-64 font-mono text-xs p-2 text-green-300 overflow-y-auto')

# Run Loop
ui.timer(1.0, main_loop)

ui.run(title='PolySim Pro', dark=True, port=8089)
