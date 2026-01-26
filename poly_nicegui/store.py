from nicegui import ui, run
import json
import market_analysis
from datetime import datetime

class Store:
    def __init__(self):
        self.url = ""
        self.market_data = {}
        self.analysis_results = {}
        self.active_position = None # {type: 'up'/'down', entry: 0.5, sl: 0.45, size: 5}
        self.is_analyzing = False
        
    def set_url(self, url):
        self.url = url
        
    async def run_analysis(self):
        print(f"DEBUG: Starting analysis for {self.url}")
        if not self.url: 
            print("DEBUG: No URL provided")
            return
        self.is_analyzing = True
        
        try:
            # Run in executor to avoid blocking main thread
            print("DEBUG: Calling market_analysis.analyze_market_data...")
            results = await run.io_bound(market_analysis.analyze_market_data, self.url)
            print(f"DEBUG: Results received: {results.keys() if results else 'None'}")
            self.analysis_results = results
        except Exception as e:
            print(f"DEBUG: Analysis Error: {e}")
            self.analysis_results = {"recommendation": f"Error: {str(e)}"}
            
        self.is_analyzing = False
        
    def get_price_labels(self):
        # Fallback
        return "Up", "Down"

# Global Store Instance
state = Store()
