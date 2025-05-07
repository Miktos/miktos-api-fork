# integrations/gemini_client_class.py
import os
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from typing import List, Dict, Any, AsyncGenerator, Optional, Union, Tuple
import asyncio
import traceback

from config.settings import settings
from .base_llm_client import BaseLLMClient
from .response_types import LLMResponse, LLMStreamChunk, LLMUsage

# --- Default Parameters ---
DEFAULT_GEMINI_MODEL = "gemini-1.5-flash-latest"
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TEMPERATURE = 0.7

class GeminiClient(BaseLLMClient):
    """Client for Google's Gemini API."""
    
    # Constants
    DEFAULT_MODEL = DEFAULT_GEMINI_MODEL
    DEFAULT_TEMPERATURE = DEFAULT_TEMPERATURE
    DEFAULT_MAX_TOKENS = DEFAULT_MAX_TOKENS
    
    def __init__(self) -> None:
        """Initialize the Gemini client with API configuration."""
        self.is_configured = False
        
        if settings.GOOGLE_API_KEY:
            try:
                genai.configure(api_key=settings.GOOGLE_API_KEY)
                self.is_configured = True
            except Exception as e:
                print(f"Error configuring Google AI Client: {e}")
        else:
            print("Warning: Google API key not found. Google AI client not configured.")
    
    async def generate_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        safety_settings: Optional[List[Dict[str, Any]]] = None,
        generation_config_overrides: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> Union[LLMResponse, AsyncGenerator[LLMStreamChunk, None]]:
        """Generate a completion from the Gemini API."""
        # Check for invalid parameters first
        valid_params = ["model", "system_prompt", "temperature", "max_tokens", "stream", 
                       "safety_settings", "generation_config_overrides"]
        invalid_params = [param for param in kwargs.keys() if param not in valid_params]
        if invalid_params:
            error_response = {
                "error": True,
                "message": f"Invalid parameters: {', '.join(invalid_params)}",
                "type": "InvalidParameterError",
                "content": None,
                "finish_reason": None,
                "usage": None,
                "model_name": "unknown",
                "raw_response": None,
                "status_code": None,
                "error_code": None
            }
            if stream:
                async def error_gen() -> AsyncGenerator[LLMStreamChunk, None]:
                    yield {
                        "error": True,
                        "message": f"Invalid parameters: {', '.join(invalid_params)}",
                        "type": "InvalidParameterError",
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
        
        # Process messages and extract system prompt
        cleaned_messages, extracted_system_prompt = self._process_system_prompt(messages)
        # Use extracted system prompt if none was explicitly provided
        if system_prompt is None and extracted_system_prompt is not None:
            system_prompt = extracted_system_prompt
        
        # Convert messages to Gemini format
        contents = self._convert_messages_to_gemini_format(cleaned_messages)
        
        # --- Prepare Generation Config ---
        gen_config_dict: Dict[str, Any] = {
            "temperature": temperature if temperature is not None else self.DEFAULT_TEMPERATURE,
            "candidate_count": 1,
            "max_output_tokens": max_tokens if max_tokens is not None else self.DEFAULT_MAX_TOKENS,
            **(generation_config_overrides or {})
        }
        
        try:
            gen_config = genai.types.GenerationConfig(**gen_config_dict)
        except Exception as e:
            return self._handle_generation_config_error(e, stream)
        
        # --- Initialize Model ---
        try:
            model_id = model or self.DEFAULT_MODEL
            gemini_model = genai.GenerativeModel(
                model_name=model_id,
                safety_settings=safety_settings,
                generation_config=gen_config,
                system_instruction=system_prompt
            )
        except Exception as e:
            return self._handle_model_init_error(e, stream)
        
        # --- API Call ---
        try:
            if stream:
                print(f"--- Calling Google AI API (Streaming) for model: {model_id} ---")
                # For streaming, we need to create the generator but not await it yet
                response = gemini_model.generate_content(contents, stream=True)
                # Return the async generator wrapper
                return self._handle_streaming_response(response, model_id)
            else:
                # --- Non-streaming ---
                print(f"--- Calling Google AI API (Non-Streaming) for model: {model_id} ---")
                # For non-streaming, we need to await the response
                response = await asyncio.to_thread(gemini_model.generate_content, contents)
                
                return self._parse_non_streaming_response(response, model_id)
                
        except Exception as e:
            return self._handle_api_call_error(e, stream)
    
    def _convert_messages_to_gemini_format(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert message list to Gemini API format.
        
        Args:
            messages: Cleaned message list (without system messages).
            
        Returns:
            List of messages in Gemini format.
        """
        contents = []
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            
            if isinstance(content, str):
                gemini_role = "model" if role == "assistant" else "user"
                parts = [{"text": content}]
                contents.append({"role": gemini_role, "parts": parts})
        
        return contents
    
    async def _handle_streaming_response(
        self, response_stream_iterable: Any, model_id: str
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """Process streaming response from Gemini API.
        
        Args:
            response_stream_iterable: Raw response stream.
            model_id: Model identifier.
            
        Yields:
            Structured response chunks.
        """
        accumulated_content = ""
        finish_reason = None
        usage = None
        
        try:
            print("--- Starting Google AI Stream Processing ---")
            for chunk in response_stream_iterable:
                chunk_text = None
                chunk_finish_reason = None
                chunk_usage = None
                is_blocked = False
                
                try: # Safe parsing of chunk attributes
                    # Check for blockage first
                    if hasattr(chunk, 'prompt_feedback') and chunk.prompt_feedback and chunk.prompt_feedback.block_reason:
                        finish_reason_str = f"BLOCKED_{chunk.prompt_feedback.block_reason.name}"
                        print(f"--- Stream chunk potentially blocked: {finish_reason_str} ---")
                        chunk_text = f"[Content potentially blocked during stream. Reason: {finish_reason_str}]"
                        if chunk_finish_reason is None: 
                            chunk_finish_reason = finish_reason_str
                        is_blocked = True
                    elif hasattr(chunk, 'parts') and chunk.parts: # Get text only if not blocked
                        chunk_text = chunk.text

                    # Always try to get finish reason and usage
                    if hasattr(chunk, 'candidates') and chunk.candidates: 
                        chunk_finish_reason = str(chunk.candidates[0].finish_reason.name)
                    if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                        chunk_usage = {
                            "prompt_tokens": getattr(chunk.usage_metadata, 'prompt_token_count', None),
                            "completion_tokens": getattr(chunk.usage_metadata, 'candidates_token_count', 0),
                            "total_tokens": getattr(chunk.usage_metadata, 'total_token_count', None)
                        }
                        if chunk_usage["prompt_tokens"] is not None and chunk_usage["total_tokens"] is not None: 
                            usage = chunk_usage
                        elif chunk_usage["completion_tokens"] > 0 and usage: 
                            usage["completion_tokens"] = chunk_usage["completion_tokens"]
                            usage["total_tokens"] = (usage["prompt_tokens"] or 0) + usage["completion_tokens"]

                    # Allow a small delay to simulate an async flow
                    await asyncio.sleep(0.01)

                except Exception as inner_e:
                    print(f"Error processing Gemini stream chunk: {inner_e}")
                    error_chunk: LLMStreamChunk = {
                        "error": True, 
                        "message": f"Error processing stream chunk: {str(inner_e)}", 
                        "type": type(inner_e).__name__,
                        "delta": None,
                        "is_final": False,
                        "accumulated_content": accumulated_content,
                        "finish_reason": None,
                        "usage": None,
                        "model_name": None
                    }
                    yield error_chunk
                    continue # Try to continue stream if possible after chunk error

                # Yield text delta if found
                if chunk_text:
                    print(f"--- Stream delta received: '{chunk_text}' ---") # Verbose
                    accumulated_content += chunk_text
                    
                    chunk_response: LLMStreamChunk = {
                        "error": is_blocked, 
                        "delta": chunk_text, 
                        "is_final": False, 
                        "accumulated_content": accumulated_content,
                        "finish_reason": None,
                        "usage": None,
                        "model_name": None,
                        "message": None,
                        "type": None
                    }
                    yield chunk_response # Include block status

                # Capture final finish reason
                if chunk_finish_reason and chunk_finish_reason != "FINISH_REASON_UNSPECIFIED":
                    finish_reason = chunk_finish_reason
                    print(f"--- Stream finish reason captured: {finish_reason} ---")

            # After the loop, yield final summary
            print(f"--- Finishing Google AI Stream Wrapper (Final State: FR={finish_reason}, Usage={usage}) ---")
            final_chunk: LLMStreamChunk = {
                "error": False, 
                "delta": None, 
                "is_final": True, 
                "accumulated_content": accumulated_content, 
                "finish_reason": finish_reason, 
                "usage": usage, 
                "model_name": model_id,
                "message": None,
                "type": None
            }
            yield final_chunk

        except google_exceptions.GoogleAPIError as e:
            error_data = self._handle_google_error(e)
            print(f"--- Error During Google AI Stream Processing (GoogleAPIError) ---\n{error_data}\n----------------------------------")
            error_chunk: LLMStreamChunk = {
                "error": True,
                "message": error_data.get("message", "Unknown error"),
                "type": error_data.get("type", "GoogleAPIError"),
                "delta": None,
                "is_final": True,
                "accumulated_content": accumulated_content,
                "finish_reason": "ERROR",
                "usage": None,
                "model_name": model_id
            }
            yield error_chunk
        except Exception as e:
            print(f"Unexpected Error processing Google AI stream: {e}")
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
                "model_name": model_id
            }
            print(f"--- Error During Google AI Stream Processing (Exception) ---\n{error_chunk}\n----------------------------------")
            yield error_chunk
    
    def _parse_non_streaming_response(
        self, response: Any, model_id: str
    ) -> LLMResponse:
        """Parse a non-streaming response from Gemini API.
        
        Args:
            response: Response from Gemini API.
            model_id: Model identifier.
            
        Returns:
            Structured response dictionary.
        """
        print(f"--- Raw Google AI Response Received ---\n{response}\n------------------------------------")

        # --- Parsing Logic ---
        response_content = None
        finish_reason = None
        usage = None
        raw_response_dump = None
        
        try:
            if hasattr(response, 'parts') and response.parts: 
                response_content = response.text
            if hasattr(response, 'candidates') and response.candidates: 
                finish_reason = str(response.candidates[0].finish_reason.name)
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = {
                    "prompt_tokens": response.usage_metadata.prompt_token_count,
                    "completion_tokens": response.usage_metadata.candidates_token_count,
                    "total_tokens": response.usage_metadata.total_token_count
                }
            if hasattr(response, 'to_dict'): 
                raw_response_dump = response.to_dict()
            print(f"--- Parsed Content: {str(response_content)[:100]}... Finish: {finish_reason} Usage: {usage} ---")

        except (ValueError, AttributeError, IndexError) as ve:
            print(f"Warning: Could not parse Gemini response content. Possible block? {ve}")
            finish_reason_str = "UNKNOWN"
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback and response.prompt_feedback.block_reason: 
                finish_reason_str = f"BLOCKED_{response.prompt_feedback.block_reason.name}"
            elif hasattr(response, 'candidates') and response.candidates and hasattr(response.candidates[0], 'finish_reason'): 
                finish_reason_str = f"STOPPED_{response.candidates[0].finish_reason.name}"
            response_content = f"[Content potentially blocked or missing. Reason: {finish_reason_str}]"
            finish_reason = finish_reason_str
            if hasattr(response, 'usage_metadata') and response.usage_metadata: 
                usage = {
                    "prompt_tokens": response.usage_metadata.prompt_token_count,
                    "completion_tokens": response.usage_metadata.candidates_token_count or 0,
                    "total_tokens": response.usage_metadata.total_token_count
                }
            print(f"--- Response likely blocked or missing content. Finish: {finish_reason} Usage: {usage} ---")

        final_return_data: LLMResponse = {
            "error": False,
            "content": response_content,
            "finish_reason": finish_reason,
            "usage": usage,
            "model_name": model_id,
            "raw_response": raw_response_dump,
            "message": None,
            "type": None,
            "status_code": None,
            "error_code": None
        }
        print(f"--- Final Data to Return from Gemini Client ---\n{final_return_data}\n-------------------------------------------")
        return final_return_data
    
    def _handle_google_error(self, e: Exception) -> Dict[str, Any]:
        """Handle Google API errors.
        
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

        if isinstance(e, google_exceptions.GoogleAPIError):
            error_info["message"] = getattr(e, 'message', str(e))
            status_code = getattr(e, 'code', None)
            error_code = getattr(e, 'reason', None)

            # Map common Google API exceptions
            if isinstance(e, google_exceptions.InvalidArgument): 
                error_info["status_code"] = status_code or 400
            elif isinstance(e, google_exceptions.PermissionDenied): 
                error_info["status_code"] = status_code or 403
            elif isinstance(e, google_exceptions.ResourceExhausted):
                error_info["status_code"] = status_code or 429
                error_info["error_code"] = error_code or "rate_limit_exceeded"
            elif isinstance(e, google_exceptions.DeadlineExceeded): 
                error_info["status_code"] = status_code or 504
            elif isinstance(e, google_exceptions.InternalServerError): 
                error_info["status_code"] = status_code or 500
            elif isinstance(e, google_exceptions.ServiceUnavailable): 
                error_info["status_code"] = status_code or 503

        print(f"Google AI API Error: {error_info}")
        return error_info
    
    def _handle_generation_config_error(
        self, e: Exception, stream: bool
    ) -> Union[LLMResponse, AsyncGenerator[LLMStreamChunk, None]]:
        """Handle errors during generation config creation.
        
        Args:
            e: Exception that occurred.
            stream: Whether this is a streaming request.
            
        Returns:
            Error response or error generator.
        """
        error_data = self._handle_google_error(e)
        
        if stream:
            async def error_gen() -> AsyncGenerator[LLMStreamChunk, None]:
                error_chunk: LLMStreamChunk = {
                    "error": True,
                    "message": error_data.get("message", ""),
                    "type": error_data.get("type", "Unknown"),
                    "delta": None,
                    "is_final": True,
                    "accumulated_content": "",
                    "finish_reason": None,
                    "usage": None,
                    "model_name": None
                }
                yield error_chunk
            return error_gen()
        else:
            error_response: LLMResponse = {
                "error": True,
                "content": None,
                "finish_reason": None,
                "usage": None,
                "model_name": "unknown",
                "raw_response": None,
                "message": error_data.get("message", ""),
                "type": error_data.get("type", "Unknown"),
                "status_code": error_data.get("status_code"),
                "error_code": error_data.get("error_code")
            }
            return error_response
    
    def _handle_model_init_error(
        self, e: Exception, stream: bool
    ) -> Union[LLMResponse, AsyncGenerator[LLMStreamChunk, None]]:
        """Handle errors during model initialization.
        
        Args:
            e: Exception that occurred.
            stream: Whether this is a streaming request.
            
        Returns:
            Error response or error generator.
        """
        error_data = self._handle_google_error(e)
        
        if stream:
            async def error_gen() -> AsyncGenerator[LLMStreamChunk, None]:
                error_chunk: LLMStreamChunk = {
                    "error": True,
                    "message": error_data.get("message", ""),
                    "type": error_data.get("type", "Unknown"),
                    "delta": None,
                    "is_final": True,
                    "accumulated_content": "",
                    "finish_reason": None,
                    "usage": None,
                    "model_name": None
                }
                yield error_chunk
            return error_gen()
        else:
            error_response: LLMResponse = {
                "error": True,
                "content": None,
                "finish_reason": None,
                "usage": None,
                "model_name": "unknown",
                "raw_response": None,
                "message": error_data.get("message", ""),
                "type": error_data.get("type", "Unknown"),
                "status_code": error_data.get("status_code"),
                "error_code": error_data.get("error_code")
            }
            return error_response
    
    def _handle_api_call_error(
        self, e: Exception, stream: bool
    ) -> Union[LLMResponse, AsyncGenerator[LLMStreamChunk, None]]:
        """Handle errors during API call.
        
        Args:
            e: Exception that occurred.
            stream: Whether this is a streaming request.
            
        Returns:
            Error response or error generator.
        """
        if isinstance(e, google_exceptions.GoogleAPIError):
            error_data = self._handle_google_error(e)
        else:
            print(f"Unexpected Error calling Google AI API: {e}")
            traceback.print_exc()
            error_data = {
                "error": True,
                "message": f"An unexpected error occurred: {str(e)}",
                "type": type(e).__name__
            }
        
        if stream:
            async def error_gen() -> AsyncGenerator[LLMStreamChunk, None]:
                error_chunk: LLMStreamChunk = {
                    "error": True,
                    "message": error_data.get("message", ""),
                    "type": error_data.get("type", "Unknown"),
                    "delta": None,
                    "is_final": True,
                    "accumulated_content": "",
                    "finish_reason": None,
                    "usage": None,
                    "model_name": None
                }
                yield error_chunk
            return error_gen()
        else:
            error_response: LLMResponse = {
                "error": True,
                "content": None,
                "finish_reason": None,
                "usage": None,
                "model_name": "unknown",
                "raw_response": None,
                "message": error_data.get("message", ""),
                "type": error_data.get("type", "Unknown"),
                "status_code": error_data.get("status_code"),
                "error_code": error_data.get("error_code")
            }
            return error_response