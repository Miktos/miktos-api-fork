# integrations/base_llm_client.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncGenerator, Optional, Union, Tuple

from .response_types import LLMResponse, LLMStreamChunk, LLMUsage

class BaseLLMClient(ABC):
    """Base class for all LLM clients.
    
    This abstract class defines the common interface and shared functionality
    for all language model clients (Claude, Gemini, OpenAI, etc).
    """
    
    @abstractmethod
    async def generate_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs: Any
    ) -> Union[LLMResponse, AsyncGenerator[LLMStreamChunk, None]]:
        """Generate a completion from the language model.
        
        Args:
            messages: A list of message dictionaries.
            model: The model ID to use.
            system_prompt: Optional system instructions.
            temperature: Controls output randomness.
            max_tokens: Maximum tokens to generate.
            stream: Whether to stream the response.
            **kwargs: Additional provider-specific parameters.
            
        Returns:
            Either a complete response or an async generator of response chunks.
        """
        pass
    
    def _format_error_response(
        self, exception: Exception, error_type: str, status_code: Optional[int] = None
    ) -> LLMResponse:
        """Format a standardized error response.
        
        Args:
            exception: The exception that occurred.
            error_type: Type of error (e.g., "ApiError", "ConfigurationError").
            status_code: Optional HTTP-like status code.
            
        Returns:
            A properly formatted error response dictionary.
        """
        error_response: LLMResponse = {
            "error": True,
            "content": None,
            "finish_reason": None,
            "usage": None,
            "model_name": "unknown",
            "raw_response": None,
            "message": str(exception),
            "type": error_type,
            "status_code": status_code,
            "error_code": None
        }
            
        return error_response
    
    @staticmethod
    def _process_system_prompt(
        messages: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Extract system prompt from messages and clean message list.
        
        Args:
            messages: Original message list that may contain a system message.
            
        Returns:
            Tuple of (cleaned_messages, system_prompt_or_None)
        """
        system_prompt = None
        cleaned_messages = []
        
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
            else:
                # Only include non-empty assistant messages
                if msg.get("role") == "assistant" and not msg.get("content"):
                    continue
                cleaned_messages.append(msg)
                
        return cleaned_messages, system_prompt