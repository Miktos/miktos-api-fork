# miktos_backend/api/endpoints.py
import datetime
import json
import traceback # Import traceback
from fastapi import APIRouter, HTTPException, Body, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, AsyncGenerator

# Import Pydantic Schemas used in this router
from .models import GenerateRequest

# Import DB session and models
from dependencies import get_db
from models.database_models import User

# Import Auth dependency and Repository Classes
from api.auth import get_current_user
from repositories.project_repository import ProjectRepository

# Import the core logic handler
from core import orchestrator

# Create an API router (prefix is handled in main.py)
router = APIRouter()

# Health check endpoint
@router.get(
    "/health",
    summary="Health check endpoint"
)
async def health_check():
    """Simple health check endpoint that returns OK if the API is running."""
    try:
        # Python 3.11+ approach
        return {"status": "ok", "timestamp": datetime.datetime.now(datetime.UTC).isoformat()}
    except AttributeError:
        # Fallback for older Python versions
        from datetime import timezone
        return {"status": "ok", "timestamp": datetime.datetime.now(timezone.utc).isoformat()}

# Status check endpoint
@router.get(
    "/status",
    summary="API status check"
)
async def check_status():
    """Check API status - simple status endpoint for monitoring."""
    return {"status": "ok", "version": "0.2.0"}

# Generation endpoint
@router.post(
    "/generate",
    response_class=StreamingResponse,
    summary="Generate AI completion and store conversation",
)
async def generate_completion_endpoint(
    payload: GenerateRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> StreamingResponse:
    """
    Generates a completion from an AI model specified in the request body,
    associating the conversation with the specified project_id.

    - Requires `project_id` in the request body.
    - Stores the conversation (user prompt + assistant response) in the project history.
    - Requires authentication.
    - Streams the response back using Server-Sent Events.
    """
    print(f"Received generate request for project: {payload.project_id}") # Log request

    # --- Verify Project Ownership ---
    project_repo = ProjectRepository(db=db)
    project = project_repo.get_by_id_for_owner(
        project_id=payload.project_id, owner_id=str(current_user.id)
    )
    if not project:
        async def error_stream_404():
            error_data = {
                "error": True,
                "message": "Project not found or not owned by user",
                "type": "NotFoundError"
            }
            yield f'data: {json.dumps(error_data)}\n\n'
        print(f"Project access denied or not found for user {current_user.id}, project {payload.project_id}")
        return StreamingResponse(error_stream_404(), media_type="text/event-stream", status_code=status.HTTP_404_NOT_FOUND)
    # --- End Ownership Check ---

    # Prepare the arguments dictionary for the orchestrator
    orchestrator_args = {
        "messages": payload.messages,
        "model": payload.model,
        "stream": True, # Force streaming for this endpoint
        "temperature": payload.temperature,
        "max_tokens": payload.max_tokens,
        "system_prompt": payload.system_prompt,
        "project_id": payload.project_id, # Pass project_id from payload
        "db": db,                         # Pass db session
        "user": current_user              # Pass authenticated user
        # Add any other relevant kwargs from payload if needed
    }

    # ---- MODIFIED EXCEPTION HANDLING ----
    caught_exception: Optional[Exception] = None # Variable to hold the exception if caught
    sse_event_generator: Optional[AsyncGenerator[str, None]] = None

    try:
        # Call the orchestrator - it now returns an AsyncGenerator yielding SSE strings
        sse_event_generator = orchestrator.process_generation_request(
            **orchestrator_args
        )
        # If orchestrator call succeeds, return the stream immediately
        return StreamingResponse(sse_event_generator, media_type="text/event-stream")

    except Exception as e:
        # Catch unexpected errors *before* starting the stream (e.g., during setup)
        print(f"Critical Error setting up stream in /generate endpoint for project {payload.project_id}: {e}")
        traceback.print_exc()
        caught_exception = e # Store the exception

    # If an exception was caught during setup, return the error stream
    if caught_exception:
        # Define the error stream function separately or pass args
        async def error_stream_500(exc: Exception): # Pass the exception as an argument
            error_data = {
                "error": True,
                 # Use the passed 'exc' argument here
                "message": f"Internal Server Error setting up generation stream: {str(exc)}",
                "type": type(exc).__name__
            }
            # Ensure proper SSE format with double newline
            yield f'data: {json.dumps(error_data)}\n\n'
        # Call the error stream function with the caught exception
        return StreamingResponse(error_stream_500(caught_exception), media_type="text/event-stream")
    # ---- END MODIFIED EXCEPTION HANDLING ----

    # This part should theoretically not be reached if logic is correct,
    # but added as a fallback defensive measure.
    async def fallback_error_stream():
         yield f'data: {json.dumps({"error": True, "message": "Unknown error occurred before streaming", "type": "UnknownError"})}\n\n'
    print("ERROR: Reached end of /generate endpoint unexpectedly after try/except block.")
    return StreamingResponse(fallback_error_stream(), media_type="text/event-stream", status_code=500)