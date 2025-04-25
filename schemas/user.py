# miktos_backend/schemas/user.py

# Make sure ConfigDict is imported
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

# ==============================================================================
# User Schemas
# ==============================================================================

# Base properties shared by all user schemas
class UserBase(BaseModel):
    username: str
    email: EmailStr
    is_active: Optional[bool] = True # Default to active, can be overridden

# Properties needed when creating a new user (received via API)
class UserCreate(UserBase):
    password: str = Field(..., min_length=8) # Add validation rule example: min 8 chars

# Properties needed when updating a user (received via API)
class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8) # Allow optional password update
    is_active: Optional[bool] = None

# Properties to return to the client (never include password)
class UserRead(UserBase):
    # Use model_config = ConfigDict(...) instead of class Config
    model_config = ConfigDict(from_attributes=True) # Enable ORM mode (SQLAlchemy model -> Pydantic schema)

    id: str # Assuming UUIDs stored as strings, change if integer
    # is_active is inherited from UserBase
    created_at: datetime


# ==============================================================================
# Project Schemas (WARNING: These should ideally be in schemas/project.py)
# ==============================================================================

class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1) # Name is required
    description: Optional[str] = None
    context_notes: Optional[str] = None

class ProjectCreate(ProjectBase):
    # No extra fields needed beyond ProjectBase for creation
    pass

class ProjectRead(ProjectBase):
    # Use model_config = ConfigDict(...) instead of class Config
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str # ID of the user who owns the project
    created_at: datetime
    updated_at: Optional[datetime] = None

class ProjectUpdate(BaseModel):
    # All fields are optional for updates
    name: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    context_notes: Optional[str] = None

# ==============================================================================
# Message Schemas (WARNING: These should ideally be in schemas/message.py)
# ==============================================================================

class MessageBase(BaseModel):
    role: str # e.g., "user", "assistant", "system"
    content: str
    model: Optional[str] = None # Which model generated the response?

class MessageCreate(MessageBase):
    # When creating, associate with a project
    project_id: str

# --- ADDED THIS SCHEMA ---
class MessageUpdate(BaseModel):
    # Define fields that can be updated for a message
    # Typically, you might only allow content updates, or maybe metadata
    content: Optional[str] = None
    # metadata: Optional[Dict[str, Any]] = None # Example if you store metadata
# --- END ADDITION ---

class MessageRead(MessageBase):
    # Use model_config = ConfigDict(...) instead of class Config
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None # For token counts, latency, etc.