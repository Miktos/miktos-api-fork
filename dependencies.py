# miktos_backend/dependencies.py
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
import os
from typing import Generator  # Add this import

# Database connection
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./miktos.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:  # Updated return type
    """Dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()