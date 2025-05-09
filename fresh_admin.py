#!/usr/bin/env python3
import sys
from pathlib import Path

# Add the project root to the Python path to import application modules
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from utils.password_utils import get_password_hash
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid
from models.database_models import User, Base

# Create the database connection
engine = create_engine("sqlite:///miktos_local.db")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

def create_fresh_admin():
    # Admin credentials
    admin_username = "admin123"
    admin_email = "admin123@miktos.com"
    admin_password = "Admin123!"
    
    print(f"\n=== Creating Fresh Admin User ===")
    print(f"Username: {admin_username}")
    print(f"Email: {admin_email}")
    print(f"Password: {admin_password}")
    
    # Hash the password
    hashed_password = get_password_hash(admin_password)
    print(f"Hashed password: {hashed_password}")
    
    # Check if user exists
    existing_user = db.query(User).filter(
        (User.username == admin_username) | (User.email == admin_email)
    ).first()
    
    if existing_user:
        print(f"User already exists with ID: {existing_user.id}")
        print(f"Updating credentials and admin status...")
        existing_user.username = admin_username
        existing_user.email = admin_email
        existing_user.hashed_password = hashed_password
        existing_user.is_admin = True
        db.commit()
        db.refresh(existing_user)
        print(f"Updated user: {existing_user.id}, is_admin={existing_user.is_admin}")
    else:
        # Create new user
        new_admin = User(
            id=str(uuid.uuid4()),
            username=admin_username,
            email=admin_email,
            hashed_password=hashed_password,
            is_active=True,
            is_admin=True
        )
        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)
        print(f"Created new admin user with ID: {new_admin.id}")
    
    print("=== Done ===\n")

if __name__ == "__main__":
    create_fresh_admin()
    db.close()
