from nicegui import ui, app
import ui_components
from store import state
import asyncio
# --- APP SETUP ---
ui.query('.q-page').classes('bg-slate-950')
ui.add_head_html('<script src="https://cdn.tailwindcss.com"></script>')

# --- MAIN LAYOUT ---
ui_components.header()

with ui.column().classes('w-full max-w-4xl mx-auto p-4 gap-4'):
    
    # URL Input
    with ui.card().classes('w-full bg-slate-800 p-4'):
        url_input = ui.input(
            label='Polymarket Event URL', 
            placeholder='https://polymarket.com/event/...',
            on_change=lambda e: state.set_url(e.value)
        ).props('dark outlined w-full').classes('w-full')
        
        ui.button('Analyze', on_click=state.run_analysis).classes('mt-2 w-full bg-blue-600')

    # Indicators & Trading
    ui_components.analysis_card()
    ui_components.trading_controls()

# Run
ui.run(title='Polymarket Turbo Trader v2', dark=True, reload=False, port=8085)
