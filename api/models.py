# miktos_backend/api/models.py

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class GenerateRequest(BaseModel):
    """Request model for the /generate endpoint."""
    model: str = Field(..., description="The ID of the target AI model (e.g., 'openai/gpt-4o', 'anthropic/claude-3-5-sonnet-20240620').")
    messages: List[Dict[str, Any]] = Field(..., description="Conversation history/prompt following OpenAI message format.")
    project_id: str = Field(..., description="The ID of the project this conversation belongs to.") # <-- ADDED THIS LINE
    stream: bool = Field(default=True, description="Whether to stream the response.") # Changed default to True as it's expected
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0, description="Optional temperature override.")
    max_tokens: Optional[int] = Field(default=None, gt=0, description="Optional max_tokens override.")
    system_prompt: Optional[str] = Field(default=None, description="System prompt (used by some providers)") # Added for clarity

    # Example for flexible provider args (consider if needed later)
    # provider_specific_kwargs: Optional[Dict[str, Any]] = Field(default_factory=dict)

class GenerateResponse(BaseModel):
    """Response model for a successful non-streaming generation."""
    # This is likely not used directly if the endpoint always streams or returns dicts from orchestrator
    error: bool = False
    content: Optional[str] = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    model_name: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "error": False,
                "content": "Miktós is an AI orchestration platform...",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 45, "completion_tokens": 15, "total_tokens": 60},
                "model_name": "gpt-4o"
            }
        }