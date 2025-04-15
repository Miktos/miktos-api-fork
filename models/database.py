# miktos_backend/models/database.py
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, JSON, Float, CheckConstraint, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import datetime
import os

# Create base class for declarative models
Base = declarative_base()

# User model
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True)

# Database connection functions
def get_engine(db_url=None):
    if db_url is None:
        db_url = os.environ.get("DATABASE_URL", "sqlite:///./miktos.db")
    return create_engine(db_url)

def get_session_factory(engine=None):
    if engine is None:
        engine = get_engine()
    return sessionmaker(bind=engine)

def init_db(db_url=None):
    """Initialize the database, creating all tables if they don't exist."""
    engine = get_engine(db_url)
    Base.metadata.create_all(engine)
    return get_session_factory(engine)()