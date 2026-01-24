"""
Gmail Tracker GUI Viewer
Using Tkinter for a native Windows interface
"""
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime
import os
import sys

# Database path (root directory)
DB_PATH = 'gmail.db'

class GmailViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gmail Inbox Tracker")
        self.root.geometry("600x500")
        
        # Style
        style = ttk.Style()
        style.configure("Big.TLabel", font=("Segoe UI", 24))
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Stat.TLabel", font=("Segoe UI", 10))
        
        # Tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.tab_dashboard = ttk.Frame(self.notebook)
        self.tab_history = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_dashboard, text='Dashboard')
        self.notebook.add(self.tab_history, text='History Log')
        
        self.setup_dashboard()
        self.setup_history()
        
        # Refresh Button
        btn_refresh = ttk.Button(root, text="Refresh Data", command=self.load_data)
        btn_refresh.pack(side='bottom', pady=10)
        
        # Load initial data
        self.load_data()

    def setup_dashboard(self):
        # Frame for Stats
        stats_frame = ttk.LabelFrame(self.tab_dashboard, text="Current Status", padding=15)
        stats_frame.pack(fill='x', padx=10, pady=10)
        
        # Grid layout for stats
        # Total
        ttk.Label(stats_frame, text="Total Messages", style="Stat.TLabel").grid(row=0, column=0, padx=20)
        self.lbl_total = ttk.Label(stats_frame, text="--", style="Big.TLabel")
        self.lbl_total.grid(row=1, column=0, padx=20)
        
        # Inbox
        ttk.Label(stats_frame, text="Inbox", style="Stat.TLabel").grid(row=0, column=1, padx=20)
        self.lbl_inbox = ttk.Label(stats_frame, text="--", style="Big.TLabel")
        self.lbl_inbox.grid(row=1, column=1, padx=20)
        
        # Unread
        ttk.Label(stats_frame, text="Unread", style="Stat.TLabel").grid(row=0, column=2, padx=20)
        self.lbl_unread = ttk.Label(stats_frame, text="--", style="Big.TLabel")
        self.lbl_unread.grid(row=1, column=2, padx=20)
        
        # Starred
        ttk.Label(stats_frame, text="Starred", style="Stat.TLabel").grid(row=0, column=3, padx=20)
        self.lbl_starred = ttk.Label(stats_frame, text="--", style="Big.TLabel")
        self.lbl_starred.grid(row=1, column=3, padx=20)
        
        # Last Updated
        self.lbl_updated = ttk.Label(stats_frame, text="Last Updated: --")
        self.lbl_updated.grid(row=2, column=0, columnspan=4, pady=(10,0))
        
        # Top Senders Section
        senders_frame = ttk.LabelFrame(self.tab_dashboard, text="Top Senders (Recent)", padding=10)
        senders_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Treeview for senders
        columns = ('name', 'count')
        self.tree_senders = ttk.Treeview(senders_frame, columns=columns, show='headings', height=8)
        self.tree_senders.heading('name', text='Sender')
        self.tree_senders.heading('count', text='Count')
        self.tree_senders.column('name', width=350)
        self.tree_senders.column('count', width=100, anchor='center')
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(senders_frame, orient=tk.VERTICAL, command=self.tree_senders.yview)
        self.tree_senders.configure(yscroll=scrollbar.set)
        
        self.tree_senders.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    def setup_history(self):
        # Treeview for history
        columns = ('time', 'total', 'inbox', 'unread', 'starred')
        self.tree_history = ttk.Treeview(self.tab_history, columns=columns, show='headings')
        
        self.tree_history.heading('time', text='Time')
        self.tree_history.heading('total', text='Total')
        self.tree_history.heading('inbox', text='Inbox')
        self.tree_history.heading('unread', text='Unread')
        self.tree_history.heading('starred', text='Starred')
        
        self.tree_history.column('time', width=150)
        self.tree_history.column('total', width=80)
        self.tree_history.column('inbox', width=80)
        self.tree_history.column('unread', width=80)
        self.tree_history.column('starred', width=80)
        
        scrollbar = ttk.Scrollbar(self.tab_history, orient=tk.VERTICAL, command=self.tree_history.yview)
        self.tree_history.configure(yscroll=scrollbar.set)
        
        self.tree_history.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    def load_data(self):
        if not os.path.exists(DB_PATH):
            messagebox.showerror("Error", "gmail.db not found!\nRun run_gmail_tracker.bat first.")
            return

        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # --- Load Dashboard Stats ---
            cursor.execute("""
                SELECT timestamp, total_messages, inbox_count, unread_count, starred_count
                FROM EmailStats
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            latest = cursor.fetchone()
            
            if latest:
                ts, total, inbox, unread, starred = latest
                dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                
                self.lbl_updated.config(text=f"Last Updated: {dt}")
                self.lbl_total.config(text=f"{total:,}")
                self.lbl_inbox.config(text=str(inbox))
                self.lbl_unread.config(text=str(unread))
                self.lbl_starred.config(text=str(starred))
            
            # --- Load Top Senders ---
            # Clear existing items
            for i in self.tree_senders.get_children():
                self.tree_senders.delete(i)
                
            cursor.execute("""
                SELECT sender_name, sender_email, message_count
                FROM TopSender
                ORDER BY message_count DESC
                LIMIT 15
            """)
            
            for name, email, count in cursor.fetchall():
                display_name = name if name and name != email else email
                self.tree_senders.insert('', 'end', values=(display_name, count))

            # --- Load History ---
            for i in self.tree_history.get_children():
                self.tree_history.delete(i)
                
            cursor.execute("""
                SELECT timestamp, total_messages, inbox_count, unread_count, starred_count
                FROM EmailStats
                ORDER BY timestamp DESC
                LIMIT 100
            """)
            
            for ts, total, inbox, unread, starred in cursor.fetchall():
                dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                self.tree_history.insert('', 'end', values=(dt, total, inbox, unread, starred))
                
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Database Error", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = GmailViewerApp(root)
    root.mainloop()
