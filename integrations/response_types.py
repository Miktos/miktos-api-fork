# integrations/response_types.py
from typing import Dict, Any, Optional, TypedDict

class LLMUsage(TypedDict):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: Optional[int]

class LLMResponse(TypedDict):
    error: bool
    content: Optional[str]
    finish_reason: Optional[str]
    usage: Optional[LLMUsage]
    model_name: str
    raw_response: Optional[Dict[str, Any]]
    message: Optional[str]
    type: Optional[str]
    status_code: Optional[int]
    error_code: Optional[str]

class LLMStreamChunk(TypedDict):
    error: bool
    delta: Optional[str]
    is_final: bool
    accumulated_content: str
    finish_reason: Optional[str]
    usage: Optional[LLMUsage]
    model_name: Optional[str]
    message: Optional[str]
    type: Optional[str]