"""
Reset Tweet Database - Clean slate
"""
import sqlite3
import os

db_path = 'example_sprout_apps/elon_tweet_tracker/tweets.db'

print("\n" + "="*60)
print(" DATABASE RESET ".center(60))
print("="*60 + "\n")

print("⚠️  WARNING: This will DELETE all tweets from the database!")
print()

response = input("Type 'YES' to confirm reset: ").strip()

if response.upper() != 'YES':
    print("\nReset cancelled.\n")
    exit()

print("\n🗑️  Deleting database file...")
if os.path.exists(db_path):
    os.remove(db_path)
    print("✅ Database deleted")
else:
    print("⚠️  Database file not found (already clean)")

print("\n✅ Reset complete! Database is now empty.")
print("\nRun backfill_tweets.bat to collect fresh tweets.\n")
