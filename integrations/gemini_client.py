# miktos_backend/integrations/gemini_client.py

import os
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from typing import List, Dict, Any, AsyncGenerator, Optional, Union
import asyncio
import traceback # Import traceback

# Import our settings loader
from miktos_backend.config import settings

# Configure the Google AI client
if settings.GOOGLE_API_KEY:
    try:
        genai.configure(api_key=settings.GOOGLE_API_KEY)
    except Exception as e:
        print(f"Error configuring Google AI Client: {e}")
else:
    print("Warning: Google API key not found. Google AI client not configured.")

# --- Default Parameters ---
DEFAULT_GEMINI_MODEL = "gemini-1.5-flash-latest"
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TEMPERATURE = 0.7

# --- Helper Function for Error Handling ---
def _handle_google_error(e: Exception) -> Dict[str, Any]:
    """Handles common Google API errors and returns a structured error dict."""
    error_info = {"error": True, "message": str(e), "type": type(e).__name__}
    status_code = None
    error_code = None

    if isinstance(e, google_exceptions.GoogleAPIError):
        error_info["message"] = getattr(e, 'message', str(e))
        status_code = getattr(e, 'code', None)
        error_code = getattr(e, 'reason', None)

    # Map common Google API exceptions
    if isinstance(e, google_exceptions.InvalidArgument): status_code = status_code or 400
    elif isinstance(e, google_exceptions.PermissionDenied): status_code = status_code or 403
    elif isinstance(e, google_exceptions.ResourceExhausted):
        status_code = status_code or 429
        error_code = error_code or "rate_limit_exceeded"
    elif isinstance(e, google_exceptions.DeadlineExceeded): status_code = status_code or 504
    elif isinstance(e, google_exceptions.InternalServerError): status_code = status_code or 500
    elif isinstance(e, google_exceptions.ServiceUnavailable): status_code = status_code or 503

    if status_code: error_info["status_code"] = status_code
    if error_code: error_info["error_code"] = error_code

    print(f"Google AI API Error: {error_info}")
    return error_info

# --- Main Generation Function - ASYNC ---
async def generate_completion(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    stream: bool = False,
    safety_settings: Optional[List[Dict[str, Any]]] = None,
    generation_config_overrides: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
    """
    Generates content using the Google Gemini API, handling streaming correctly.
    """
    if not settings.GOOGLE_API_KEY:
        print("--- Returning error: Google AI client not configured ---")
        if stream:
             async def error_gen_g_init(): yield {"error": True, "message": "Google AI client not configured...", "type": "ConfigurationError"}
             return error_gen_g_init()
        else: return {"error": True, "message": "Google AI client not configured...", "type": "ConfigurationError"}

    # --- Input Conversion ---
    contents = []
    system_instruction = system_prompt
    
    # Filter out empty assistant messages
    filtered_messages = [msg for msg in messages if not (msg.get("role") == "assistant" and (not msg.get("content") or msg.get("content") == ""))]
    
    for msg in filtered_messages:
        role = msg.get("role")
        content = msg.get("content")
        if role == "system" and not system_instruction:
            if isinstance(content, str): system_instruction = content
            continue
        if role == "system": continue
        gemini_role = "model" if role == "assistant" else "user"
        if isinstance(content, str): parts = [{"text": content}]
        else: continue
        contents.append({"role": gemini_role, "parts": parts})

    # --- Prepare Generation Config ---
    gen_config_dict = {
        "temperature": temperature if temperature is not None else DEFAULT_TEMPERATURE,
        "candidate_count": 1,
        "max_output_tokens": max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS,
        **(generation_config_overrides or {})
    }
    gen_config = genai.types.GenerationConfig(**gen_config_dict)

    # --- Initialize Model ---
    try:
        model_id = model or DEFAULT_GEMINI_MODEL
        gemini_model = genai.GenerativeModel(
            model_name=model_id,
            safety_settings=safety_settings,
            generation_config=gen_config,
            system_instruction=system_instruction
        )
    except Exception as e:
        error_data = _handle_google_error(e)
        if stream:
             async def error_gen_g_model(): 
                 yield error_data
             return error_gen_g_model()
        else: return error_data

    # --- API Call ---
    try:
        if stream:
            print(f"--- Calling Google AI API (Streaming) for model: {model_id} ---")
            # For streaming, we need to create the generator but not await it yet
            response = gemini_model.generate_content(contents, stream=True)
            # Return the async generator wrapper
            return _gemini_stream_wrapper(response, model_id)
        else:
            # --- Non-streaming ---
            print(f"--- Calling Google AI API (Non-Streaming) for model: {model_id} ---")
            # For non-streaming, we need to await the response
            response = await asyncio.to_thread(gemini_model.generate_content, contents)
            
            print(f"--- Raw Google AI Response Received ---\n{response}\n------------------------------------")

            # --- Parsing Logic ---
            response_content = None; finish_reason = None; usage = None; raw_response_dump = None
            try:
                 if hasattr(response, 'parts') and response.parts: response_content = response.text
                 if hasattr(response, 'candidates') and response.candidates: finish_reason = str(response.candidates[0].finish_reason.name)
                 if hasattr(response, 'usage_metadata') and response.usage_metadata:
                     usage = {"prompt_tokens": response.usage_metadata.prompt_token_count,"completion_tokens": response.usage_metadata.candidates_token_count,"total_tokens": response.usage_metadata.total_token_count}
                 if hasattr(response, 'to_dict'): raw_response_dump = response.to_dict()
                 print(f"--- Parsed Content: {str(response_content)[:100]}... Finish: {finish_reason} Usage: {usage} ---")

            except (ValueError, AttributeError, IndexError) as ve:
                 print(f"Warning: Could not parse Gemini response content. Possible block? {ve}")
                 finish_reason_str = "UNKNOWN"
                 if hasattr(response,'prompt_feedback') and response.prompt_feedback and response.prompt_feedback.block_reason: finish_reason_str = f"BLOCKED_{response.prompt_feedback.block_reason.name}"
                 elif hasattr(response, 'candidates') and response.candidates and hasattr(response.candidates[0], 'finish_reason'): finish_reason_str = f"STOPPED_{response.candidates[0].finish_reason.name}"
                 response_content = f"[Content potentially blocked or missing. Reason: {finish_reason_str}]"; finish_reason = finish_reason_str
                 if hasattr(response, 'usage_metadata') and response.usage_metadata: usage = { "prompt_tokens": response.usage_metadata.prompt_token_count, "total_tokens": response.usage_metadata.prompt_token_count }
                 print(f"--- Response likely blocked or missing content. Finish: {finish_reason} Usage: {usage} ---")

            final_return_data = {"error": False,"content": response_content,"finish_reason": finish_reason,"usage": usage,"model_name": model_id,"raw_response": raw_response_dump}
            print(f"--- Final Data to Return from Gemini Client ---\n{final_return_data}\n-------------------------------------------")
            return final_return_data

    # --- Error Handling ---
    except google_exceptions.GoogleAPIError as e: error_data = _handle_google_error(e)
    except Exception as e:
        print(f"Unexpected Error calling Google AI API: {e}")
        traceback.print_exc()
        error_data = {"error": True, "message": f"An unexpected error occurred: {str(e)}", "type": type(e).__name__}

    # Handle stream vs non-stream error return
    print(f"--- Error Data to Return from Gemini Client (Exception Block) ---\n{error_data}\n-------------------------------------------")
    if stream and 'error_data' in locals():
        async def error_gen_final(): yield error_data
        return error_gen_final()
    elif 'error_data' in locals():
        return error_data
    else: # Should not happen, but fallback
         fallback_error = {"error": True, "message": "Unknown error state in Gemini client", "type": "InternalError"}
         if stream: 
             async def fallback_gen(): yield fallback_error
             return fallback_gen()
         else: 
             return fallback_error


# --- Stream Wrapper Generator - ASYNC ---
async def _gemini_stream_wrapper(response_stream_iterable: Any, model_id: str) -> AsyncGenerator[Dict[str, Any], None]:
    """Wraps the Google AI stream to yield structured dictionaries."""
    accumulated_content = ""
    finish_reason = None
    usage = None

    try:
        print("--- Starting Google AI Stream Processing ---")
        # Work with the iterator synchronously since Gemini's API doesn't provide an async iterator
        for chunk in response_stream_iterable:
            chunk_text = None; chunk_finish_reason = None; chunk_usage = None
            is_blocked = False
            try: # Safe parsing of chunk attributes
                # Check for blockage first
                if hasattr(chunk,'prompt_feedback') and chunk.prompt_feedback and chunk.prompt_feedback.block_reason:
                     finish_reason_str = f"BLOCKED_{chunk.prompt_feedback.block_reason.name}"
                     print(f"--- Stream chunk potentially blocked: {finish_reason_str} ---")
                     chunk_text = f"[Content potentially blocked during stream. Reason: {finish_reason_str}]"
                     if chunk_finish_reason is None: chunk_finish_reason = finish_reason_str
                     is_blocked = True
                elif hasattr(chunk, 'parts') and chunk.parts: # Get text only if not blocked
                    chunk_text = chunk.text

                # Always try to get finish reason and usage
                if hasattr(chunk, 'candidates') and chunk.candidates: chunk_finish_reason = str(chunk.candidates[0].finish_reason.name)
                if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                     chunk_usage = {"prompt_tokens": getattr(chunk.usage_metadata, 'prompt_token_count', None),"completion_tokens": getattr(chunk.usage_metadata, 'candidates_token_count', 0),"total_tokens": getattr(chunk.usage_metadata, 'total_token_count', None)}
                     if chunk_usage["prompt_tokens"] is not None and chunk_usage["total_tokens"] is not None: usage = chunk_usage
                     elif chunk_usage["completion_tokens"] > 0 and usage: usage["completion_tokens"] = chunk_usage["completion_tokens"]; usage["total_tokens"] = (usage["prompt_tokens"] or 0) + usage["completion_tokens"]

                # Yield a chunk for each iteration in the Gemini response
                # Allow a small delay to simulate an async flow
                await asyncio.sleep(0.01)

            except Exception as inner_e:
                 print(f"Error processing Gemini stream chunk: {inner_e}")
                 yield {"error": True, "message": f"Error processing stream chunk: {str(inner_e)}", "type": type(inner_e).__name__}
                 continue # Try to continue stream if possible after chunk error

            # Yield text delta if found
            if chunk_text:
                print(f"--- Stream delta received: '{chunk_text}' ---") # Verbose
                accumulated_content += chunk_text
                yield {"error": is_blocked, "delta": chunk_text, "is_final": False, "accumulated_content": accumulated_content} # Include block status

            # Capture final finish reason
            if chunk_finish_reason and chunk_finish_reason != "FINISH_REASON_UNSPECIFIED":
                finish_reason = chunk_finish_reason
                print(f"--- Stream finish reason captured: {finish_reason} ---")

        # After the loop, yield final summary
        print(f"--- Finishing Google AI Stream Wrapper (Final State: FR={finish_reason}, Usage={usage}) ---")
        yield {"error": False, "delta": None, "is_final": True, "accumulated_content": accumulated_content, "finish_reason": finish_reason, "usage": usage, "model_name": model_id}

    except google_exceptions.GoogleAPIError as e:
        error_data = _handle_google_error(e)
        print(f"--- Error During Google AI Stream Processing (GoogleAPIError) ---\n{error_data}\n----------------------------------")
        yield error_data
    except Exception as e:
        print(f"Unexpected Error processing Google AI stream: {e}")
        traceback.print_exc()
        error_data = {"error": True, "message": f"An unexpected error occurred during streaming: {str(e)}", "type": type(e).__name__}
        print(f"--- Error During Google AI Stream Processing (Exception) ---\n{error_data}\n----------------------------------")
        yield error_data