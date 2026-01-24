"""
SQLite Database Viewer - Windowed GUI
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import sqlite3
from datetime import datetime

class TweetViewerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Elon Musk Tweet Database Viewer")
        self.root.geometry("900x600")
        
        # Database connection
        self.db = sqlite3.connect('example_sprout_apps/elon_tweet_tracker/tweets.db')
        self.cursor = self.db.cursor()
        
        # Create UI
        self.create_widgets()
        self.load_stats()
        self.load_tweets()
    
    def create_widgets(self):
        # Top frame - Stats
        stats_frame = tk.Frame(self.root, bg='#2c3e50', pady=10)
        stats_frame.pack(fill='x')
        
        self.stats_label = tk.Label(stats_frame, text="Loading...", 
                                    fg='white', bg='#2c3e50', 
                                    font=('Arial', 12, 'bold'))
        self.stats_label.pack()
        
        # Search frame
        search_frame = tk.Frame(self.root, pady=10)
        search_frame.pack(fill='x', padx=10)
        
        tk.Label(search_frame, text="Search:").pack(side='left', padx=5)
        self.search_entry = tk.Entry(search_frame, width=40)
        self.search_entry.pack(side='left', padx=5)
        self.search_entry.bind('<Return>', lambda e: self.search_tweets())
        
        tk.Button(search_frame, text="Search", command=self.search_tweets).pack(side='left', padx=5)
        tk.Button(search_frame, text="Show All", command=self.show_latest).pack(side='left', padx=5)
        
        # Pagination frame
        page_frame = tk.Frame(self.root, pady=5)
        page_frame.pack(fill='x', padx=10)
        
        self.page_label = tk.Label(page_frame, text="Page 1")
        self.page_label.pack(side='left', padx=10)
        
        tk.Button(page_frame, text="◄ Previous 100", command=self.prev_page).pack(side='left', padx=5)
        tk.Button(page_frame, text="Next 100 ►", command=self.next_page).pack(side='left', padx=5)
        
        # Tweet list frame
        list_frame = tk.Frame(self.root)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Treeview for tweets
        columns = ('date', 'preview')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=10)
        
        self.tree.heading('date', text='Date')
        self.tree.heading('preview', text='Tweet Preview')
        
        self.tree.column('#0', width=50)
        self.tree.column('date', width=150)
        self.tree.column('preview', width=650)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Bind selection
        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        
        # Detail frame
        detail_frame = tk.LabelFrame(self.root, text="Tweet Details", padx=10, pady=10)
        detail_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.detail_text = scrolledtext.ScrolledText(detail_frame, wrap='word', height=8)
        self.detail_text.pack(fill='both', expand=True)
        
        # Pagination state
        self.current_offset = 0
        self.page_size = 100
        self.current_query = None
    
    def load_stats(self):
        self.cursor.execute("SELECT COUNT(*) FROM Tweet")
        total = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(*) FROM Tweet WHERE created_at >= '2026-01-20'")
        from_jan20 = self.cursor.fetchone()[0]
        
        self.stats_label.config(text=f"Total Tweets: {total}  |  From Jan 20: {from_jan20}")
    
    def load_tweets(self, offset=0):
        self.current_offset = offset
        self.current_query = None
        
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Get total count
        self.cursor.execute("SELECT COUNT(*) FROM Tweet")
        total = self.cursor.fetchone()[0]
        
        # Load tweets with pagination
        self.cursor.execute("""
            SELECT tweet_id, text, created_at, fetched_at
            FROM Tweet
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (self.page_size, offset))
        
        for i, (tid, text, created, fetched) in enumerate(self.cursor.fetchall(), offset + 1):
            date_str = created[:16] if created else "Unknown"
            preview = text[:80] + "..." if len(text) > 80 else text
            
            self.tree.insert('', 'end', iid=tid, text=str(i), 
                           values=(date_str, preview),
                           tags=(tid, text, created, fetched))
        
        # Update page label
        page_num = (offset // self.page_size) + 1
        total_pages = (total + self.page_size - 1) // self.page_size
        self.page_label.config(text=f"Page {page_num} of {total_pages} | Showing {offset+1}-{min(offset+self.page_size, total)} of {total}")
    
    def next_page(self):
        self.cursor.execute("SELECT COUNT(*) FROM Tweet")
        total = self.cursor.fetchone()[0]
        
        if self.current_offset + self.page_size < total:
            if self.current_query:
                self.search_tweets(self.current_offset + self.page_size)
            else:
                self.load_tweets(self.current_offset + self.page_size)
    
    def prev_page(self):
        if self.current_offset >= self.page_size:
            if self.current_query:
                self.search_tweets(self.current_offset - self.page_size)
            else:
                self.load_tweets(self.current_offset - self.page_size)
    
    def search_tweets(self, offset=0):
        query = self.search_entry.get().strip()
        if not query:
            return
        
        self.current_offset = offset
        self.current_query = query
        
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Get count for pagination
        self.cursor.execute("""
            SELECT COUNT(*) FROM Tweet WHERE text LIKE ?
        """, (f'%{query}%',))
        total = self.cursor.fetchone()[0]
        
        # Search with pagination
        self.cursor.execute("""
            SELECT tweet_id, text, created_at, fetched_at
            FROM Tweet
            WHERE text LIKE ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (f'%{query}%', self.page_size, offset))
        
        results = self.cursor.fetchall()
        
        for i, (tid, text, created, fetched) in enumerate(results, offset + 1):
            date_str = created[:16] if created else "Unknown"
            preview = text[:80] + "..." if len(text) > 80 else text
            
            self.tree.insert('', 'end', iid=tid, text=str(i),
                           values=(date_str, preview),
                           tags=(tid, text, created, fetched))
        
        page_num = (offset // self.page_size) + 1
        total_pages = (total + self.page_size - 1) // self.page_size
        self.stats_label.config(text=f"Search: '{query}' - {total} results")
        self.page_label.config(text=f"Page {page_num} of {total_pages} | Showing {offset+1}-{min(offset+self.page_size, total)} of {total}")
    
    def show_latest(self):
        self.search_entry.delete(0, tk.END)
        self.load_tweets(0)
        self.load_stats()
    
    def on_select(self, event):
        selection = self.tree.selection()
        if not selection:
            return
        
        item = self.tree.item(selection[0])
        tags = item['tags']
        
        if len(tags) >= 4:
            tid, text, created, fetched = tags[0], tags[1], tags[2], tags[3]
            
            fetch_time = datetime.fromtimestamp(int(fetched)).strftime("%Y-%m-%d %H:%M:%S")
            
            detail = f"Tweet ID: {tid}\n"
            detail += f"Created: {created}\n"
            detail += f"Fetched: {fetch_time}\n"
            detail += f"\n{'-'*70}\n\n"
            detail += text
            
            self.detail_text.delete('1.0', tk.END)
            self.detail_text.insert('1.0', detail)
    
    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()

if __name__ == "__main__":
    root = tk.Tk()
    app = TweetViewerGUI(root)
    root.mainloop()
