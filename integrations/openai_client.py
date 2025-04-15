# miktos_backend/integrations/openai_client.py

import os
from openai import OpenAI, APIError, RateLimitError, APITimeoutError, AsyncOpenAI # Use Async Client
from typing import List, Dict, Any, AsyncGenerator, Optional, Union
import traceback

# Import our settings loader
from miktos_backend.config import settings

# Initialize the ASYNC OpenAI client
if settings.OPENAI_API_KEY:
    # Use AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
else:
    client = None
    print("Warning: OpenAI API key not found. Async OpenAI client not initialized.")

# --- Default Parameters ---
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TEMPERATURE = 0.7

# --- Helper Function for Error Handling ---
def _handle_openai_error(e: APIError) -> Dict[str, Any]:
    """Handles common OpenAI API errors and returns a structured error dict."""
    error_info = {"error": True, "message": str(e), "type": type(e).__name__}
    if hasattr(e, 'status_code'): error_info["status_code"] = e.status_code
    if hasattr(e, 'code'): error_info["error_code"] = e.code
    print(f"OpenAI API Error: {error_info}")
    return error_info


# --- Main Generation Function - ASYNC ---
async def generate_completion(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    stream: bool = False,
    **kwargs
) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
    """
    Generates a chat completion using the OpenAI API (async), handling streaming.
    """
    if not client:
        print("--- Returning error: OpenAI client not initialized ---")
        if stream:
            async def error_gen_oai_init(): yield {"error": True, "message": "OpenAI client not initialized...", "type": "ConfigurationError"}
            return error_gen_oai_init()
        else: return {"error": True, "message": "OpenAI client not initialized...", "type": "ConfigurationError"}

    # Filter out empty assistant messages
    filtered_messages = [msg for msg in messages if not (msg.get("role") == "assistant" and (not msg.get("content") or msg.get("content") == ""))]
    
    request_params = {
        "model": model or DEFAULT_OPENAI_MODEL,
        "messages": filtered_messages,
        "temperature": temperature if temperature is not None else DEFAULT_TEMPERATURE,
        "max_tokens": max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS,
        "stream": stream, # Pass stream flag directly to async create method
        **kwargs
    }

    try:
        if stream:
            print(f"--- Calling OpenAI API (Streaming) with params: {request_params} ---")
            # *** AWAIT HERE is needed for the async create method which returns the stream object ***
            response_stream = await client.chat.completions.create(**request_params) # type: ignore
            # Pass the async generator to the wrapper
            return _process_openai_stream(response_stream) # Wrapper is async
        else:
            # --- Non-streaming ---
            print(f"--- Calling OpenAI API (Non-Streaming) with params: {request_params} ---")
            # *** AWAIT the non-streaming async create call ***
            completion = await client.chat.completions.create(**request_params)
            # 'completion' is the resolved ChatCompletion object

            print(f"--- Raw OpenAI Response Received ---\n{completion}\n------------------------------------")

            # --- Parsing Logic ---
            response_content = None; finish_reason = None; usage = None
            if completion.choices:
                message = completion.choices[0].message
                response_content = message.content
                finish_reason = completion.choices[0].finish_reason
            if completion.usage:
                 usage = {"prompt_tokens": completion.usage.prompt_tokens, "completion_tokens": completion.usage.completion_tokens, "total_tokens": completion.usage.total_tokens}

            final_return_data = {
                "error": False, "content": response_content, "finish_reason": finish_reason,
                "usage": usage, "model_name": completion.model, "raw_response": completion.model_dump()
            }
            print(f"--- Final Data to Return from OpenAI Client ---\n{final_return_data}\n-------------------------------------------")
            return final_return_data

    # --- Error Handling ---
    except RateLimitError as e: error_data = _handle_openai_error(e)
    except APITimeoutError as e: error_data = _handle_openai_error(e)
    except APIError as e: error_data = _handle_openai_error(e)
    except Exception as e:
        print(f"Unexpected Error calling OpenAI API: {e}")
        traceback.print_exc()
        error_data = {"error": True, "message": f"An unexpected error occurred: {str(e)}", "type": type(e).__name__}

    # Handle stream vs non-stream error return
    print(f"--- Error Data to Return from OpenAI Client (Exception Block) ---\n{error_data}\n-------------------------------------------")
    if stream and 'error_data' in locals():
        async def error_gen_oai_final(): yield error_data
        return error_gen_oai_final()
    elif 'error_data' in locals():
        return error_data
    else: # Fallback
         fallback_error = {"error": True, "message": "Unknown error state in OpenAI client", "type": "InternalError"}
         if stream: 
             async def fallback_gen_oai(): yield fallback_error
             return fallback_gen_oai()
         else: 
             return fallback_error


# --- Stream Wrapper Generator - ASYNC ---
async def _process_openai_stream(response_stream: Any) -> AsyncGenerator[Dict[str, Any], None]:
    """Wraps the OpenAI stream async generator to yield structured dictionaries."""
    accumulated_content = ""
    finish_reason = None
    # Usage info isn't typically available reliably chunk-by-chunk in OpenAI streams
    model_name = None

    try:
        print("--- Starting OpenAI Stream Processing ---")
        async for chunk in response_stream:
            print(f"--- Received OpenAI Stream Chunk ---") # Verbose
            model_name = chunk.model # Capture model from chunk
            delta = chunk.choices[0].delta
            chunk_finish_reason = chunk.choices[0].finish_reason

            chunk_text = None
            if delta and delta.content:
                chunk_text = delta.content
                print(f"--- Stream delta received: '{chunk_text}' ---") # Verbose
                accumulated_content += chunk_text
                yield {
                    "error": False, "delta": chunk_text, "is_final": False,
                    "accumulated_content": accumulated_content
                }

            if chunk_finish_reason:
                finish_reason = chunk_finish_reason
                print(f"--- Stream finish reason captured: {finish_reason} ---")
                # Don't break, allow loop to finish naturally

        # After the loop, yield final summary
        print(f"--- Finishing OpenAI Stream Wrapper (Final State: FR={finish_reason}) ---")
        yield {
            "error": False, "delta": None, "is_final": True,
            "accumulated_content": accumulated_content, "finish_reason": finish_reason,
            "usage": None, # Usage data not reliably available in stream end event from SDK
            "model_name": model_name
        }

    except APIError as e:
        error_data = _handle_openai_error(e)
        print(f"--- Error During OpenAI Stream Processing (APIError) ---\n{error_data}\n----------------------------------")
        yield error_data
    except Exception as e:
        print(f"Unexpected Error processing OpenAI stream: {e}")
        traceback.print_exc()
        error_data = {"error": True, "message": f"An unexpected error occurred during streaming: {str(e)}", "type": type(e).__name__}
        print(f"--- Error During OpenAI Stream Processing (Exception) ---\n{error_data}\n----------------------------------")
        yield error_data