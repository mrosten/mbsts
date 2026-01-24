"""
Accurate count of tweets from January 20, 2026 onwards
"""
import sqlite3
from datetime import datetime

db_path = 'example_sprout_apps/elon_tweet_tracker/tweets.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print()
print("=" * 50)
print(" TWEET COUNT FROM JAN 20, 2026 ".center(50))
print("=" * 50)
print()

# Count tweets where created_at >= 2026-01-20
cursor.execute("""
    SELECT COUNT(DISTINCT tweet_id) 
    FROM Tweet 
    WHERE created_at >= '2026-01-20'
""")

count_since_jan20 = cursor.fetchone()[0]

# Total count
cursor.execute("SELECT COUNT(DISTINCT tweet_id) FROM Tweet")
total_count = cursor.fetchone()[0]

# Count before Jan 20
before_count = total_count - count_since_jan20

print(f"Total tweets in database: {total_count}")
print(f"Tweets BEFORE Jan 20:     {before_count}")
print(f"Tweets FROM Jan 20:       {count_since_jan20}")
print()
print("=" * 50)
print()

# Show date range
cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM Tweet WHERE created_at >= '2026-01-20'")
min_date, max_date = cursor.fetchone()
print(f"Date range (from Jan 20):")
print(f"  Earliest: {min_date}")
print(f"  Latest:   {max_date}")
print()

conn.close()
