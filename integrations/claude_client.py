# miktos_backend/integrations/claude_client.py

import os
from anthropic import Anthropic, APIError, RateLimitError, APITimeoutError, AsyncAnthropic # Use Async client
from typing import List, Dict, Any, AsyncGenerator, Optional, Union
import asyncio
import traceback  # Add traceback for detailed debugging

# Import our settings loader
from miktos_backend.config import settings

# Initialize the ASYNC Anthropic client
if settings.ANTHROPIC_API_KEY:
    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
else:
    client = None
    print("Warning: Anthropic API key not found. Async Anthropic client not initialized.")

# --- Defaults ---
DEFAULT_CLAUDE_MODEL = "claude-3-5-sonnet-20240620"
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TEMPERATURE = 0.7
ANTHROPIC_API_VERSION = "2023-06-01"

# --- Error Helper ---
def _handle_anthropic_error(e: APIError) -> Dict[str, Any]:
    error_info = {"error": True, "message": str(e), "type": type(e).__name__}
    if hasattr(e, 'status_code'): error_info["status_code"] = e.status_code
    print(f"Anthropic API Error: {error_info}")
    return error_info

# --- Main Function - ASYNC ---
async def generate_completion(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    stream: bool = False,
    **kwargs
) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
    if not client:
        print("--- Returning error: Anthropic client not initialized ---")
        if stream:
             async def error_gen_init(): yield {"error": True, "message": "Anthropic client not initialized...", "type": "ConfigurationError"}
             return error_gen_init()
        else: return {"error": True, "message": "Anthropic client not initialized...", "type": "ConfigurationError"}

    effective_max_tokens = max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS
    if effective_max_tokens is None:
         print(f"--- Returning error: max_tokens required...")
         if stream:
              async def error_gen_max(): yield {"error": True, "message": "max_tokens required...", "type": "ConfigurationError"}
              return error_gen_max()
         else: return {"error": True, "message": "max_tokens required...", "type": "ConfigurationError"}

    # Filter out empty assistant messages
    filtered_messages = [msg for msg in messages if not (msg.get("role") == "assistant" and (not msg.get("content") or msg.get("content") == ""))]
    
    request_params = {
        "model": model or DEFAULT_CLAUDE_MODEL,
        "messages": filtered_messages,
        "max_tokens": effective_max_tokens,
        "temperature": temperature if temperature is not None else DEFAULT_TEMPERATURE,
        # Removed "stream": stream, as it's passed to the specific method call
        **kwargs
    }
    if system_prompt: request_params["system"] = system_prompt

    try:
        if stream:
            print(f"--- Calling Anthropic API (Streaming) with params (excluding stream): {request_params} ---")
            # client.messages.stream returns an AsyncContextManager, don't await here
            response_stream_manager = client.messages.stream(**request_params)
            # Return the async generator wrapper, passing the context manager
            return _anthropic_stream_wrapper(response_stream_manager)
        else:
            # --- Non-streaming ---
            print(f"--- Calling Anthropic API (Non-Streaming) with params: {request_params} ---")
            # Await the non-streaming create call
            completion = await client.messages.create(**request_params)
            print(f"--- Raw Anthropic Response Received ---\n{completion}\n------------------------------------")

            # --- Parsing Logic ---
            response_content = None
            finish_reason = None
            usage = None
            model_name = None
            final_return_data = None
            if completion.content and isinstance(completion.content, list) and len(completion.content) > 0:
                if completion.content[0].type == "text": response_content = completion.content[0].text
            finish_reason = completion.stop_reason
            model_name = completion.model
            if completion.usage:
                usage = {"prompt_tokens": completion.usage.input_tokens, "completion_tokens": completion.usage.output_tokens, "total_tokens": completion.usage.input_tokens + completion.usage.output_tokens}

            final_return_data = {
                "error": False, "content": response_content, "finish_reason": finish_reason,
                "usage": usage, "model_name": model_name, "raw_response": completion.model_dump()
            }
            print(f"--- Final Data to Return from Claude Client ---\n{final_return_data}\n-------------------------------------------")
            return final_return_data

    # --- Error Handling ---
    except RateLimitError as e: error_data = _handle_anthropic_error(e)
    except APITimeoutError as e: error_data = _handle_anthropic_error(e)
    except APIError as e: error_data = _handle_anthropic_error(e)
    except Exception as e:
        print(f"Unexpected Error calling Anthropic API: {e}")
        traceback.print_exc()  # Print stack trace for better debugging
        error_data = {"error": True, "message": f"An unexpected error occurred: {str(e)}", "type": type(e).__name__}

    # Handle error return for stream vs non-stream
    print(f"--- Error Data to Return from Claude Client (Exception Block) ---\n{error_data}\n-------------------------------------------") # Debug Error Return
    if stream:
        async def error_gen_final(): yield error_data
        return error_gen_final()
    else:
        return error_data


# --- Stream Wrapper Generator - ASYNC ---
async def _anthropic_stream_wrapper(response_stream_manager: Any) -> AsyncGenerator[Dict[str, Any], None]:
    """Wraps the Anthropic stream async context manager to yield structured dictionaries."""
    accumulated_content = ""
    finish_reason = None
    usage = None # Initialize usage dict
    model_name = None
    prompt_tokens = None # Store initial prompt tokens

    try:
        print("--- Starting Anthropic Stream Processing ---")
        # Use async with on the stream manager
        async with response_stream_manager as stream:
            # Iterate over the 'stream' object obtained from 'async with'
            async for event in stream:
                print(f"--- Received Anthropic Stream Event: {event.type} ---") # Less verbose logging
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
                        print(f"--- Stream delta received: '{chunk_text}' ---") # Verbose
                        accumulated_content += chunk_text
                        yield {
                            "error": False, "delta": chunk_text, "is_final": False,
                            "accumulated_content": accumulated_content
                        }

                elif event.type == "message_delta":
                    # Capture finish reason
                    finish_reason = event.delta.stop_reason
                    # Capture usage delta (only contains output_tokens)
                    completion_tokens_delta = 0
                    if hasattr(event, 'usage') and event.usage:
                        completion_tokens_delta = getattr(event.usage, 'output_tokens', 0)

                    # Update running usage total if initialized
                    if usage is not None:
                        usage["completion_tokens"] = completion_tokens_delta # Anthropic SDK provides cumulative output tokens here
                        usage["total_tokens"] = (usage["prompt_tokens"] or 0) + usage["completion_tokens"]

                    print(f"--- Stream message_delta processed (FR={finish_reason}, Current Usage={usage}) ---")

                elif event.type == "message_stop":
                    print("--- Stream message stop event received ---")
                    # Loop will terminate automatically after this

        # After the loop, yield final summary
        print(f"--- Finishing Anthropic Stream Wrapper (Final State: FR={finish_reason}, Usage={usage}) ---")
        yield {
            "error": False, "delta": None, "is_final": True,
            "accumulated_content": accumulated_content, "finish_reason": finish_reason,
            "usage": usage, # Send final captured usage
            "model_name": model_name
        }

    except APIError as e:
        error_data = _handle_anthropic_error(e)
        print(f"--- Error During Anthropic Stream Processing (APIError) ---\n{error_data}\n----------------------------------")
        yield error_data
    except Exception as e:
        print(f"Unexpected Error processing Anthropic stream: {e}")
        traceback.print_exc() # Print stack trace to terminal
        error_data = {"error": True, "message": f"An unexpected error occurred during streaming: {str(e)}", "type": type(e).__name__}
        print(f"--- Error During Anthropic Stream Processing (Exception) ---\n{error_data}\n----------------------------------")
        yield error_data