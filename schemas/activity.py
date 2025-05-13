# miktos_backend/schemas/activity.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Optional
from datetime import datetime

class ActivityBase(BaseModel):
    """Base class for user activity data."""
    user_id: str
    activity_type: str = Field(..., description="Type of activity: login, api_call, logout, etc.")
    endpoint: Optional[str] = Field(None, description="API endpoint for api_call activity type")
    details: Optional[Dict] = Field(default_factory=dict, description="Additional activity details")

class ActivityCreate(ActivityBase):
    """Schema for creating a new activity record."""
    pass

class ActivityUpdate(BaseModel):
    """Schema for updating an activity record."""
    details: Optional[Dict] = None

class ActivityRead(ActivityBase):
    """Schema for reading an activity record."""
    id: str
    timestamp: datetime
    
    model_config = ConfigDict(from_attributes=True)
