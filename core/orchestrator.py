# miktos_backend/core/orchestrator.py

import asyncio
import json # Import json for formatting SSE data
from typing import List, Dict, Any, Optional, Union, AsyncGenerator

# --- Database and Schema Imports ---
from sqlalchemy.orm import Session
import schemas # Import your schemas module
from repositories import message_repository # Import the message repo
from models import database_models as models # Import User model

# --- Integration Client Imports ---
from integrations import openai_client, claude_client, gemini_client

# --- Model Provider Mapping (Keep as is) ---
def get_provider_from_model(model_id: str) -> Optional[str]:
    """Determines the likely provider based on the model ID prefix."""
    model_id_lower = model_id.lower()
    if model_id_lower.startswith("gpt-"):
        return "openai"
    elif model_id_lower.startswith("claude-"):
        return "anthropic"
    elif model_id_lower.startswith("gemini-"):
        return "google"
    elif "/" in model_id_lower:
        provider = model_id_lower.split('/')[0]
        if provider in ["openai", "google", "anthropic"]: # Add more if clients exist
             return provider
    return None

# --- Main Orchestration Function - MODIFIED ---
async def process_generation_request(
    *, # Force keyword arguments
    messages: List[Dict[str, Any]],
    model: str,
    stream: bool = False, # Default to False, but frontend likely sends True
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    system_prompt: Optional[str] = None,
    project_id: str, # Added project_id
    db: Session, # Added db session
    user: models.User, # Added authenticated user
    **provider_specific_kwargs
) -> AsyncGenerator[str, None]: # Return type changed to SSE string generator
    """
    Orchestrates the request to the appropriate AI model provider client,
    saves user and assistant messages, and yields SSE formatted strings.

    Args:
        messages: List of message dictionaries (including the latest user prompt).
        model: The target model ID.
        stream: Whether to stream the response (should be True for this endpoint).
        temperature: Sampling temperature.
        max_tokens: Max tokens for the completion.
        system_prompt: System prompt/instruction.
        project_id: The ID of the project this conversation belongs to.
        db: SQLAlchemy Session dependency.
        user: The authenticated User object.
        **provider_specific_kwargs: Additional provider arguments.

    Yields:
        Server-Sent Event (SSE) formatted strings (e.g., "data: {...}\\n\\n").
    """
    print(f"Orchestrator received request for project {project_id}, model: {model}, stream: {stream}")

    # --- Instantiate Message Repository ---
    msg_repo = message_repository.MessageRepository(db=db)

    # --- 1. Save User Message ---
    if not messages or messages[-1].get("role") != "user":
        error_msg = "Internal error: Could not identify user message to save."
        print(f"Error for project {project_id}: {error_msg}")
        yield f'data: {json.dumps({"error": True, "message": error_msg})}\n\n'
        return

    user_message_content = messages[-1].get("content")
    try:
        user_message_schema = schemas.MessageCreate(
            project_id=project_id,
            user_id=user.id,
            role=schemas.MessageRole.USER,
            content=user_message_content
        )
        msg_repo.create(obj_in=user_message_schema)
        print(f"Saved user message for project {project_id}")
    except Exception as e:
        # Log error, maybe yield non-fatal error to frontend?
        print(f"Error saving user message for project {project_id}: {e}")
        yield f'data: {json.dumps({"warning": True, "message": "Failed to save user message to history."})}\n\n'


    # --- Routing Logic (Keep as is) ---
    provider = get_provider_from_model(model)
    actual_model_id = model.split('/')[-1] if '/' in model else model

    if not provider:
        error_msg = f"Could not determine provider for model: {model}"
        print(f"Error for project {project_id}: {error_msg}")
        yield f'data: {json.dumps({"error": True, "message": error_msg, "type": "RoutingError"})}\n\n'
        return

    client_func = None
    client_args = {
        "messages": messages,
        "model": actual_model_id,
        "stream": True, # Force stream=True for this orchestrator version
        "temperature": temperature,
        "max_tokens": max_tokens,
        **provider_specific_kwargs
    }

    if provider == "openai":
        print(f"Routing to OpenAI client with model: {actual_model_id}...")
        client_func = openai_client.generate_completion
    elif provider == "anthropic":
        print(f"Routing to Anthropic client with model: {actual_model_id}...")
        client_func = claude_client.generate_completion
        client_args["system_prompt"] = system_prompt
    elif provider == "google":
        print(f"Routing to Google client with model: {actual_model_id}...")
        client_func = gemini_client.generate_completion
        client_args["system_prompt"] = system_prompt
    else:
        error_msg = f"No integration client implemented for provider: {provider} (model: {model})"
        print(f"Error for project {project_id}: {error_msg}")
        yield f'data: {json.dumps({"error": True, "message": error_msg, "type": "RoutingError"})}\n\n'
        return

    # --- Execute Client Call & Handle Streaming ---
    final_assistant_content = ""
    final_model_name_used = actual_model_id # Default to requested model
    error_occurred = False

    try:
        # Await the client call to get the async generator
        stream_generator = await client_func(**client_args)

        # Iterate through the stream generator from the client
        async for chunk_dict in stream_generator:
            # Assuming client yields dictionaries like {"delta": "...", "model_name": "...", "error": ...}
            if isinstance(chunk_dict, dict):
                 # Format the dictionary chunk into an SSE string
                 sse_event_string = f'data: {json.dumps(chunk_dict)}\n\n'
                 yield sse_event_string

                 # Accumulate content and check for errors/model name
                 if chunk_dict.get("delta"):
                     final_assistant_content += chunk_dict["delta"]
                 if chunk_dict.get("model_name"):
                     final_model_name_used = chunk_dict["model_name"]
                 if chunk_dict.get("error"):
                      error_occurred = True
                      print(f"Error received from client stream for project {project_id}: {chunk_dict.get('message')}")
                      # Potentially break or just let stream finish yielding error
            else:
                 # Handle unexpected chunk type from client generator
                 print(f"Warning: Orchestrator received unexpected chunk type: {type(chunk_dict)}")


    except Exception as e:
        error_occurred = True
        print(f"Unexpected Error during stream processing for {provider} on project {project_id}: {e}")
        import traceback
        traceback.print_exc() # Print full traceback for debugging server-side
        error_msg = f"An unexpected error occurred processing the stream from {provider}: {str(e)}"
        yield f'data: {json.dumps({"error": True, "message": error_msg, "type": type(e).__name__})}\n\n'


    # --- 3. Save Assistant Message (After Stream Finishes) ---
    # Only save if no error occurred during the stream and we got content
    if not error_occurred and final_assistant_content:
        try:
            assistant_message_schema = schemas.MessageCreate(
                project_id=project_id,
                user_id=user.id, # Associate with the user's session
                role=schemas.MessageRole.ASSISTANT,
                content=final_assistant_content.strip(),
                model=final_model_name_used # Store the actual model used
                # Add metadata if available
            )
            msg_repo.create(obj_in=assistant_message_schema)
            print(f"Saved assistant message for project {project_id}")
        except Exception as e:
            # Log error saving assistant message, but can't yield to client now
            print(f"Error saving assistant message for project {project_id}: {e}")
    elif error_occurred:
         print(f"Skipping assistant message save for project {project_id} due to stream error.")
    else: # No error, but no content
         print(f"Assistant response was empty for project {project_id}, not saving.")