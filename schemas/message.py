# schemas/message.py
import enum
# Make sure ConfigDict is imported
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, Dict, Any
import uuid # Import uuid for default ID

# Enum for message roles (good practice, aligns with frontend)
class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    # Add SYSTEM later if needed

# Schema for creating a message (input for repository)
class MessageCreate(BaseModel):
    project_id: str
    user_id: str
    role: MessageRole
    content: str
    model: Optional[str] = None
    message_metadata: Optional[Dict[str, Any]] = None

# Schema for reading a message (output for API)
class MessageRead(BaseModel):
    # Use model_config = ConfigDict(...) instead of class Config
    model_config = ConfigDict(from_attributes=True) # Pydantic v2 style (replaces orm_mode)

    id: str
    project_id: str
    user_id: str
    role: MessageRole
    content: str
    model: Optional[str] = None
    message_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

# Optional: If your BaseRepository needs an Update schema
class MessageUpdate(BaseModel):
    content: Optional[str] = None
    message_metadata: Optional[Dict[str, Any]] = None
    # Add other updatable fields if necessary