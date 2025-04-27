# miktos_backend/schemas/user.py

from pydantic import BaseModel, EmailStr, Field, ConfigDict # Ensure ConfigDict is imported
from typing import Optional # Removed List, Dict, Any if only used by deleted schemas
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
    model_config = ConfigDict(from_attributes=True) # Enable ORM mode

    id: str # Assuming UUIDs stored as strings, change if integer
    # is_active is inherited from UserBase
    created_at: datetime

