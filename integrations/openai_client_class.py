# integrations/openai_client_class.py

import os
from openai import AsyncOpenAI, APIError, RateLimitError, APITimeoutError
from typing import List, Dict, Any, AsyncGenerator, Optional, Union
import traceback

# Import our settings loader
from config.settings import settings
from .base_llm_client import BaseLLMClient
from .response_types import LLMResponse, LLMStreamChunk, LLMUsage

# --- Default Parameters ---
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TEMPERATURE = 0.7


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI's API.
    
    Provides a standardized interface for interacting with OpenAI models
    using OpenAI's async API client.
    """
    
    # Constants
    DEFAULT_MODEL = DEFAULT_OPENAI_MODEL
    DEFAULT_TEMPERATURE = DEFAULT_TEMPERATURE
    DEFAULT_MAX_TOKENS = DEFAULT_MAX_TOKENS
    
    def __init__(self) -> None:
        """Initialize the OpenAI client with API configuration."""
        self.is_configured = False
        self.client = None
        
        if settings.OPENAI_API_KEY:
            try:
                self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                self.is_configured = True
            except Exception as e:
                print(f"Error configuring OpenAI Client: {e}")
        else:
            print("Warning: OpenAI API key not found. Async OpenAI client not initialized.")
    
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
        """Generate a completion from the OpenAI API.
        
        This method handles both streaming and non-streaming completions from
        OpenAI's API, with proper error handling and response formatting.
        
        Args:
            messages: A list of message dictionaries.
            model: The model ID to use. Defaults to class DEFAULT_MODEL.
            system_prompt: Optional system instructions.
            temperature: Controls randomness of outputs (0.0-1.0).
            max_tokens: Maximum tokens to generate.
            stream: If True, return an async generator of response chunks.
            **kwargs: Additional provider-specific parameters.
            
        Returns:
            Either a complete response or an async generator of response chunks.
        """
        if not self.is_configured or not self.client:
            error_response: LLMResponse = {
                "error": True,
                "message": "OpenAI client not initialized...",
                "type": "ConfigurationError",
                "content": None,
                "finish_reason": None,
                "usage": None,
                "model_name": "unknown",
                "raw_response": None,
                "status_code": None,
                "error_code": None
            }
            
            if stream:
                async def error_gen_oai_init() -> AsyncGenerator[LLMStreamChunk, None]:
                    yield {
                        "error": True,
                        "message": "OpenAI client not initialized...",
                        "type": "ConfigurationError",
                        "delta": None,
                        "is_final": True,
                        "accumulated_content": "",
                        "finish_reason": None,
                        "usage": None,
                        "model_name": None
                    }
                return error_gen_oai_init()
            else:
                return error_response
        
        # Process system prompt if available
        processed_messages = []
        has_system_message = False
        
        # Filter out empty assistant messages and handle system messages
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                if not has_system_message and system_prompt is None:
                    # Use the first system message found
                    system_prompt = content
                    has_system_message = True
                continue
            
            if role == "assistant" and not content:
                continue
                
            processed_messages.append({"role": role, "content": content})
        
        # Add system prompt as a system message if provided
        if system_prompt:
            processed_messages.insert(0, {"role": "system", "content": system_prompt})
        
        request_params = {
            "model": model or self.DEFAULT_MODEL,
            "messages": processed_messages,
            "temperature": temperature if temperature is not None else self.DEFAULT_TEMPERATURE,
            "max_tokens": max_tokens if max_tokens is not None else self.DEFAULT_MAX_TOKENS,
            "stream": stream,  # Pass stream flag directly to async create method
            **kwargs
        }
        
        try:
            if stream:
                print(f"--- Calling OpenAI API (Streaming) with params: {request_params} ---")
                # Await the async create method which returns the stream object
                response_stream = await self.client.chat.completions.create(**request_params)
                # Pass the async generator to the wrapper
                return self._process_openai_stream(response_stream)  # Wrapper is async
            else:
                # --- Non-streaming ---
                print(f"--- Calling OpenAI API (Non-Streaming) with params: {request_params} ---")
                # Await the non-streaming async create call
                completion = await self.client.chat.completions.create(**request_params)
                
                return self._parse_non_streaming_response(completion)
        
        # --- Error Handling ---
        except RateLimitError as e:
            return self._handle_openai_error(e, stream)
        except APITimeoutError as e:
            return self._handle_openai_error(e, stream)
        except APIError as e:
            return self._handle_openai_error(e, stream)
        except Exception as e:
            print(f"Unexpected Error calling OpenAI API: {e}")
            traceback.print_exc()
            error_data: LLMResponse = {
                "error": True,
                "message": f"An unexpected error occurred: {str(e)}",
                "type": type(e).__name__,
                "content": None,
                "finish_reason": None,
                "usage": None,
                "model_name": "unknown",
                "raw_response": None,
                "status_code": None,
                "error_code": None
            }
            
            if stream:
                async def error_gen_final() -> AsyncGenerator[LLMStreamChunk, None]:
                    yield {
                        "error": True,
                        "message": f"An unexpected error occurred: {str(e)}",
                        "type": type(e).__name__,
                        "delta": None,
                        "is_final": True,
                        "accumulated_content": "",
                        "finish_reason": None,
                        "usage": None,
                        "model_name": None
                    }
                return error_gen_final()
            else:
                return error_data
    
    async def _process_openai_stream(
        self, response_stream: Any
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """Process streaming response from OpenAI API.
        
        Args:
            response_stream: The async generator returned by OpenAI's API.
            
        Yields:
            Structured stream chunks.
        """
        accumulated_content = ""
        finish_reason = None
        # Usage info isn't typically available reliably chunk-by-chunk in OpenAI streams
        model_name = None
        
        try:
            print("--- Starting OpenAI Stream Processing ---")
            async for chunk in response_stream:
                print("--- Received OpenAI Stream Chunk ---")  # Verbose
                model_name = chunk.model  # Capture model from chunk
                delta = chunk.choices[0].delta
                chunk_finish_reason = chunk.choices[0].finish_reason
                
                chunk_text = None
                if delta and hasattr(delta, 'content') and delta.content:
                    chunk_text = delta.content
                    print(f"--- Stream delta received: '{chunk_text}' ---")  # Verbose
                    accumulated_content += chunk_text
                    
                    chunk_response: LLMStreamChunk = {
                        "error": False,
                        "delta": chunk_text,
                        "is_final": False,
                        "accumulated_content": accumulated_content,
                        "finish_reason": None,
                        "usage": None,
                        "model_name": model_name,
                        "message": None,
                        "type": None
                    }
                    yield chunk_response
                
                if chunk_finish_reason:
                    finish_reason = chunk_finish_reason
                    print(f"--- Stream finish reason captured: {finish_reason} ---")
                    # Don't break, allow loop to finish naturally
            
            # After the loop, yield final summary
            print(f"--- Finishing OpenAI Stream Wrapper (Final State: FR={finish_reason}) ---")
            final_chunk: LLMStreamChunk = {
                "error": False,
                "delta": None,
                "is_final": True,
                "accumulated_content": accumulated_content,
                "finish_reason": finish_reason,
                "usage": None,  # Usage data not reliably available in stream end event from SDK
                "model_name": model_name,
                "message": None,
                "type": None
            }
            yield final_chunk
        
        except APIError as e:
            error_data = self._handle_openai_error_dict(e)
            print(f"--- Error During OpenAI Stream Processing (APIError) ---\n{error_data}\n----------------------------------")
            error_chunk: LLMStreamChunk = {
                "error": True,
                "message": error_data.get("message", "Unknown error"),
                "type": error_data.get("type", "OpenAIAPIError"),
                "delta": None,
                "is_final": True,
                "accumulated_content": accumulated_content,
                "finish_reason": "ERROR",
                "usage": None,
                "model_name": model_name
            }
            yield error_chunk
        except Exception as e:
            print(f"Unexpected Error processing OpenAI stream: {e}")
            traceback.print_exc()
            error_chunk: LLMStreamChunk = {
                "error": True,
                "message": f"An unexpected error occurred during streaming: {str(e)}",
                "type": type(e).__name__,
                "delta": None,
                "is_final": True,
                "accumulated_content": accumulated_content,
                "finish_reason": "ERROR",
                "usage": None,
                "model_name": model_name
            }
            print(f"--- Error During OpenAI Stream Processing (Exception) ---\n{error_chunk}\n----------------------------------")
            yield error_chunk
    
    def _parse_non_streaming_response(
        self, completion: Any
    ) -> LLMResponse:
        """Parse a non-streaming response from OpenAI API.
        
        Args:
            completion: Response from OpenAI API.
            
        Returns:
            Structured response dictionary.
        """
        print(f"--- Raw OpenAI Response Received ---\n{completion}\n------------------------------------")
        
        # --- Parsing Logic ---
        response_content = None
        finish_reason = None
        usage = None
        model_name = getattr(completion, "model", "unknown")
        
        try:
            if hasattr(completion, "choices") and completion.choices:
                message = completion.choices[0].message
                response_content = message.content
                finish_reason = completion.choices[0].finish_reason
            
            if hasattr(completion, "usage") and completion.usage:
                usage = {
                    "prompt_tokens": completion.usage.prompt_tokens,
                    "completion_tokens": completion.usage.completion_tokens,
                    "total_tokens": completion.usage.total_tokens
                }
            
            raw_response = None
            if hasattr(completion, "model_dump"):
                raw_response = completion.model_dump()
            
            final_return_data: LLMResponse = {
                "error": False,
                "content": response_content,
                "finish_reason": finish_reason,
                "usage": usage,
                "model_name": model_name,
                "raw_response": raw_response,
                "message": None,
                "type": None,
                "status_code": None,
                "error_code": None
            }
            
            print(f"--- Final Data to Return from OpenAI Client ---\n{final_return_data}\n-------------------------------------------")
            return final_return_data
        
        except Exception as e:
            print(f"Error parsing OpenAI response: {e}")
            traceback.print_exc()
            
            return {
                "error": True,
                "content": None,
                "finish_reason": None,
                "usage": None,
                "model_name": model_name,
                "raw_response": None,
                "message": f"Failed to parse OpenAI response: {str(e)}",
                "type": "ParsingError",
                "status_code": None,
                "error_code": None
            }
    
    def _handle_openai_error_dict(self, e: Exception) -> Dict[str, Any]:
        """Handle OpenAI API errors and return a dictionary.
        
        Args:
            e: Exception that occurred.
            
        Returns:
            Error dictionary.
        """
        error_info = {
            "error": True,
            "message": str(e),
            "type": type(e).__name__
        }
        
        if hasattr(e, 'status_code'):
            error_info["status_code"] = e.status_code
        if hasattr(e, 'code'):
            error_info["error_code"] = e.code
        
        print(f"OpenAI API Error: {error_info}")
        return error_info
    
    def _handle_openai_error(
        self, e: Exception, stream: bool = False
    ) -> Union[LLMResponse, AsyncGenerator[LLMStreamChunk, None]]:
        """Handle OpenAI API errors.
        
        Args:
            e: Exception that occurred.
            stream: Whether this is a streaming request.
            
        Returns:
            Error response or error generator.
        """
        error_dict = self._handle_openai_error_dict(e)
        
        error_response: LLMResponse = {
            "error": True,
            "message": error_dict.get("message", "Unknown error"),
            "type": error_dict.get("type", "OpenAIAPIError"),
            "content": None,
            "finish_reason": None,
            "usage": None,
            "model_name": "unknown",
            "raw_response": None,
            "status_code": error_dict.get("status_code"),
            "error_code": error_dict.get("error_code")
        }
        
        if stream:
            async def error_gen() -> AsyncGenerator[LLMStreamChunk, None]:
                yield {
                    "error": True,
                    "message": error_dict.get("message", "Unknown error"),
                    "type": error_dict.get("type", "OpenAIAPIError"),
                    "delta": None,
                    "is_final": True,
                    "accumulated_content": "",
                    "finish_reason": None,
                    "usage": None,
                    "model_name": None
                }
            return error_gen()
        else:
            return error_response