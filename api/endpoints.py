# miktos_backend/api/endpoints.py
import datetime
import json # Keep for potential error formatting if needed
from fastapi import APIRouter, HTTPException, Body, Depends, status
from fastapi.responses import StreamingResponse # Import StreamingResponse from fastapi
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, AsyncGenerator # Added AsyncGenerator

# Import Pydantic Schemas used in this router
# Import generation schemas directly from api/models.py (or wherever defined)
from .models import GenerateRequest # Ensure this exists and includes project_id

# Import DB session and models
# Assuming get_db is defined in 'dependencies.py' or similar
from dependencies import get_db
from models.database_models import User

# Import Auth dependency and Repository Classes (only if needed for checks)
from api.auth import get_current_user
# Remove MessageRepository import - orchestrator handles saving
# from repositories.message_repository import MessageRepository
from repositories.project_repository import ProjectRepository # Keep if doing ownership check

# Import the core logic handler
# Ensure orchestrator has the refactored process_generation_request
from core import orchestrator

# Create an API router (prefix is handled in main.py)
router = APIRouter()

# Health check endpoint
@router.get(
    "/health",
    summary="Health check endpoint"
    # Tags applied in main.py
)
async def health_check():
    """Simple health check endpoint that returns OK if the API is running."""
    return {"status": "ok", "timestamp": datetime.datetime.utcnow().isoformat()}

# Add this near your existing endpoints
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
    response_class=StreamingResponse, # Correct response class for streaming
    summary="Generate AI completion and store conversation",
    # Tags applied in main.py
)
async def generate_completion_endpoint(
    payload: GenerateRequest = Body(...), # Use the schema, includes project_id
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
    # Return type is handled by response_class
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

    # --- Optional: Verify Project Ownership ---
    # This check is good practice before calling the orchestrator
    project_repo = ProjectRepository(db=db)
    project = project_repo.get_by_id_for_owner(
        project_id=payload.project_id, owner_id=str(current_user.id)
    )
    if not project:
        # How to return error in stream? Yield single error event.
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

    try:
        # Call the orchestrator - it now returns an AsyncGenerator yielding SSE strings
        sse_event_generator: AsyncGenerator[str, None] = orchestrator.process_generation_request(
            **orchestrator_args
        )

        # Directly return the generator wrapped in StreamingResponse
        return StreamingResponse(sse_event_generator, media_type="text/event-stream")

    except Exception as e:
        # Catch unexpected errors *before* starting the stream (e.g., during setup)
        print(f"Critical Error setting up stream in /generate endpoint for project {payload.project_id}: {e}")
        # Log traceback here
        import traceback
        traceback.print_exc()
        # Return an error stream if setup fails
        async def error_stream_500():
            error_data = {
                "error": True,
                "message": f"Internal Server Error setting up generation stream: {str(e)}",
                "type": type(e).__name__
            }
            yield f'data: {json.dumps(error_data)}\n\n'
        # Note: Cannot easily set 500 status code here with async generator error response
        # The client will receive a 200 OK initially, then the error event.
        return StreamingResponse(error_stream_500(), media_type="text/event-stream")