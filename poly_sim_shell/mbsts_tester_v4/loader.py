import pandas as pd
from datetime import datetime
import time

class LogLoader:
    def __init__(self, filepath):
        self.filepath = filepath
        self.df = None
        self.ticks = []
        
    def load(self):
        """Loads the CSV and filters for SIM/LIVE ticks, excluding metadata rows."""
        self.df = pd.read_csv(self.filepath)
        
        # Filter for rows that have valid price data (Timestamp is usually a full date string for ticks)
        # In our format, Timestamp is 'TRADE_EVENT' for trades. We want the ones that ARE date times.
        ticks_df = self.df[self.df['Timestamp'] != 'TRADE_EVENT'].copy()
        ticks_df['Timestamp'] = pd.to_datetime(ticks_df['Timestamp'])
        
        # Convert necessary columns to numeric
        cols = ['BTC_Price', 'BTC_Open', 'UP_Bid', 'DN_Bid', 'UP_Price', 'DN_Price']
        for col in cols:
            ticks_df[col] = pd.to_numeric(ticks_df[col], errors='coerce')
            
        # Clean up
        ticks_df = ticks_df.dropna(subset=['BTC_Price'])
        
        # Sort by timestamp just in case
        ticks_df = ticks_df.sort_values('Timestamp')
        
        self.ticks = ticks_df.to_dict('records')
        return self.ticks

    def get_window_iterator(self):
        """Yields chunks of ticks grouped by their 5-minute window."""
        if not self.ticks:
            return
            
        current_window = []
        last_open = None
        
        for tick in self.ticks:
            if last_open is None:
                last_open = tick['BTC_Open']
            
            # If BTC_Open changes, it's a new window
            if tick['BTC_Open'] != last_open:
                yield current_window
                current_window = []
                last_open = tick['BTC_Open']
                
            current_window.append(tick)
            
        if current_window:
            yield current_window
