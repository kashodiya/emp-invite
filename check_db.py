import sqlite3

# Connect to database and check structure
conn = sqlite3.connect('employee_database.db')
cursor = conn.cursor()

# Get table schema
cursor.execute("PRAGMA table_info(employees)")
columns = cursor.fetchall()
print("Database columns:")
for col in columns:
    print(f"  {col[1]} ({col[2]})")

# Check current data for first few employees
cursor.execute("SELECT rowid, firstName, lastName, email_invite_sent, email_sent_at FROM employees LIMIT 5")
rows = cursor.fetchall()
print("\nSample data:")
for row in rows:
    print(f"  ID: {row[0]}, Name: {row[1]} {row[2]}, Email Sent: {row[3]}, Timestamp: {row[4]}")

conn.close()