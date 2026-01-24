"""
Beautiful tweet viewer with word wrapping
"""
import sqlite3
import datetime
import textwrap

WIDTH = 40  # Character width for wrapping

db_path = 'example_sprout_apps/elon_tweet_tracker/tweets.db'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get count
    cursor.execute('SELECT COUNT(*) FROM Tweet')
    count = cursor.fetchone()[0]
    
    print()
    print("=" * WIDTH)
    print("  ELON MUSK TWEET TRACKER".center(WIDTH))
    print("=" * WIDTH)
    print(f"\nTotal tweets: {count}".center(WIDTH))
    print()
    print("-" * WIDTH)
    print(" LATEST 5 TWEETS ".center(WIDTH))
    print("-" * WIDTH)
    
    # Get latest tweets
    cursor.execute('SELECT text, created_at, fetched_at FROM Tweet ORDER BY fetched_at DESC LIMIT 5')
    tweets = cursor.fetchall()
    
    for i, (text, created_at, fetched_at) in enumerate(tweets, 1):
        print()
        # Header
        fetch_time = datetime.datetime.fromtimestamp(fetched_at).strftime("%Y-%m-%d %H:%M")
        post_date = created_at[:10] if created_at else "Unknown"
        
        print(f"[{i}] {fetch_time}")
        print(f"    Posted: {post_date}")
        print()
        
        # Word-wrapped tweet text
        wrapped = textwrap.fill(text, width=WIDTH, initial_indent="    ", subsequent_indent="    ")
        print(wrapped)
        print()
        print("-" * WIDTH)
    
    conn.close()
    print()
    
except Exception as e:
    print()
    print("=" * WIDTH)
    print(" ERROR ".center(WIDTH))
    print("=" * WIDTH)
    print()
    print(f"Could not read tweets: {e}")
    print()
    print("Make sure tracker is running:")
    print("  run_elon_tracker.bat")
    print()
