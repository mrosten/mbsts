"""
Gmail Stats Viewer - Simple CLI
"""
import sqlite3
from datetime import datetime
import os

db_path = 'gmail.db'

if not os.path.exists(db_path):
    print("\nNo data yet! Run run_gmail_tracker.bat first.\n")
    exit()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("\n" + "="*60)
print(" GMAIL INBOX STATISTICS ".center(60))
print("="*60 + "\n")

# Latest stats
cursor.execute("""
    SELECT timestamp, total_messages, inbox_count, unread_count, starred_count
    FROM EmailStats
    ORDER BY timestamp DESC
    LIMIT 1
""")

result = cursor.fetchone()
if result:
    ts, total, inbox, unread, starred = result
    dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"Last Updated: {dt}")
    print()
    print(f"  Total Messages: {total:,}")
    print(f"  Inbox:          {inbox:,}")
    print(f"  Unread:         {unread:,}")
    print(f"  Starred:        {starred:,}")
else:
    print("No stats collected yet...")

print("\n" + "-"*60)
print(" TOP 10 SENDERS ".center(60))
print("-"*60 + "\n")

cursor.execute("""
    SELECT sender_name, sender_email, message_count
    FROM TopSender
    ORDER BY message_count DESC
    LIMIT 10
""")

for i, (name, email, count) in enumerate(cursor.fetchall(), 1):
    display = f"{name} <{email}>" if name != email else email
    print(f"{i:2d}. {display[:50]:<50} ({count} msgs)")

print("\n" + "="*60 + "\n")

# Stats over time
cursor.execute("SELECT COUNT(*) FROM EmailStats")
total_records = cursor.fetchone()[0]
print(f"{total_records} data points collected")

if total_records > 1:
    cursor.execute("""
        SELECT 
            MIN(timestamp) as first,
            MAX(timestamp) as last
        FROM EmailStats
    """)
    first, last = cursor.fetchone()
    first_dt = datetime.fromtimestamp(first).strftime("%Y-%m-%d %H:%M")
    last_dt = datetime.fromtimestamp(last).strftime("%Y-%m-%d %H:%M")
    print(f"   From: {first_dt}")
    print(f"   To:   {last_dt}")

conn.close()
print()
