# miktos_backend/schemas/user.py

from pydantic import BaseModel, EmailStr, Field # Added Field for potential future use
from typing import Optional, List, Dict, Any # Added Dict, Any for potential use
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
    id: str # Assuming UUIDs stored as strings, change if integer
    # is_active is inherited from UserBase
    created_at: datetime

    class Config:
        from_attributes = True # Enable ORM mode (SQLAlchemy model -> Pydantic schema)

# You might want a separate response model if UserRead exposes too much
# class UserResponse(BaseModel):
#     id: str
#     username: str
#     email: EmailStr
#     is_active: bool
#     created_at: datetime
#     class Config:
#         from_attributes = True

# ==============================================================================
# Project Schemas
# ==============================================================================

class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1) # Name is required
    description: Optional[str] = None
    context_notes: Optional[str] = None

class ProjectCreate(ProjectBase):
    # No extra fields needed beyond ProjectBase for creation
    pass

class ProjectRead(ProjectBase):
    id: str
    owner_id: str # ID of the user who owns the project
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ProjectUpdate(BaseModel):
    # All fields are optional for updates
    name: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    context_notes: Optional[str] = None

# ==============================================================================
# Message Schemas (Example - Adapt as needed)
# ==============================================================================

class MessageBase(BaseModel):
    role: str # e.g., "user", "assistant", "system"
    content: str
    model: Optional[str] = None # Which model generated the response?

class MessageCreate(MessageBase):
    # When creating, associate with a project
    project_id: str

class MessageRead(MessageBase):
    id: str
    project_id: str
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None # For token counts, latency, etc.

    class Config:
        from_attributes = True