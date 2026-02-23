import pandas as pd
from datetime import datetime
import time
import os

class LogLoader:
    def __init__(self, filepath):
        self.filepath = filepath
        self.df = None
        self.ticks = []
        
    def load(self):
        """Loads the CSV and filters for SIM/LIVE ticks, excluding metadata rows."""
        self.df = pd.read_csv(self.filepath)
        
        # Filter for rows that have valid price data
        ticks_df = self.df[self.df['Timestamp'] != 'TRADE_EVENT'].copy()
        
        # Convert timestamp to datetime if possible
        try:
            ticks_df['Timestamp'] = pd.to_datetime(ticks_df['Timestamp'])
        except:
            pass
        
        # Convert necessary columns to numeric
        cols = ['BTC_Price', 'BTC_Open', 'UP_Bid', 'DN_Bid', 'UP_Price', 'DN_Price', 'SimBal', 'RiskBankroll']
        for col in cols:
            if col in ticks_df.columns:
                ticks_df[col] = pd.to_numeric(ticks_df[col], errors='coerce')
            
        # Clean up
        ticks_df = ticks_df.dropna(subset=['BTC_Price'])
        
        # Sort by timestamp
        try:
            ticks_df = ticks_df.sort_values('Timestamp')
        except:
            pass
            
        self.ticks = ticks_df.to_dict('records')
        return self.ticks

    def get_historical_trades(self):
        """Extracts bot-made trades from the log for comparison."""
        if self.df is None: return []
        
        trades = self.df[self.df['Timestamp'] == 'TRADE_EVENT'].copy()
        trade_list = []
        
        for _, row in trades.iterrows():
            try:
                # Mapping based on user observed schema
                trade_data = {
                    'Time': row.get('Mode', 'N/A'),
                    'Type': row.get('SimBal', 'N/A'),
                    'Direction': row.get('LiveBal', 'N/A'),
                    'Amount': float(row.get('RiskBankroll', 0)) if pd.notnull(row.get('RiskBankroll')) else 0,
                    'Price': row.get('TimeRem', '0'), # Often Price or Time Remaining
                    'Note': row.get('Sig_Slingshot', '')
                }
                
                # Check if Note contains Settlement info
                note_str = str(trade_data['Note'])
                if trade_data['Type'] == 'SETTLE' and '|' in note_str:
                    parts = note_str.split('|')
                    trade_data['Result'] = parts[0].strip()
                    trade_data['PnL_Summary'] = parts[1].strip()
                
                trade_list.append(trade_data)
            except Exception as e:
                pass
        return trade_list

    def get_window_iterator(self):
        """Yields chunks of ticks grouped by their 5-minute window."""
        if not self.ticks:
            return
            
        current_window = []
        last_open = None
        
        for tick in self.ticks:
            if last_open is None:
                last_open = tick.get('BTC_Open')
            
            # If BTC_Open changes, it's a new window
            if tick.get('BTC_Open') != last_open:
                if current_window:
                    yield current_window
                current_window = []
                last_open = tick.get('BTC_Open')
                
            current_window.append(tick)
            
        if current_window:
            yield current_window
