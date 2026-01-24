import sqlite3

db = sqlite3.connect('example_sprout_apps/elon_tweet_tracker/tweets.db')
c = db.cursor()

# Count from Jan 20
c.execute("SELECT COUNT(DISTINCT tweet_id) FROM Tweet WHERE created_at >= '2026-01-20'")
count = c.fetchone()[0]

print(f"\nTweets from Jan 20, 2026 onwards: {count}\n")

# Check if we need more
if count < 208:
    missing = 208 - count
    print(f"Missing approximately {missing} tweets")
    print("The backfill may not have scrolled far enough.")
else:
    print("✅ Complete collection!")

db.close()
