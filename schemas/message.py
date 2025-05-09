# schemas/message.py
import enum
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


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
    model_config = ConfigDict(
        from_attributes=True,  # Pydantic v2 style (replaces orm_mode)
    )
    
    # Override serialization methods for UUID and datetime
    @classmethod
    def model_serializer(cls, obj, **kwargs):
        data = super().model_serializer(obj, **kwargs)
        # Convert UUID to string
        if "id" in data and isinstance(data["id"], uuid.UUID):
            data["id"] = str(data["id"])
        if "project_id" in data and isinstance(data["project_id"], uuid.UUID):
            data["project_id"] = str(data["project_id"])
        if "user_id" in data and isinstance(data["user_id"], uuid.UUID):
            data["user_id"] = str(data["user_id"])
        # Convert datetime to ISO format
        for field, value in data.items():
            if isinstance(value, datetime):
                data[field] = value.isoformat()
        return data

    id: str
    project_id: str
    user_id: str
    role: MessageRole
    content: str
    model: Optional[str] = None
    message_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    # Add model_dump method for direct serialization if needed
    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        # Convert datetime to ISO string if needed (Pydantic usually handles this)
        if "created_at" in data and isinstance(data["created_at"], datetime):
            data["created_at"] = data["created_at"].isoformat()
        return data


# Optional: If your BaseRepository needs an Update schema
class MessageUpdate(BaseModel):
    content: Optional[str] = None
    message_metadata: Optional[Dict[str, Any]] = None
    # Add other updatable fields if necessary
