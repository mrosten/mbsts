import sqlite3

db_path = 'example_sprout_apps/elon_tweet_tracker/tweets.db'  # Fixed path!
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables:", [t[0] for t in tables])

# Check tweet count
try:
    cursor.execute("SELECT COUNT(*) FROM Tweet")
    count = cursor.fetchone()[0]
    print(f"Tweet count: {count}")
    
    if count > 0:
        cursor.execute("SELECT tweet_id, text, created_at, fetched_at FROM Tweet ORDER BY fetched_at DESC LIMIT 3")
        tweets = cursor.fetchall()
        print("\nLatest tweets:")
        for tweet in tweets:
            print(f"\nID: {tweet[0]}")
            print(f"Text: {tweet[1][:100]}...")
            print(f"Created: {tweet[2]}")
            print(f"Fetched: {tweet[3]}")
except Exception as e:
    print(f"Error querying tweets: {e}")

conn.close()
