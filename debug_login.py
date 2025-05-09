#!/usr/bin/env python3
import sys
import sqlite3
from pathlib import Path

# Add the project root to the Python path to import application modules
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from utils.password_utils import verify_password
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models.database_models import User
from repositories.user_repository import UserRepository

# Create a direct database connection
engine = create_engine("sqlite:///miktos_local.db")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

# Test credentials
username = "admin"
email = "admin@miktos.com"
password = "admin_secure_password"

print("\n=== DEBUGGING LOGIN PROCESS ===")

# Step 1: Get user by identifier using direct SQL and print results
print("\n1. Direct SQL query results:")
conn = sqlite3.connect("miktos_local.db")
cursor = conn.cursor()
cursor.execute("SELECT id, username, email, hashed_password, is_admin FROM users WHERE username = ? OR email = ?", (username, email))
result = cursor.fetchone()
if result:
    print(f"  User found: ID={result[0]}, Username={result[1]}, Email={result[2]}")
    print(f"  Hashed password: {result[3]}")
    print(f"  Is admin: {result[4]}")
else:
    print("  User not found in database!")
conn.close()

# Step 2: Get user by email using UserRepository
print("\n2. UserRepository.get_by_email results:")
user_repo = UserRepository(db)
user_by_email = user_repo.get_by_email(email)
if user_by_email:
    print(f"  User found: ID={user_by_email.id}, Email={user_by_email.email}")
    print(f"  Hashed password: {user_by_email.hashed_password}")
    print(f"  Has is_admin attr: {hasattr(user_by_email, 'is_admin')}")
    if hasattr(user_by_email, 'is_admin'):
        print(f"  Is admin: {user_by_email.is_admin}")
else:
    print("  User not found by email!")

# Step 3: Get user by username using UserRepository
print("\n3. UserRepository.get_by_username results:")
user_by_username = user_repo.get_by_username(username)
if user_by_username:
    print(f"  User found: ID={user_by_username.id}, Username={user_by_username.username}")
    print(f"  Hashed password: {user_by_username.hashed_password}")
    print(f"  Has is_admin attr: {hasattr(user_by_username, 'is_admin')}")
    if hasattr(user_by_username, 'is_admin'):
        print(f"  Is admin: {user_by_username.is_admin}")
else:
    print("  User not found by username!")

# Step 4: Test full authentication
print("\n4. Testing full authentication process:")
authenticated_user = user_repo.authenticate(identifier=username, password=password)
if authenticated_user:
    print(f"  Authentication successful: ID={authenticated_user.id}")
    print(f"  Has is_admin attr: {hasattr(authenticated_user, 'is_admin')}")
    if hasattr(authenticated_user, 'is_admin'):
        print(f"  Is admin: {authenticated_user.is_admin}")
else:
    print("  Authentication failed!")

# Try with email
print("\n5. Testing authentication with email:")
authenticated_user = user_repo.authenticate(identifier=email, password=password)
if authenticated_user:
    print(f"  Authentication successful: ID={authenticated_user.id}")
else:
    print("  Authentication failed!")

db.close()
print("\n=== DEBUG COMPLETE ===\n")
