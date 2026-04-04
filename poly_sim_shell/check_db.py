import sqlite3
import os

db_path = "../poly_history.db"
if not os.path.exists(db_path):
    db_path = "../../poly_history.db"
if not os.path.exists(db_path):
    print(f"Error: poly_history.db not found in {os.getcwd()} or parents")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print(f"Tables: {tables}")

for table in tables:
    t_name = table[0]
    cursor.execute(f"SELECT COUNT(*) FROM {t_name}")
    count = cursor.fetchone()[0]
    print(f"Table '{t_name}': {count} rows")

conn.close()
