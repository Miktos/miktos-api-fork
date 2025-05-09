#!/usr/bin/env python3
"""
Script to directly test authentication by bypassing the API and using
the repository and database classes directly.
"""
import sys
import uuid
from pathlib import Path

# Add the project root to the Python path to import application modules
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Import necessary modules
from config.database import SessionLocal
from repositories.user_repository import UserRepository
from utils.password_utils import get_password_hash, verify_password
from models.database_models import User
from sqlalchemy import create_engine, inspect
import sqlite3

# Config
USERNAME = "admin"
EMAIL = "admin@miktos.com"
PASSWORD = "admin_secure_password"

def print_header(title):
    print("\n" + "=" * 50)
    print(f" {title} ".center(50))
    print("=" * 50)

def print_section(title):
    print("\n" + "-" * 40)
    print(f" {title} ".center(40))
    print("-" * 40)

def reset_admin_password():
    """Reset the admin password directly in the SQLite database"""
    print_section("Resetting Admin Password in Database")
    
    conn = sqlite3.connect("miktos_local.db")
    cursor = conn.cursor()
    
    hashed_password = get_password_hash(PASSWORD)
    print(f"Generated password hash: {hashed_password}")
    
    cursor.execute("UPDATE users SET hashed_password = ? WHERE username = ?", 
                  (hashed_password, USERNAME))
    conn.commit()
    
    # Verify the update
    cursor.execute("SELECT hashed_password FROM users WHERE username = ?", (USERNAME,))
    result = cursor.fetchone()
    print(f"Updated password hash in database: {result[0]}")
    conn.close()

def test_direct_authentication():
    """Test authentication directly using the UserRepository"""
    print_section("Testing Direct Authentication")
    
    # Initialize database session
    db = SessionLocal()
    
    try:
        # Create repository
        user_repo = UserRepository(db)
        
        # Test authenticate with username
        print("\n> Testing authentication with USERNAME:")
        user = user_repo.authenticate(USERNAME, PASSWORD)
        if user:
            print(f"✅ Authentication SUCCESS with username")
            print(f"User ID: {user.id}")
            print(f"Username: {user.username}")
            print(f"Email: {user.email}")
            print(f"Is Admin: {getattr(user, 'is_admin', 'N/A')}")
        else:
            print(f"❌ Authentication FAILED with username")
        
        # Test authenticate with email
        print("\n> Testing authentication with EMAIL:")
        user = user_repo.authenticate(EMAIL, PASSWORD)
        if user:
            print(f"✅ Authentication SUCCESS with email")
            print(f"User ID: {user.id}")
            print(f"Username: {user.username}")
            print(f"Email: {user.email}")
            print(f"Is Admin: {getattr(user, 'is_admin', 'N/A')}")
        else:
            print(f"❌ Authentication FAILED with email")
        
    finally:
        db.close()

def test_password_verification():
    """Test password verification directly"""
    print_section("Testing Password Verification")
    
    conn = sqlite3.connect("miktos_local.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT hashed_password FROM users WHERE username = ?", (USERNAME,))
    result = cursor.fetchone()
    
    if result:
        hashed_password = result[0]
        print(f"Stored password hash: {hashed_password}")
        
        # Test direct verification
        is_valid = verify_password(PASSWORD, hashed_password)
        print(f"Direct password verification result: {is_valid}")
    else:
        print(f"No user found with username: {USERNAME}")
    
    conn.close()

def check_user_model():
    """Check the User model structure"""
    print_section("Checking User Model in Database")
    
    engine = create_engine("sqlite:///miktos_local.db")
    inspector = inspect(engine)
    
    # Check if the table exists
    if "users" in inspector.get_table_names():
        print("✅ 'users' table exists in database")
        
        # Get columns
        columns = inspector.get_columns("users")
        print("\nColumns in users table:")
        for column in columns:
            print(f"- {column['name']}: {column['type']}")
        
        # Check specifically for is_admin column
        has_admin_column = any(col["name"] == "is_admin" for col in columns)
        if has_admin_column:
            print("\n✅ 'is_admin' column exists in users table")
        else:
            print("\n❌ 'is_admin' column is MISSING from users table")
    else:
        print("❌ 'users' table does not exist in database")
    
    # Now check the SQLAlchemy model
    print("\nAttributes in SQLAlchemy User model:")
    for attr in dir(User):
        if not attr.startswith("_") and attr != "metadata":
            print(f"- {attr}")
    
    # Check specifically for is_admin attribute
    if hasattr(User, "is_admin"):
        print("\n✅ 'is_admin' attribute exists in User model")
    else:
        print("\n❌ 'is_admin' attribute is MISSING from User model")

def main():
    print_header("Direct Authentication Testing")
    
    # First check the user model to confirm is_admin exists
    check_user_model()
    
    # Reset the admin password to ensure it's correct
    reset_admin_password()
    
    # Test direct password verification
    test_password_verification()
    
    # Test direct authentication
    test_direct_authentication()
    
    print_header("Test Complete")

if __name__ == "__main__":
    main()
