# models/database_models.py
from sqlalchemy import (Boolean, Column, ForeignKey, Integer, String, Text,
                        DateTime, JSON, Enum)
from sqlalchemy.dialects.postgresql import UUID  # We'll use PostgreSQL's UUID type and have sqlite handle it as a string
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from config.database import Base
import uuid
import enum

# Create a custom UUID type for SQLite compatibility
class GUID(TypeDecorator):
    """Platform-independent GUID type.
    
    Uses PostgreSQL's UUID type when available, otherwise uses
    String(36), storing as stringified UUID.
    """
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            if isinstance(value, str):
                # Convert string to UUID if needed
                try:
                    return str(uuid.UUID(value))
                except (ValueError, AttributeError):
                    return str(value)
            else:
                # Already UUID object
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                try:
                    return uuid.UUID(value)
                except (ValueError, AttributeError):
                    return value
            else:
                return value

# Enum for Context Status
class ContextStatus(enum.Enum):
    PENDING = "PENDING"
    INDEXING = "INDEXING"
    READY = "READY"
    FAILED = "FAILED"
    NONE = "NONE"

class User(Base):
    __tablename__ = "users"
    # Use custom GUID type
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, index=True, nullable=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    projects = relationship("Project", back_populates="owner")
    messages = relationship("Message", back_populates="user")

class Project(Base):
    __tablename__ = "projects"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    context_notes = Column(Text, nullable=True)
    # Use custom GUID type for foreign key
    owner_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    repository_url = Column(String, nullable=True)
    context_status = Column(Enum(ContextStatus), default=ContextStatus.NONE, nullable=False)

    owner = relationship("User", back_populates="projects")
    messages = relationship("Message", back_populates="project", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    # Use custom GUID type
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    # Use custom GUID type for foreign keys
    project_id = Column(GUID(), ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    model = Column(String, nullable=True)
    message_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project", back_populates="messages")
    user = relationship("User", back_populates="messages")