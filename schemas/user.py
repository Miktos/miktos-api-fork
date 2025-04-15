# miktos_backend/schemas/user.py

from typing import Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime

# Shared properties
class UserBase(BaseModel):
    username: str
    email: EmailStr
    is_active: Optional[bool] = True

# Properties to receive on user creation
class UserCreate(UserBase):
    password: str

# Properties to receive on user update
class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

# Properties to return to client
class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True