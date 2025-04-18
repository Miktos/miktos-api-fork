# miktos_backend/api/endpoints.py
import datetime
from fastapi import APIRouter, HTTPException, Body, Depends
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
from sqlalchemy.orm import Session
from typing import Optional

# Import modules
from .models import GenerateRequest, GenerateResponse
from core import orchestrator
from config.database import get_db
from models.database_models import User, Project
from api.auth import get_current_user
from repositories import message_repository, project_repository

# Create an API router
router = APIRouter()

# Health check endpoint
@router.get(
    "/health",
    tags=["System"],
    summary="Health check endpoint"
)
async def health_check():
    """Simple health check endpoint that returns OK if the API is running."""
    return {"status": "ok", "timestamp": datetime.datetime.utcnow().isoformat()}

# Generation endpoint with optional project context
@router.post(
    "/generate",
    tags=["Generation"],
    response_model=GenerateResponse
)
async def generate_completion_endpoint(
    request: GenerateRequest = Body(...),
    current_user: Optional[User] = Depends(get_current_user),
    project_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Generates a completion from an AI model with optional project context.
    If project_id is provided, the conversation will be stored in that project.
    """
    # Check project ownership if a project ID is provided
    if project_id and current_user:
        project = project_repository.get_project_by_id(db, project_id, owner_id=current_user.id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or not owned by user")
    
    # Prepare arguments for the orchestrator
    orchestrator_args = {
        "messages": request.messages,
        "model": request.model,
        "stream": request.stream,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
    }

    try:
        result_or_stream = await orchestrator.process_generation_request(**orchestrator_args)

        if request.stream:
            # For streaming responses
            is_async_generator = hasattr(result_or_stream, '__aiter__')

            if not is_async_generator:
                print(f"Stream requested but received non-generator: {result_or_stream}")
                error_payload = result_or_stream if isinstance(result_or_stream, dict) else {"error": True, "message":"Unknown stream error"}

                async def error_stream():
                    try:
                        yield {"event": "error", "data": json.dumps(error_payload)}
                    except TypeError as e:
                        yield {"event": "error", "data": json.dumps({"error": True, "message": f"Non-serializable error occurred: {e}"})}
                return EventSourceResponse(error_stream())

            # Set up a special stream wrapper to save to database after completion
            accumulated_chunks = []
            
            async def stream_wrapper():
                accumulated_content = ""
                model_used = None
                
                try:
                    async for chunk in result_or_stream:
                        # Keep track of chunks for saving later
                        accumulated_chunks.append(chunk)
                        
                        # Update accumulated content if this chunk has content
                        if chunk.get("delta"):
                            accumulated_content += chunk.get("delta")
                        
                        # Capture the model name if present
                        if chunk.get("model_name") and not model_used:
                            model_used = chunk.get("model_name")
                            
                        # Determine if this is a final or error chunk
                        is_final = chunk.get("is_final", False)
                        is_error = chunk.get("error", False)
                        
                        # Forward chunk to client
                        if is_error:
                            yield {"event": "error", "data": json.dumps(chunk)}
                        elif is_final:
                            yield {"event": "final", "data": json.dumps(chunk)}
                            
                            # Save completed conversation to database if needed
                            if project_id and current_user and not is_error:
                                # Create and save messages
                                try:
                                    messages_to_save = request.messages.copy()
                                    # Add assistant response
                                    messages_to_save.append({
                                        "role": "assistant",
                                        "content": accumulated_content
                                    })
                                    message_repository.store_conversation(db, project_id, messages_to_save, model=model_used)
                                except Exception as db_error:
                                    print(f"Error saving conversation to database: {db_error}")
                                    # Don't interrupt the stream for database errors
                        elif chunk.get("delta") is not None:
                            yield {"event": "message", "data": json.dumps(chunk)}
                            
                except Exception as e:
                    error_payload = {"error": True, "message": f"Stream consumption error: {str(e)}"}
                    yield {"event": "error", "data": json.dumps(error_payload)}
                    
            return EventSourceResponse(stream_wrapper())
        else:
            # Non-streaming response
            if isinstance(result_or_stream, dict) and result_or_stream.get("error"):
                status_code = 500
                if result_or_stream.get("status_code"):
                    status_code = result_or_stream["status_code"]
                raise HTTPException(status_code=status_code, detail=result_or_stream.get("message", "An unknown error occurred."))
            
            # Save to database if project provided
            if project_id and current_user and not result_or_stream.get("error"):
                try:
                    messages_to_save = request.messages.copy()
                    # Add assistant response
                    messages_to_save.append({
                        "role": "assistant",
                        "content": result_or_stream.get("content", "")
                    })
                    message_repository.store_conversation(db, project_id, messages_to_save, model=result_or_stream.get("model_name"))
                except Exception as db_error:
                    print(f"Error saving conversation to database: {db_error}")
                    # Continue even if database save fails
            
            return result_or_stream

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"Critical Error in /generate endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")