from nicegui import ui
from store import state

def header():
    with ui.header().classes('items-center justify-between bg-slate-900 text-white'):
        ui.label('🚀 Polymarket Turbo Trader v2').classes('text-lg font-bold')
        ui.label('NiceGUI Edition').classes('text-xs opacity-70')

def analysis_card():
    with ui.card().classes('w-full bg-slate-800 text-white p-4 gap-2'):
        ui.label('📊 Market Analysis').classes('text-xl font-bold mb-2')
        
        # Recommendation Banner
        with ui.row().classes('w-full p-4 rounded-lg mb-4 items-center justify-center') as banner:
            banner.style('border-left: 5px solid #gray')
            banner_label = ui.label('Waiting for analysis...').classes('text-lg font-bold')
            
        def update_banner():
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

        # Metrics Grid
        with ui.grid(columns=3).classes('w-full gap-4'):
             with ui.column().classes('bg-slate-700 p-2 rounded'):
                 ui.label('Strike Price').classes('text-xs opacity-70')
                 strike_label = ui.label('$0.00').classes('text-lg')
                 
             with ui.column().classes('bg-slate-700 p-2 rounded'):
                 ui.label('RSI (14)').classes('text-xs opacity-70')
                 rsi_label = ui.label('0.0').classes('text-lg')
                 
             with ui.column().classes('bg-slate-700 p-2 rounded'):
                 ui.label('Volatility').classes('text-xs opacity-70')
                 vol_label = ui.label('N/A').classes('text-lg')

        def update_metrics():
            res = state.analysis_results
            if not res: return
            
            strike_label.text = f"${res.get('strike_price', 0):,.2f}"
            rsi_label.text = f"{res.get('rsi', 0):.1f}"
            vol_label.text = res.get('vol_status', 'N/A')
            
        # Refresher
        ui.timer(1.0, update_banner)
        ui.timer(1.0, update_metrics)

def trading_controls():
    with ui.card().classes('w-full bg-slate-800 text-white p-4 mt-4'):
        ui.label('⚡ Quick Trade').classes('text-xl font-bold mb-2')
        
        with ui.row().classes('w-full gap-4'):
            shares_input = ui.number(label='Shares', value=5.0, min=1.0, step=1.0).props('dark outlined').classes('w-32')
            
            ui.button('BUY UP', color='green').classes('flex-1 h-14 text-lg font-bold')
            ui.button('BUY DOWN', color='red').classes('flex-1 h-14 text-lg font-bold')
