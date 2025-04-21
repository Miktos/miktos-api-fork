# miktos_backend/models/database_models.py
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from config.database import Base
from sqlalchemy.orm import relationship # Ensure this is imported
from sqlalchemy import Column, ForeignKey, String, Text, DateTime, JSON # Ensure ForeignKey is imported
from sqlalchemy.orm import relationship # Ensure relationship is imported
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    username = Column(String, unique=True, index=True, nullable=True)  # Make username optional
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    projects = relationship("Project", back_populates="owner")
    messages = relationship("Message", back_populates="user")
    
class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    context_notes = Column(Text, nullable=True)  # Plain text context for the project
    owner_id = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="projects")
    messages = relationship("Message", back_populates="project")

class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True) # Added nullable=False, index=True
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True) # <--- ADD THIS COLUMN
    role = Column(String, nullable=False) # 'user' or 'assistant' # Added nullable=False
    content = Column(Text, nullable=False) # Added nullable=False
    model = Column(String, nullable=True)
    message_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False) # Added nullable=False

    # Relationships
    project = relationship("Project", back_populates="messages")
    user = relationship("User", back_populates="messages") # <--- ADD THIS RELATIONSHIP