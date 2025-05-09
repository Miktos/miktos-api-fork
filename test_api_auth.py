#!/usr/bin/env python3
"""
Test script for directly testing authentication with the API using requests.
This will help us diagnose login issues step by step.
"""
import sys
import uuid
import json
import requests
import sqlite3
from pathlib import Path
import time

# Add the project root to the Python path to import application modules
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from utils.password_utils import get_password_hash

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1"
USERNAME = "admin"
EMAIL = "admin@miktos.com"
PASSWORD = "admin_secure_password"

def print_header(text):
    print("\n" + "=" * 80)
    print(f" {text} ".center(80, "="))
    print("=" * 80)

def print_section(text):
    print("\n" + "-" * 60)
    print(f" {text} ".center(60, "-"))
    print("-" * 60)

def print_json(data):
    """Pretty-print JSON data"""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            print(data)
            return
    print(json.dumps(data, indent=2))

def ensure_admin_user():
    """Make sure the admin user exists with correct credentials"""
    print_section("Ensuring admin user exists")
    conn = sqlite3.connect("miktos_local.db")
    cursor = conn.cursor()

    # Check if user exists
    cursor.execute("SELECT id, username, email, hashed_password, is_admin FROM users WHERE username = ?", (USERNAME,))
    user = cursor.fetchone()

    if user:
        print(f"Admin user exists: {user[0]}")
        
        # Update the password and ensure admin privileges
        hashed_password = get_password_hash(PASSWORD)
        cursor.execute(
            "UPDATE users SET hashed_password = ?, is_admin = 1 WHERE id = ?",
            (hashed_password, user[0])
        )
        print(f"Updated admin user password hash: {hashed_password[:20]}...")
    else:
        # Create new admin user
        user_id = str(uuid.uuid4())
        hashed_password = get_password_hash(PASSWORD)
        try:
            cursor.execute(
                "INSERT INTO users (id, username, email, hashed_password, is_active, is_admin) VALUES (?, ?, ?, ?, 1, 1)",
                (user_id, USERNAME, EMAIL, hashed_password)
            )
            print(f"Created new admin user with ID: {user_id}")
        except sqlite3.IntegrityError as e:
            print(f"Error creating user: {e}")
    
    conn.commit()
    
    # Verify the user after update
    cursor.execute("SELECT id, username, email, substr(hashed_password, 1, 20) as pwd_preview, is_admin FROM users WHERE username = ?", (USERNAME,))
    user = cursor.fetchone()
    print(f"Admin user after update: ID={user[0]}, Username={user[1]}, Email={user[2]}, PwdHash={user[3]}..., IsAdmin={user[4]}")
    conn.close()
    return user[0]

def test_auth_endpoint_with_username():
    """Test authentication using username"""
    print_section("Testing auth with username")
    response = requests.post(
        f"{API_BASE_URL}/auth/token",
        data={"username": USERNAME, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    print(f"Status code: {response.status_code}")
    if response.status_code != 200:
        print(f"Error response:")
        print_json(response.json())
        return None
    else:
        print("Login successful!")
        token_data = response.json()
        print_json(token_data)
        return token_data

def test_auth_endpoint_with_email():
    """Test authentication using email"""
    print_section("Testing auth with email")
    response = requests.post(
        f"{API_BASE_URL}/auth/token",
        data={"username": EMAIL, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    print(f"Status code: {response.status_code}")
    if response.status_code != 200:
        print(f"Error response:")
        print_json(response.json())
        return None
    else:
        print("Login successful!")
        token_data = response.json()
        print_json(token_data)
        return token_data

def test_me_endpoint(token):
    """Test accessing the /users/me endpoint with the token"""
    print_section("Testing /users/me endpoint")
    if not token:
        print("No token available, skipping test")
        return
        
    response = requests.get(
        f"{API_BASE_URL}/auth/users/me",
        headers={"Authorization": f"Bearer {token['access_token']}"}
    )
    print(f"Status code: {response.status_code}")
    if response.status_code != 200:
        print(f"Error response:")
        print_json(response.json())
    else:
        print("User details retrieved successfully:")
        print_json(response.json())

def test_admin_endpoints(token):
    """Test accessing admin endpoints with the token"""
    print_section("Testing admin endpoints")
    if not token:
        print("No token available, skipping test")
        return
        
    response = requests.get(
        f"{API_BASE_URL}/admin/stats",
        headers={"Authorization": f"Bearer {token['access_token']}"}
    )
    print(f"Status code: {response.status_code}")
    if response.status_code != 200:
        print(f"Error response:")
        print_json(response.json())
    else:
        print("Admin stats retrieved successfully:")
        print_json(response.json())

def main():
    print_header("Miktos API Authentication Test")
    
    # Step 1: Ensure admin user exists with correct credentials
    user_id = ensure_admin_user()
    
    # Skip test user creation as it's causing issues
    # test_username, test_password = create_test_user()
    
    # Step 3: Test authentication with username
    token = test_auth_endpoint_with_username()
    
    # Step 4: Test authentication with email
    if not token:
        token = test_auth_endpoint_with_email()
    
    # Step 5: Test accessing /users/me endpoint
    test_me_endpoint(token)
    
    # Step 6: Test accessing admin endpoints
    if token:
        test_admin_endpoints(token)
        
    print_header("Test Complete")
    if token:
        print("✅ Successfully authenticated!")
    else:
        print("❌ Authentication failed!")

if __name__ == "__main__":
    main()
