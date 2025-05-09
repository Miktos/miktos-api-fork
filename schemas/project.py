# schemas/project.py
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import UUID4, BaseModel, Field

from models.database_models import ContextStatus

# --- Project Schemas ---


class ProjectCreate(BaseModel):
    """Schema for creating a new project"""

    name: str
    description: Optional[str] = None
    context_notes: Optional[str] = None
    repository_url: Optional[str] = None  # Using str instead of HttpUrl for better compatibility


class ProjectUpdate(BaseModel):
    """Schema for updating an existing project"""

    name: Optional[str] = None
    description: Optional[str] = None
    context_notes: Optional[str] = None
    repository_url: Optional[str] = None  # Using str instead of HttpUrl for better compatibility


class ProjectRead(BaseModel):
    """Schema for reading project data via API"""

    id: UUID4
    owner_id: UUID4
    name: str
    description: Optional[str] = None
    context_notes: Optional[str] = None
    repository_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    context_status: ContextStatus

    model_config = {
        "from_attributes": True,  # Pydantic v2 style for mapping from SQLAlchemy models
    }

    # Alternative method for model_dump if needed for direct serialization
    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        # Convert UUIDs to strings
        if "id" in data and isinstance(data["id"], uuid.UUID):
            data["id"] = str(data["id"])
        if "owner_id" in data and isinstance(data["owner_id"], uuid.UUID):
            data["owner_id"] = str(data["owner_id"])
        return data
