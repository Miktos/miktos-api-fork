# miktos_backend/api/endpoints.py
import datetime
from fastapi import APIRouter, HTTPException, Body, Depends, Query, status
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

# Import Pydantic Schemas used in this router
# Import generation schemas directly from api/models.py
from .models import GenerateRequest, GenerateResponse # Assuming these are Pydantic models defined here

# Import DB session and models
from config.database import get_db
from models.database_models import User # Import User model for type hint

# Import Auth dependency and Repository Classes
from api.auth import get_current_user
from repositories.message_repository import MessageRepository # Import CLASS
from repositories.project_repository import ProjectRepository # Import CLASS

# Import the core logic handler
from core import orchestrator

# Create an API router (prefix is handled in main.py)
router = APIRouter()

# Health check endpoint
@router.get(
    "/health",
    # tags=["System"], # Tags defined in main.py for this router
    summary="Health check endpoint"
)
async def health_check():
    """Simple health check endpoint that returns OK if the API is running."""
    return {"status": "ok", "timestamp": datetime.datetime.utcnow().isoformat()}

# Generation endpoint with optional project context
@router.post(
    "/generate",
    # tags=["Generation"], # Tags defined in main.py for this router
    # response_model=GenerateResponse, # Removing as actual response varies (stream/dict)
    summary="Generate AI completion, optionally linking to a project"
)
async def generate_completion_endpoint(
    # Require authentication for this endpoint
    current_user: User = Depends(get_current_user),
    # Require the main request body (validated against GenerateRequest schema)
    request: GenerateRequest = Body(...),
    # Project ID is an optional query parameter
    project_id: Optional[str] = Query(
        None,
        description="Optional ID of the project to associate conversation history with."
    ),
    # DB Session Dependency
    db: Session = Depends(get_db)
    # Return type depends on streaming, Any is safest for now
) -> Any:
    """
    Generates a completion from an AI model specified in the request body.

    - If `project_id` (query parameter) is provided and valid for the user,
      the conversation (request messages + assistant response) will be stored
      in that project's history.
    - Requires authentication.
    - Supports streaming (`stream: true` in request body).
    """
    project = None # Initialize project variable
    # Check project ownership if project_id is provided
    if project_id:
        project_repo = ProjectRepository(db=db)
        project = project_repo.get_by_id_for_owner(
            project_id=project_id, owner_id=str(current_user.id)
        )
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or not owned by user"
            )

    # Prepare arguments for the orchestrator
    # Assuming request.messages are already validated list of dicts by Pydantic
    # Ensure orchestrator expects List[Dict[str, Any]] or adapt if it needs Pydantic models
    orchestrator_args = {
        "messages": request.messages, # Pass the list of message dicts
        "model": request.model,
        "stream": request.stream,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        # Pass other parameters if needed
    }

    try:
        # Call the core logic - result is either a dict or an async generator
        result_or_stream = await orchestrator.process_generation_request(**orchestrator_args)

        if request.stream:
            # --- Streaming Response Handling ---
            is_async_generator = hasattr(result_or_stream, '__aiter__')

            if not is_async_generator:
                # Handle cases where stream=True but orchestrator didn't return a generator
                print(f"Stream requested but received non-generator: {result_or_stream}")
                error_payload = result_or_stream if isinstance(result_or_stream, dict) else {"error": True, "message":"Unknown stream error"}
                async def error_stream():
                    try:
                        yield {"event": "error", "data": json.dumps(error_payload)}
                    except TypeError as e:
                         yield {"event": "error", "data": json.dumps({"error": True, "message": f"Non-serializable stream error occurred: {e}"})}
                return EventSourceResponse(error_stream())

            # Instantiate MessageRepository ONCE before wrapper
            message_repo = MessageRepository(db=db)

            async def stream_wrapper():
                accumulated_content = ""
                model_used = request.model # Start with requested model

                try:
                    async for chunk_dict in result_or_stream: # Assuming orchestrator yields dicts
                        # Attempt to serialize chunk safely
                        try:
                            chunk_data = json.dumps(chunk_dict)
                        except TypeError:
                            error_chunk = {"error": True, "message": "Received non-serializable stream chunk"}
                            yield {"event": "error", "data": json.dumps(error_chunk)}
                            continue # Skip this chunk

                        # Extract info for saving and yielding
                        delta = chunk_dict.get("delta")
                        is_final = chunk_dict.get("is_final", False)
                        is_error = chunk_dict.get("error", False)
                        chunk_model = chunk_dict.get("model_name")

                        if chunk_model: model_used = chunk_model
                        if delta: accumulated_content += delta

                        # Yield chunk to client
                        if is_error:
                            yield {"event": "error", "data": chunk_data}
                        elif is_final:
                            yield {"event": "final", "data": chunk_data}
                            # --- Stream finished: Save conversation if project_id exists ---
                            if project_id and not is_error:
                                try:
                                    # --- FIX: Use request.messages directly (it's already a list of dicts) ---
                                    messages_to_save = request.messages.copy() # Copy the list of dicts
                                    # --- END FIX ---
                                    messages_to_save.append({
                                        "role": "assistant",
                                        "content": accumulated_content
                                    })
                                    # Call repo method on the INSTANCE
                                    message_repo.store_conversation(
                                        project_id=project_id,
                                        messages_data=messages_to_save,
                                        default_model=model_used
                                    )
                                except Exception as db_error:
                                    print(f"Error saving streamed conversation to database: {db_error}")
                            # --- End save block ---
                        elif delta is not None:
                             yield {"event": "message", "data": chunk_data}

                except Exception as e:
                    print(f"Stream consumption error: {e}")
                    error_payload = {"error": True, "message": f"Stream consumption error: {str(e)}"}
                    yield {"event": "error", "data": json.dumps(error_payload)}

            return EventSourceResponse(stream_wrapper())
            # --- End Streaming Response Handling ---

        else:
            # --- Non-Streaming Response Handling ---
            if isinstance(result_or_stream, dict) and result_or_stream.get("error"):
                status_code = result_or_stream.get("status_code", 500)
                raise HTTPException(status_code=status_code, detail=result_or_stream.get("message", "Orchestrator returned an error."))

            # Save conversation if project_id exists
            if project_id:
                 try:
                    # Instantiate MessageRepository
                    message_repo = MessageRepository(db=db)
                    # --- FIX: Use request.messages directly (it's already a list of dicts) ---
                    messages_to_save = request.messages.copy() # Copy the list of dicts
                    # --- END FIX ---
                    # Assuming result_or_stream is a dict with 'content' and maybe 'model_name'
                    assistant_content = result_or_stream.get("content", "") if isinstance(result_or_stream, dict) else ""
                    model_used = result_or_stream.get("model_name", request.model) if isinstance(result_or_stream, dict) else request.model
                    messages_to_save.append({
                        "role": "assistant",
                        "content": assistant_content
                    })
                    message_repo.store_conversation(
                        project_id=project_id,
                        messages_data=messages_to_save,
                        default_model=model_used
                    )
                 except Exception as db_error:
                     print(f"Error saving non-streamed conversation to database: {db_error}")
                     # Decide if non-saving should be an error or just a warning

            # Return the direct result from the orchestrator
            return result_or_stream
            # --- End Non-Streaming Response Handling ---

    except HTTPException as http_exc:
        # Re-raise HTTPExceptions cleanly
        raise http_exc
    except Exception as e:
        # Catch-all for unexpected errors during orchestration/processing
        print(f"Critical Error in /generate endpoint: {e}")
        # Consider logging the full traceback here
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error processing request.")