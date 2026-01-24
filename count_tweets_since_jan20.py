"""
Count Elon's tweets from January 20, 2026 12:00 PM ET to now
"""
import sqlite3
from datetime import datetime, timezone
import pytz

# January 20, 2026, 12:00 PM ET
et = pytz.timezone('US/Eastern')
start_time = et.localize(datetime(2026, 1, 20, 12, 0, 0))
start_timestamp = int(start_time.timestamp())

# Now
now_timestamp = int(datetime.now().timestamp())

# Convert to readable format
start_str = start_time.strftime("%Y-%m-%d %I:%M %p %Z")
now_str = datetime.now().strftime("%Y-%m-%d %I:%M %p")

print()
print("=" * 50)
print(" ELON MUSK TWEET COUNTER ".center(50))
print("=" * 50)
print()
print(f"From: {start_str}")
print(f"To:   {now_str} (Local)")
print()
print("-" * 50)

# Query database
db_path = 'example_sprout_apps/elon_tweet_tracker/tweets.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Count tweets where created_at is after Jan 20, 12 PM ET
# The created_at field is ISO format like "2026-01-23T19:09:24.000Z"
cursor.execute("""
    SELECT COUNT(DISTINCT text) 
    FROM Tweet 
    WHERE created_at >= ?
""", (start_time.strftime("%Y-%m-%d"),))

count = cursor.fetchone()[0]

print()
print(f"  Total Tweets: {count}")
print()
print("=" * 50)
print()

# Show some sample tweets from that period
cursor.execute("""
    SELECT DISTINCT text, created_at 
    FROM Tweet 
    WHERE created_at >= ?
    ORDER BY created_at DESC
    LIMIT 3
""", (start_time.strftime("%Y-%m-%d"),))

print("Sample recent tweets:")
print()
for i, (text, created) in enumerate(cursor.fetchall(), 1):
    preview = text[:60] + "..." if len(text) > 60 else text
    print(f"{i}. [{created[:16]}] {preview}")

conn.close()
print()
