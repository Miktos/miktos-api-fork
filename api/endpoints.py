# miktos_backend/api/endpoints.py

import datetime
from fastapi import APIRouter, HTTPException, Body
# from fastapi.responses import StreamingResponse # We are using EventSourceResponse instead
from sse_starlette.sse import EventSourceResponse # Need this for streaming
import asyncio # For async generator handling
import json # Needed for serializing data in SSE

# Import our request/response models and the orchestrator function
from .models import GenerateRequest, GenerateResponse # Import both models
from core import orchestrator

# Create an API router
router = APIRouter()

# Assuming 'router' is your existing APIRouter instance
@router.get(
    "/health",
    tags=["System"],
    summary="Health check endpoint"
)
async def health_check():
    """
    Simple health check endpoint that returns OK if the API is running.
    Does not check database or external service connectivity.
    """
    return {"status": "ok", "timestamp": datetime.datetime.utcnow().isoformat()}

# Define the generation endpoint
# Added response_model=GenerateResponse for non-streaming success cases
@router.post(
    "/generate",
    tags=["Generation"],
    response_model=GenerateResponse # Specify the model for successful non-streaming responses
)
async def generate_completion_endpoint(
    request: GenerateRequest = Body(...) # Use Body to receive JSON payload
):
    """
    Receives a prompt and parameters, routes to the appropriate model via the orchestrator,
    and returns the response (streaming or non-streaming).
    """
    # Prepare arguments for the orchestrator
    # Handle potential system prompt (pass explicitly if needed by orchestrator design)
    # For now, assume orchestrator handles extracting system prompt if needed from messages
    orchestrator_args = {
        "messages": request.messages,
        "model": request.model,
        "stream": request.stream,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        # Add system_prompt if defined in GenerateRequest and needed by orchestrator signature
        # "system_prompt": request.system_prompt,
        # Add provider_specific_kwargs if defined in GenerateRequest
        # **request.provider_specific_kwargs
    }

    try:
        result_or_stream = await orchestrator.process_generation_request(**orchestrator_args)

        if request.stream:
            # Check if the result is an async generator (expected for streams)
            # Needs refinement: check actual type or use hasattr __aiter__
            is_async_generator = hasattr(result_or_stream, '__aiter__')

            if not is_async_generator:
                 # If orchestrator returned an error dict instead of a stream generator
                 print(f"Stream requested but received non-generator: {result_or_stream}")
                 # Ensure the error dict itself is serializable
                 error_payload = result_or_stream if isinstance(result_or_stream, dict) else {"error": True, "message":"Unknown stream error"}

                 # Stream an error event back
                 async def error_stream():
                     try:
                         yield {"event": "error", "data": json.dumps(error_payload)}
                     except TypeError as e:
                          # Fallback if error_payload isn't serializable
                          yield {"event": "error", "data": json.dumps({"error": True, "message": f"Non-serializable error occurred: {e}"})}
                 return EventSourceResponse(error_stream())

            # Define an async generator function to wrap the stream for EventSourceResponse
            async def stream_generator():
                try:
                    async for chunk in result_or_stream: # Iterate through the stream from orchestrator
                        # Ensure chunk is serializable
                        try:
                            chunk_data = json.dumps(chunk)
                        except TypeError:
                             print(f"Warning: Non-serializable chunk encountered in stream: {chunk}")
                             # Decide how to handle - skip, send error, send placeholder?
                             # Sending an error event for now
                             chunk = {"error": True, "message": "Received non-serializable stream chunk"}
                             chunk_data = json.dumps(chunk)

                        if chunk.get("error"):
                            # If an error occurs during the stream, send an error event
                            yield {"event": "error", "data": chunk_data}
                            break # Stop streaming on error
                        elif chunk.get("is_final"):
                            # Send a final 'done' or summary event (optional)
                            yield {"event": "final", "data": chunk_data}
                        elif chunk.get("delta") is not None: # Check specifically for delta presence
                            # Send the actual text delta
                            yield {"event": "message", "data": chunk_data}
                        # else: handle other potential chunk types if needed

                except Exception as e:
                    print(f"Error consuming stream in API endpoint: {e}")
                    # Send an error event if consumption fails
                    error_payload = {"error": True, "message": f"Stream consumption error: {str(e)}", "type": type(e).__name__}
                    try:
                        yield {"event": "error", "data": json.dumps(error_payload)}
                    except TypeError as te:
                         yield {"event": "error", "data": json.dumps({"error": True, "message": f"Non-serializable stream error: {te}"})}


            # Use EventSourceResponse for Server-Sent Events
            return EventSourceResponse(stream_generator())

        else:
            # Non-streaming: Return the result directly
            # Check if the result indicates an error
            if isinstance(result_or_stream, dict) and result_or_stream.get("error"):
                 # Determine appropriate HTTP status code based on error type/code
                 status_code = 500 # Default internal server error
                 error_detail = result_or_stream.get("message", "An unknown error occurred.")
                 # Use status code provided by the client error handling if available
                 if result_or_stream.get("status_code"):
                      status_code = result_or_stream["status_code"]
                 # Add specific mappings if needed (already done in client helpers mostly)
                 elif result_or_stream.get("type") == "ConfigurationError":
                      status_code = 503
                 elif result_or_stream.get("type") == "RoutingError":
                      status_code = 400

                 # Raise HTTPException, FastAPI handles converting this to JSON error response
                 raise HTTPException(status_code=status_code, detail=error_detail)

            # Return successful non-streaming dictionary. FastAPI will validate
            # against 'response_model=GenerateResponse' and serialize to JSON.
            if not isinstance(result_or_stream, dict):
                 # Should not happen if clients return dicts, but safety check
                 print(f"Error: Non-streaming call returned non-dict: {type(result_or_stream)}")
                 raise HTTPException(status_code=500, detail="Internal server error: Invalid response type from orchestrator.")

            return result_or_stream

    except HTTPException as http_exc:
         # Re-raise HTTPExceptions that were raised intentionally (like for errors)
         raise http_exc
    except Exception as e:
        # Catch any other unexpected errors during the endpoint logic/orchestration call
        print(f"Critical Error in /generate endpoint: {e}")
        # Optionally include traceback for detailed server logs
        # import traceback
        # traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")