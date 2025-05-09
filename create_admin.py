#!/usr/bin/env python3
# create_admin.py
import sys
import uuid
import sqlite3
import datetime
from pathlib import Path

# Add the project root to the Python path to import application modules
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from utils.password_utils import get_password_hash

# Admin user details
password = "admin_secure_password"
hashed_password = get_password_hash(password)
user_id = str(uuid.uuid4())
username = "admin"
email = "admin@miktos.com"
is_active = True
is_admin = True
created_at = datetime.datetime.now().isoformat()

print(f"Generated password hash: {hashed_password}")

# Connect to the database
conn = sqlite3.connect("miktos_local.db")
cursor = conn.cursor()

# Check for the is_admin column, add it if it doesn't exist
cursor.execute("PRAGMA table_info(users)")
columns = [column[1] for column in cursor.fetchall()]
if "is_admin" not in columns:
    print("Adding is_admin column to users table...")
    cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0")

# Check if admin user already exists
cursor.execute("SELECT id, username, email FROM users WHERE username = ? OR email = ?", (username, email))
existing_user = cursor.fetchone()

if existing_user:
    # Update existing user to have admin privileges
    print(f"User {existing_user[1]} ({existing_user[2]}) already exists with ID {existing_user[0]}")
    cursor.execute(
        "UPDATE users SET is_admin = 1, hashed_password = ? WHERE id = ?",
        (hashed_password, existing_user[0])
    )
    print(f"Updated user to have admin privileges and set new password")
else:
    # Insert new admin user
    cursor.execute(
        "INSERT INTO users (id, username, email, hashed_password, is_active, created_at, is_admin) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, username, email, hashed_password, is_active, created_at, is_admin)
    )
    print(f"Created new admin user:")
    print(f"  ID: {user_id}")
    print(f"  Username: {username}")
    print(f"  Email: {email}")

print(f"\nAdmin credentials:")
print(f"  Username or Email: {username} or {email}")
print(f"  Password: {password}")

conn.commit()
conn.close()

print("\nAdmin user setup complete. You can now log in with these credentials.")
