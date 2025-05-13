"""
User Activities Migration

This script creates the user_activities table for tracking user activity
in existing databases. Run this script after deploying the activity tracking feature.

Usage: python migrations/add_user_activities_table.py
"""

import os
import sys
from sqlalchemy import create_engine, Column, String, ForeignKey, DateTime, JSON
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import settings and database configuration
from config.settings import settings
from config.database import GUID

# Create a temporary Base class for this migration
Base = declarative_base()

# Define the UserActivity model class for migration
class UserActivity(Base):
    __tablename__ = "user_activities"

    id = Column(GUID(), primary_key=True, default=None)  # Will use UUID function from database
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    activity_type = Column(String, nullable=False, index=True)
    endpoint = Column(String, nullable=True, index=True)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

def run_migration():
    """Run the migration to create the user_activities table."""
    print(f"Running migration to add user_activities table...")
    
    # Get database connection string from settings
    database_url = settings.DATABASE_URL
    
    # Create engine to connect to the database
    engine = create_engine(database_url)
    
    try:
        # Create the user_activities table
        UserActivity.__table__.create(engine)
        print(f"✅ Successfully created user_activities table")
        return True
    except Exception as e:
        print(f"❌ Error creating user_activities table: {str(e)}")
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
