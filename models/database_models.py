# models/database_models.py
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, DateTime, JSON, Enum #<-- Import Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from config.database import Base
import uuid
import enum # <-- Import enum

# --- NEW: Enum for Context Status ---
class ContextStatus(enum.Enum):
    PENDING = "PENDING"       # Waiting to be indexed
    INDEXING = "INDEXING"     # Indexing in progress
    READY = "READY"           # Indexing complete and usable
    FAILED = "FAILED"         # Indexing failed
    NONE = "NONE"             # No repository URL provided

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    # ... (User model remains the same) ...
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
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

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    context_notes = Column(Text, nullable=True)
    owner_id = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # --- ADDED Fields for Codebase Context ---
    repository_url = Column(String, nullable=True) # Store the Git repository URL
    context_status = Column(Enum(ContextStatus), default=ContextStatus.NONE, nullable=False) # Track indexing status

    # Relationships
    owner = relationship("User", back_populates="projects")
    messages = relationship(
        "Message",
        back_populates="project",
        cascade="all, delete-orphan"
    )

class Message(Base):
    # ... (Message model remains the same) ...
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    model = Column(String, nullable=True)
    message_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project", back_populates="messages")
    user = relationship("User", back_populates="messages")