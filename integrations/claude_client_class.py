# integrations/claude_client_class.py

import os
from anthropic import AsyncAnthropic, Anthropic, APIError, RateLimitError, APITimeoutError
from typing import List, Dict, Any, AsyncGenerator, Optional, Union
import asyncio
import traceback

# Import our settings loader
from config.settings import settings
from .base_llm_client import BaseLLMClient
from .response_types import LLMResponse, LLMStreamChunk, LLMUsage

# --- Defaults ---
DEFAULT_CLAUDE_MODEL = "claude-3-5-sonnet-20240620"
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TEMPERATURE = 0.7
ANTHROPIC_API_VERSION = "2023-06-01"

class ClaudeClient(BaseLLMClient):
    """Client for Anthropic's Claude API.
    
    Provides a standardized interface for interacting with Claude models
    using Anthropic's API.
    """
    
    # Constants
    DEFAULT_MODEL = DEFAULT_CLAUDE_MODEL
    DEFAULT_TEMPERATURE = DEFAULT_TEMPERATURE
    DEFAULT_MAX_TOKENS = DEFAULT_MAX_TOKENS
    
    def __init__(self) -> None:
        """Initialize the Claude client with API configuration."""
        self.is_configured = False
        self.client = None
        
        if settings.ANTHROPIC_API_KEY:
            try:
                self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
                self.is_configured = True
            except Exception as e:
                print(f"Error configuring Anthropic Client: {e}")
        else:
            print("Warning: Anthropic API key not found. Async Anthropic client not initialized.")
    
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
        """Generate a completion from the Claude API.
        
        This method handles both streaming and non-streaming completions from
        Anthropic's Claude API, with proper error handling and response formatting.
        
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
                "message": "Anthropic client not initialized...", 
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
                async def error_gen_init() -> AsyncGenerator[LLMStreamChunk, None]:
                    yield {
                        "error": True, 
                        "message": "Anthropic client not initialized...", 
                        "type": "ConfigurationError",
                        "delta": None,
                        "is_final": True,
                        "accumulated_content": "",
                        "finish_reason": None,
                        "usage": None,
                        "model_name": None
                    }
                return error_gen_init()
            else:
                return error_response
        
        effective_max_tokens = max_tokens if max_tokens is not None else self.DEFAULT_MAX_TOKENS
        if effective_max_tokens is None:
            error_response: LLMResponse = {
                "error": True, 
                "message": "max_tokens required...", 
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
                async def error_gen_max() -> AsyncGenerator[LLMStreamChunk, None]:
                    yield {
                        "error": True, 
                        "message": "max_tokens required...", 
                        "type": "ConfigurationError",
                        "delta": None,
                        "is_final": True,
                        "accumulated_content": "",
                        "finish_reason": None,
                        "usage": None,
                        "model_name": None
                    }
                return error_gen_max()
            else:
                return error_response
        
        # Filter out empty assistant messages
        filtered_messages = [msg for msg in messages if not (msg.get("role") == "assistant" and (not msg.get("content") or msg.get("content") == ""))]
        
        # Process system prompt if present in messages
        system_instruction = system_prompt
        for msg in list(filtered_messages):
            if msg.get("role") == "system":
                if not system_instruction:
                    system_instruction = msg.get("content", "")
                filtered_messages.remove(msg)
        
        request_params = {
            "model": model or self.DEFAULT_MODEL,
            "messages": filtered_messages,
            "max_tokens": effective_max_tokens,
            "temperature": temperature if temperature is not None else self.DEFAULT_TEMPERATURE,
            **kwargs
        }
        if system_instruction:
            request_params["system"] = system_instruction
        
        try:
            if stream:
                print(f"--- Calling Anthropic API (Streaming) with params (excluding stream): {request_params} ---")
                # client.messages.stream returns an AsyncContextManager, don't await here
                response_stream_manager = self.client.messages.stream(**request_params)
                # Return the async generator wrapper, passing the context manager
                return self._anthropic_stream_wrapper(response_stream_manager)
            else:
                # --- Non-streaming ---
                print(f"--- Calling Anthropic API (Non-Streaming) with params: {request_params} ---")
                # Await the non-streaming create call
                completion = await self.client.messages.create(**request_params)
                print(f"--- Raw Anthropic Response Received ---\n{completion}\n------------------------------------")
                
                return self._parse_non_streaming_response(completion)
        
        # --- Error Handling ---
        except RateLimitError as e:
            return self._handle_anthropic_error(e)
        except APITimeoutError as e:
            return self._handle_anthropic_error(e)
        except APIError as e:
            return self._handle_anthropic_error(e)
        except Exception as e:
            print(f"Unexpected Error calling Anthropic API: {e}")
            traceback.print_exc()
            error_response: LLMResponse = {
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
                return error_response
    
    async def _anthropic_stream_wrapper(
        self, response_stream_manager: Any
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """Wraps the Anthropic stream async context manager to yield structured dictionaries.
        
        Args:
            response_stream_manager: The AsyncContextManager returned by Anthropic's stream method.
            
        Yields:
            Structured stream chunks.
        """
        accumulated_content = ""
        finish_reason = None
        usage = None  # Initialize usage dict
        model_name = None
        prompt_tokens = None  # Store initial prompt tokens
        
        try:
            print("--- Starting Anthropic Stream Processing ---")
            # Use async with on the stream manager
            async with response_stream_manager as stream:
                # Iterate over the 'stream' object obtained from 'async with'
                async for event in stream:
                    print(f"--- Received Anthropic Stream Event: {event.type} ---")  # Less verbose logging
                    if event.type == "message_start":
                        model_name = event.message.model
                        # Capture initial usage (mainly prompt tokens)
                        if event.message.usage:
                            prompt_tokens = getattr(event.message.usage, 'input_tokens', None)
                            usage = {"prompt_tokens": prompt_tokens, "completion_tokens": 0, "total_tokens": prompt_tokens or 0}
                        print(f"--- Stream started (Model: {model_name}, Initial Usage: {usage}) ---")
                    
                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            chunk_text = event.delta.text
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
                    
                    elif event.type == "message_delta":
                        # Capture finish reason
                        finish_reason = event.delta.stop_reason
                        # Capture usage delta (only contains output_tokens)
                        completion_tokens_delta = 0
                        if hasattr(event, 'usage') and event.usage:
                            completion_tokens_delta = getattr(event.usage, 'output_tokens', 0)
                        
                        # Update running usage total if initialized
                        if usage is not None:
                            usage["completion_tokens"] = completion_tokens_delta  # Anthropic SDK provides cumulative output tokens here
                            usage["total_tokens"] = (usage["prompt_tokens"] or 0) + usage["completion_tokens"]
                        
                        print(f"--- Stream message_delta processed (FR={finish_reason}, Current Usage={usage}) ---")
                    
                    elif event.type == "message_stop":
                        print("--- Stream message stop event received ---")
                        # Loop will terminate automatically after this
            
            # After the loop, yield final summary
            print(f"--- Finishing Anthropic Stream Wrapper (Final State: FR={finish_reason}, Usage={usage}) ---")
            final_chunk: LLMStreamChunk = {
                "error": False, 
                "delta": None, 
                "is_final": True,
                "accumulated_content": accumulated_content, 
                "finish_reason": finish_reason,
                "usage": usage,  # Send final captured usage
                "model_name": model_name,
                "message": None,
                "type": None
            }
            yield final_chunk
        
        except APIError as e:
            error_data = self._handle_anthropic_error(e)
            print(f"--- Error During Anthropic Stream Processing (APIError) ---\n{error_data}\n----------------------------------")
            error_chunk: LLMStreamChunk = {
                "error": True,
                "message": error_data.get("message", "Unknown error"),
                "type": error_data.get("type", "AnthropicAPIError"),
                "delta": None,
                "is_final": True,
                "accumulated_content": accumulated_content,
                "finish_reason": "ERROR",
                "usage": usage,
                "model_name": model_name
            }
            yield error_chunk
        except Exception as e:
            print(f"Unexpected Error processing Anthropic stream: {e}")
            traceback.print_exc()  # Print stack trace to terminal
            error_chunk: LLMStreamChunk = {
                "error": True, 
                "message": f"An unexpected error occurred during streaming: {str(e)}", 
                "type": type(e).__name__,
                "delta": None,
                "is_final": True,
                "accumulated_content": accumulated_content,
                "finish_reason": "ERROR",
                "usage": usage,
                "model_name": model_name
            }
            print(f"--- Error During Anthropic Stream Processing (Exception) ---\n{error_chunk}\n----------------------------------")
            yield error_chunk
    
    def _parse_non_streaming_response(
        self, completion: Any
    ) -> LLMResponse:
        """Parse a non-streaming response from Claude API.
        
        Args:
            completion: Response from Claude API.
            
        Returns:
            Structured response dictionary.
        """
        try:
            # --- Parsing Logic ---
            response_content = None
            finish_reason = None
            usage = None
            model_name = None
            
            if completion.content and isinstance(completion.content, list) and len(completion.content) > 0:
                if completion.content[0].type == "text":
                    response_content = completion.content[0].text
            
            finish_reason = completion.stop_reason
            model_name = completion.model
            
            if completion.usage:
                usage = {
                    "prompt_tokens": completion.usage.input_tokens, 
                    "completion_tokens": completion.usage.output_tokens, 
                    "total_tokens": completion.usage.input_tokens + completion.usage.output_tokens
                }
            
            final_return_data: LLMResponse = {
                "error": False, 
                "content": response_content, 
                "finish_reason": finish_reason,
                "usage": usage, 
                "model_name": model_name, 
                "raw_response": completion.model_dump(),
                "message": None,
                "type": None,
                "status_code": None,
                "error_code": None
            }
            
            print(f"--- Final Data to Return from Claude Client ---\n{final_return_data}\n-------------------------------------------")
            return final_return_data
        
        except Exception as e:
            print(f"Error parsing Claude response: {e}")
            traceback.print_exc()
            
            return {
                "error": True,
                "content": None,
                "finish_reason": None,
                "usage": None,
                "model_name": getattr(completion, "model", "unknown"),
                "raw_response": None,
                "message": f"Failed to parse Claude response: {str(e)}",
                "type": "ParsingError",
                "status_code": None,
                "error_code": None
            }
    
    def _handle_anthropic_error(self, e: Exception) -> LLMResponse:
        """Handle Anthropic API errors.
        
        Args:
            e: Exception that occurred.
            
        Returns:
            Structured error response.
        """
        error_info: LLMResponse = {
            "error": True,
            "message": str(e),
            "type": type(e).__name__,
            "content": None,
            "finish_reason": None,
            "usage": None,
            "model_name": "unknown",
            "raw_response": None,
            "status_code": None,
            "error_code": None
        }
        
        if isinstance(e, APIError):
            # FIX: Check for status_code on the response attribute
            if hasattr(e, 'response') and e.response and hasattr(e.response, 'status_code'):
                error_info["status_code"] = e.response.status_code
            # Keep the original check as a fallback, though less likely for Anthropic's library
            elif hasattr(e, 'status_code') and e.status_code:
                error_info["status_code"] = e.status_code
        
        print(f"Anthropic API Error: {error_info}")
        return error_info