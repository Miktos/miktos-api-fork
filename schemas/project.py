# schemas/project.py
from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import Optional, Any
from models.database_models import ContextStatus
import uuid

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
        "from_attributes": True  # Pydantic v2 style for mapping from SQLAlchemy models
    }