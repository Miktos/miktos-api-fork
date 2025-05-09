#!/usr/bin/env python3
import sys
import sqlite3
from pathlib import Path

# Add the project root to the Python path to import application modules
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from utils.password_utils import verify_password

# Connect to the database
conn = sqlite3.connect("miktos_local.db")
cursor = conn.cursor()

# Get the admin user's hashed password
cursor.execute("SELECT hashed_password FROM users WHERE username = 'admin'")
result = cursor.fetchone()

if not result:
    print("Admin user not found in database!")
    sys.exit(1)

hashed_password = result[0]
plain_password = "admin_secure_password"

print(f"Testing password verification:")
print(f"Plain password: {plain_password}")
print(f"Hashed password: {hashed_password}")

# Test password verification
is_valid = verify_password(plain_password, hashed_password)
print(f"Password verification result: {is_valid}")

conn.close()
