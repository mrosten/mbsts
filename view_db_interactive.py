"""
Interactive SQLite Database Viewer - Terminal GUI
"""
import sqlite3
import textwrap
from datetime import datetime

WIDTH = 70

def clear_screen():
    import os
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(text):
    print("\n" + "=" * WIDTH)
    print(text.center(WIDTH))
    print("=" * WIDTH + "\n")

def view_all_tweets():
    """View all tweets with pagination"""
    db = sqlite3.connect('example_sprout_apps/elon_tweet_tracker/tweets.db')
    c = db.cursor()
    
    c.execute("SELECT COUNT(*) FROM Tweet")
    total = c.fetchone()[0]
    
    page_size = 5
    offset = 0
    
    while True:
        clear_screen()
        print_header(f"ALL TWEETS (Showing {offset+1}-{min(offset+page_size, total)} of {total})")
        
        c.execute("""
            SELECT tweet_id, text, created_at, fetched_at 
            FROM Tweet 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
        """, (page_size, offset))
        
        tweets = c.fetchall()
        
        for i, (tid, text, created, fetched) in enumerate(tweets, offset+1):
            print(f"\n[{i}] ID: {tid[:30]}...")
            print(f"    Created: {created[:19]}")
            print(f"    Fetched: {datetime.fromtimestamp(fetched).strftime('%Y-%m-%d %H:%M')}")
            print()
            wrapped = textwrap.fill(text, width=WIDTH-4, initial_indent="    ", subsequent_indent="    ")
            print(wrapped)
            print("-" * WIDTH)
        
        print(f"\n[N]ext page | [P]revious | [B]ack to menu")
        choice = input("Choice: ").strip().lower()
        
        if choice == 'n' and offset + page_size < total:
            offset += page_size
        elif choice == 'p' and offset > 0:
            offset -= page_size
        elif choice == 'b':
            break
    
    db.close()

def search_tweets():
    """Search tweets by keyword"""
    keyword = input("\nEnter search keyword: ").strip()
    if not keyword:
        return
    
    db = sqlite3.connect('example_sprout_apps/elon_tweet_tracker/tweets.db')
    c = db.cursor()
    
    c.execute("""
        SELECT tweet_id, text, created_at 
        FROM Tweet 
        WHERE text LIKE ? 
        ORDER BY created_at DESC
    """, (f'%{keyword}%',))
    
    results = c.fetchall()
    
    clear_screen()
    print_header(f"SEARCH RESULTS: '{keyword}' ({len(results)} found)")
    
    for i, (tid, text, created) in enumerate(results[:10], 1):
        print(f"\n[{i}] {created[:19]}")
        wrapped = textwrap.fill(text, width=WIDTH-4, initial_indent="    ", subsequent_indent="    ")
        print(wrapped)
        print("-" * WIDTH)
    
    if len(results) > 10:
        print(f"\n(Showing first 10 of {len(results)} results)")
    
    input("\n\nPress Enter to continue...")
    db.close()

def view_stats():
    """Show database statistics"""
    db = sqlite3.connect('example_sprout_apps/elon_tweet_tracker/tweets.db')
    c = db.cursor()
    
    clear_screen()
    print_header("DATABASE STATISTICS")
    
    # Total count
    c.execute("SELECT COUNT(*) FROM Tweet")
    total = c.fetchone()[0]
    print(f"  Total tweets: {total}")
    
    # From Jan 20
    c.execute("SELECT COUNT(*) FROM Tweet WHERE created_at >= '2026-01-20'")
    from_jan20 = c.fetchone()[0]
    print(f"  From Jan 20:  {from_jan20}")
    
    # Date range
    c.execute("SELECT MIN(created_at), MAX(created_at) FROM Tweet")
    min_date, max_date = c.fetchall()[0]
    print(f"\n  Earliest: {min_date[:19]}")
    print(f"  Latest:   {max_date[:19]}")
    
    # Tweets by date
    print(f"\n  Tweets by date:")
    c.execute("""
        SELECT DATE(created_at) as day, COUNT(*) as count
        FROM Tweet
        GROUP BY day
        ORDER BY day DESC
        LIMIT 5
    """)
    for day, count in c.fetchall():
        print(f"    {day}: {count} tweets")
    
    input("\n\nPress Enter to continue...")
    db.close()

def view_latest():
    """View latest 10 tweets"""
    db = sqlite3.connect('example_sprout_apps/elon_tweet_tracker/tweets.db')
    c = db.cursor()
    
    clear_screen()
    print_header("LATEST 10 TWEETS")
    
    c.execute("""
        SELECT text, created_at, fetched_at
        FROM Tweet
        ORDER BY created_at DESC
        LIMIT 10
    """)
    
    for i, (text, created, fetched) in enumerate(c.fetchall(), 1):
        print(f"\n[{i}] {created[:19]}")
        wrapped = textwrap.fill(text, width=WIDTH-4, initial_indent="    ", subsequent_indent="    ")
        print(wrapped)
        print("-" * WIDTH)
    
    input("\n\nPress Enter to continue...")
    db.close()

def main_menu():
    while True:
        clear_screen()
        print_header("ELON MUSK TWEET DATABASE VIEWER")
        
        print("  [1] View latest tweets")
        print("  [2] Browse all tweets")
        print("  [3] Search tweets")
        print("  [4] View statistics")
        print("  [Q] Quit")
        print()
        
        choice = input("Select option: ").strip().lower()
        
        if choice == '1':
            view_latest()
        elif choice == '2':
            view_all_tweets()
        elif choice == '3':
            search_tweets()
        elif choice == '4':
            view_stats()
        elif choice == 'q':
            print("\nGoodbye!\n")
            break

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\nExiting...\n")
