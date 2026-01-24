"""
SQLite Database Viewer - Windowed GUI for Polytrading
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import sqlite3
from datetime import datetime

class PolyViewerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Polytrading Active Markets Viewer")
        self.root.geometry("1000x600")
        
        # Database connection
        self.db = sqlite3.connect('example_sprout_apps/polytrading/polytrading.db')
        self.cursor = self.db.cursor()
        
        # Create UI
        self.create_widgets()
        self.load_stats()
        self.load_data()
    
    def create_widgets(self):
        # Create Notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Tab 1: Active Markets
        self.tab_markets = tk.Frame(self.notebook)
        self.notebook.add(self.tab_markets, text='Active Markets')
        self.setup_markets_tab(self.tab_markets)
        
        # Tab 2: Price History
        self.tab_prices = tk.Frame(self.notebook)
        self.notebook.add(self.tab_prices, text='Price History')
        self.setup_prices_tab(self.tab_prices)

    def setup_markets_tab(self, parent):
        # Top frame - Stats
        stats_frame = tk.Frame(parent, bg='#2c3e50', pady=10)
        stats_frame.pack(fill='x')
        
        self.market_stats_label = tk.Label(stats_frame, text="Loading...", 
                                    fg='white', bg='#2c3e50', 
                                    font=('Arial', 12, 'bold'))
        self.market_stats_label.pack()
        
        # List frame
        list_frame = tk.Frame(parent)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        columns = ('date', 'title', 'markets')
        self.market_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
        self.market_tree.heading('date', text='Timestamp')
        self.market_tree.heading('title', text='Event Title')
        self.market_tree.heading('markets', text='Markets')
        self.market_tree.column('date', width=150)
        self.market_tree.column('title', width=600)
        self.market_tree.column('markets', width=100)
        
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.market_tree.yview)
        self.market_tree.configure(yscrollcommand=scrollbar.set)
        self.market_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        refresh_btn = tk.Button(parent, text="Refresh Data", command=self.load_market_data)
        refresh_btn.pack(pady=5)

    def setup_prices_tab(self, parent):
        # Top frame - Stats
        stats_frame = tk.Frame(parent, bg='#27ae60', pady=10)
        stats_frame.pack(fill='x')
        
        self.price_stats_label = tk.Label(stats_frame, text="Loading...", 
                                    fg='white', bg='#27ae60', 
                                    font=('Arial', 12, 'bold'))
        self.price_stats_label.pack()
        
        # List frame
        list_frame = tk.Frame(parent)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        columns = ('date', 'outcome', 'price')
        self.price_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
        self.price_tree.heading('date', text='Timestamp')
        self.price_tree.heading('outcome', text='Outcome')
        self.price_tree.heading('price', text='Price')
        self.price_tree.column('date', width=150)
        self.price_tree.column('outcome', width=100)
        self.price_tree.column('price', width=100)
        
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.price_tree.yview)
        self.price_tree.configure(yscrollcommand=scrollbar.set)
        self.price_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        refresh_btn = tk.Button(parent, text="Refresh Prices", command=self.load_price_data)
        refresh_btn.pack(pady=5)
    
    def load_data(self):
        self.load_market_data()
        self.load_price_data()

    def load_market_data(self):
        for item in self.market_tree.get_children():
            self.market_tree.delete(item)
            
        try:
            self.cursor.execute("SELECT COUNT(*) FROM ActiveMarket")
            total = self.cursor.fetchone()[0]
            self.market_stats_label.config(text=f"Total Active Market Records: {total}")
            
            self.cursor.execute("SELECT title, market_count, timestamp FROM ActiveMarket ORDER BY timestamp DESC LIMIT 100")
            for title, count, ts in self.cursor.fetchall():
                date_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
                self.market_tree.insert('', 'end', values=(date_str, title, count))
        except Exception as e:
            print(f"Error loading markets: {e}")

    def load_price_data(self):
        for item in self.price_tree.get_children():
            self.price_tree.delete(item)
            
        try:
            self.cursor.execute("SELECT COUNT(*) FROM PriceHistory")
            total = self.cursor.fetchone()[0]
            self.price_stats_label.config(text=f"Total Price Records: {total}")
            
            self.cursor.execute("SELECT outcome, price, timestamp FROM PriceHistory ORDER BY timestamp DESC LIMIT 100")
            for outcome, price, ts in self.cursor.fetchall():
                date_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
                self.price_tree.insert('', 'end', values=(date_str, outcome, f"{price:.4f}"))
        except Exception as e:
            print(f"Error loading prices: {e}")
            self.price_stats_label.config(text="PriceHistory table not found or empty")

    # Disable old methods
    def load_stats(self): pass
    def next_page(self): pass
    def prev_page(self): pass
    def search_data(self): pass
    def show_latest(self): pass
    def on_select(self, e): pass
    
    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()

if __name__ == "__main__":
    root = tk.Tk()
    app = PolyViewerGUI(root)
    root.mainloop()
