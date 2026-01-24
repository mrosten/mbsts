"""
Test database init manually
"""
import asyncio
import sys
sys.path.insert(0, '.')

from sprout.configuration import SproutConfiguration
from sprout.database import initialize_database
from example_sprout_apps.elon_tweet_tracker.data import classes as tweet_classes

async def test_db():
    print("Loading config...")
    config = SproutConfiguration(path='example_sprout_apps/elon_tweet_tracker/').config
    
    print(f"Config loaded. DB file: {config.db.sqlite.storage_file}")
    
    print("Initializing database...")
    await initialize_database(config, config.db.sqlite.storage_file, tweet_classes)
    
    print("✅ Database initialized!")
    
    # Try to create a tweet
    print("Creating test tweet...")
    import time
    tweet = tweet_classes.Tweet("test_123")
    await tweet.set(
        tweet_id="test_123",
        text="This is a test tweet",
        created_at="2026-01-23",
        retweet_count=0,
        favorite_count=0,
        fetched_at=int(time.time())
    )
    print("✅ Test tweet created!")
    
    # Verify
    import sqlite3
    db = sqlite3.connect(config.db.sqlite.storage_file)
    c = db.cursor()
    c.execute("SELECT COUNT(*) FROM Tweet")
    count = c.fetchone()[0]
    print(f"✅ Tweet count in DB: {count}")
    
    if count > 0:
        c.execute("SELECT tweet_id, text FROM Tweet")
        for row in c.fetchall():
            print(f"   - {row[0]}: {row[1]}")
    
    db.close()

asyncio.run(test_db())
print("\n✅ Test complete!")
