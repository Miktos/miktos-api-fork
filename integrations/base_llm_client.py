# integrations/base_llm_client.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncGenerator, Optional, Union, Tuple
import traceback

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
        self, exception: Exception, error_type: str, status_code: Optional[int] = None,
        error_code: Optional[str] = None
    ) -> LLMResponse:
        """Format a standardized error response.
        
        Args:
            exception: The exception that occurred.
            error_type: Type of error (e.g., "ApiError", "ConfigurationError").
            status_code: Optional HTTP-like status code.
            error_code: Optional vendor-specific error code.
            
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
            "error_code": error_code
        }
            
        return error_response

    def create_standard_error_response(
        self, error_type: str, message: str, status_code: Optional[int] = None,
        error_code: Optional[str] = None, model_name: Optional[str] = None
    ) -> LLMResponse:
        """Create a standardized error response without an exception.
        
        Args:
            error_type: Type of error (e.g., "ApiError", "ConfigurationError").
            message: Error message string.
            status_code: Optional HTTP-like status code.
            error_code: Optional vendor-specific error code.
            model_name: Optional model name (if available).
            
        Returns:
            A properly formatted error response dictionary.
        """
        error_response: LLMResponse = {
            "error": True,
            "content": None,
            "finish_reason": None,
            "usage": None,
            "model_name": model_name or "unknown",
            "raw_response": None,
            "message": message,
            "type": error_type,
            "status_code": status_code,
            "error_code": error_code
        }
            
        return error_response
    
    async def create_error_stream_chunk(
        self, error_type: str, message: str, status_code: Optional[int] = None,
        error_code: Optional[str] = None
    ) -> LLMStreamChunk:
        """Create a standardized error chunk for streaming responses.
        
        Args:
            error_type: Type of error (e.g., "ApiError", "StreamError").
            message: Error message string.
            status_code: Optional HTTP-like status code.
            error_code: Optional vendor-specific error code.
            
        Returns:
            A properly formatted error chunk for streaming.
        """
        return {
            "error": True,
            "message": message,
            "type": error_type,
            "delta": None,
            "is_final": True,
            "accumulated_content": "",
            "finish_reason": "error",
            "usage": None,
            "model_name": None,
            "status_code": status_code,
            "error_code": error_code
        }
        
    async def handle_exception_for_stream(
        self, exception: Exception, error_type: Optional[str] = None
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """Handle exception for streaming responses.
        
        Args:
            exception: The exception that occurred.
            error_type: Optional error type override.
            
        Returns:
            An async generator yielding a single error chunk.
        """
        error_type = error_type or type(exception).__name__
        
        # Extract status code if available
        status_code = None
        error_code = None
        
        if hasattr(exception, 'status_code'):
            status_code = exception.status_code
        if hasattr(exception, 'code'):
            error_code = exception.code
            
        # Log the error
        print(f"Error in LLM client ({error_type}): {str(exception)}")
        traceback.print_exc()
        
        # Return error chunk
        yield await self.create_error_stream_chunk(
            error_type=error_type,
            message=str(exception),
            status_code=status_code,
            error_code=error_code
        )
    
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