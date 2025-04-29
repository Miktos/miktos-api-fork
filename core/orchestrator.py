# miktos_backend/core/orchestrator.py

import asyncio
import json
from typing import List, Dict, Any, Optional, Union, AsyncGenerator

# --- Database and Schema Imports ---
from sqlalchemy.orm import Session
from fastapi import HTTPException # Import for error handling
import schemas
from repositories import message_repository, project_repository # Import both repos
from models import database_models as models

# --- Integration Client Imports ---
from integrations import openai_client, claude_client, gemini_client

# --- Model Provider Mapping - MODIFIED ---
def get_provider_from_model(model_id: str) -> Optional[str]:
    """Determines the likely provider based on the model ID prefix or structure."""
    model_id_lower = model_id.lower()
    if model_id_lower.startswith("gpt-"): return "openai"
    elif model_id_lower.startswith("claude-"): return "anthropic"
    elif model_id_lower.startswith("gemini-"): return "google"
    elif "/" in model_id_lower:
        provider = model_id_lower.split('/')[0]
        # FIX: Return any provider found before the slash
        # if provider in ["openai", "google", "anthropic"]: return provider # Old check
        if provider: return provider # Return if non-empty
    return None

# --- Main Orchestration Function - UPDATED ---
async def process_generation_request(
    *, # Force keyword arguments
    messages: List[Dict[str, Any]],
    model: str,
    stream: bool = True, # Default stream to True as endpoint expects it
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    # system_prompt: Optional[str] = None, # Removed - will be derived from notes or handled via messages
    project_id: str,
    db: Session,
    user: models.User,
    **provider_specific_kwargs
) -> AsyncGenerator[str, None]:
    """
    Orchestrates the request to the AI provider, injecting project context notes,
    saves user/assistant messages, and yields SSE formatted strings.
    """
    print(f"Orchestrator request for project {project_id}, model: {model}")

    # --- Instantiate Repositories ---
    msg_repo = message_repository.MessageRepository(db=db)
    project_repo = project_repository.ProjectRepository(db=db) # Instantiate Project Repo

    # --- 1. Fetch Project & Notes ---
    project_notes = ""
    try:
        # Fetch project using the repo (includes owner check)
        project = project_repo.get_by_id_for_owner(project_id=project_id, owner_id=user.id)
        if not project:
             # Should be caught by endpoint, but defensive check
             error_msg = "Project not found or access denied."
             print(f"Error for project {project_id}: {error_msg}")
             yield f'data: {json.dumps({"error": True, "message": error_msg, "type": "NotFoundError"})}\n\n'
             return

        if project.context_notes:
            project_notes = project.context_notes.strip()
            if project_notes: # Log only if notes actually exist
                print(f"Found {len(project_notes)} chars of context notes for project {project_id}")

    except Exception as e:
        print(f"Warning: Could not fetch project details/notes for project {project_id}: {e}")
        yield f'data: {json.dumps({"warning": True, "message": "Could not load project context notes."})}\n\n'
        # Continue without notes

    # --- 2. Save User Message ---
    if not messages or messages[-1].get("role") != "user":
        error_msg = "Internal error: Could not identify user message to save."
        print(f"Error for project {project_id}: {error_msg}")
        yield f'data: {json.dumps({"error": True, "message": error_msg})}\n\n'
        return

    user_message_content = messages[-1].get("content")
    try:
        user_message_schema = schemas.MessageCreate(
            project_id=project_id, user_id=user.id, role=schemas.MessageRole.USER, content=user_message_content
        )
        msg_repo.create(obj_in=user_message_schema)
        print(f"Saved user message for project {project_id}")
    except Exception as e:
        print(f"Error saving user message for project {project_id}: {e}")
        yield f'data: {json.dumps({"warning": True, "message": "Failed to save user message to history."})}\n\n'


    # --- 3. Prepare Messages & System Prompt for AI (Inject Notes) ---
    messages_for_api = messages.copy() # Create a copy to modify
    final_system_prompt = None # For providers supporting explicit system prompt

    provider = get_provider_from_model(model) # Get provider for injection logic

    if project_notes:
         # Inject notes based on provider strategy
         if provider in ["anthropic", "google"]:
              final_system_prompt = project_notes # Use dedicated system prompt parameter
              print(f"Injecting project notes ({len(project_notes)} chars) as system prompt for {provider}.")
         elif provider == "openai":
               # Prepend notes as a system message if none exists, otherwise append
               system_msg_index = -1
               for i, msg in enumerate(messages_for_api):
                    if msg.get("role") == "system":
                         system_msg_index = i
                         break
               if system_msg_index != -1:
                    # Append to existing system message
                    messages_for_api[system_msg_index]["content"] = f"{messages_for_api[system_msg_index]['content']}\n\n[Project Context Notes]\n{project_notes}"
                    print(f"Appending project notes ({len(project_notes)} chars) to existing system message for OpenAI.")
               else:
                    # Prepend as new system message
                    messages_for_api.insert(0, {"role": "system", "content": project_notes})
                    print(f"Prepending project notes ({len(project_notes)} chars) as system message for OpenAI.")
         else: # Fallback for unknown providers
              # Prepend notes as a user message clearly marked
              messages_for_api.insert(0, {"role": "user", "content": f"[START CONTEXT NOTES]\n{project_notes}\n[END CONTEXT NOTES]\n\nPlease use the above notes as context for my next message."})
              print(f"Prepending project notes ({len(project_notes)} chars) as faux user message.")


    # --- 4. Routing Logic (Use potentially modified messages_for_api) ---
    actual_model_id = model.split('/')[-1] if '/' in model else model
    if not provider: # Double check provider after potential note injection logic
        error_msg = f"Could not determine provider for model: {model}"
        print(f"Error for project {project_id}: {error_msg}")
        yield f'data: {json.dumps({"error": True, "message": error_msg, "type": "RoutingError"})}\n\n'
        return

    client_func = None
    client_args = {
        "messages": messages_for_api, # Use the (potentially modified) list
        "model": actual_model_id,
        "stream": True,
        "temperature": temperature,
        "max_tokens": max_tokens,
        # Pass system prompt explicitly only if it was set *and* provider uses it
        "system_prompt": final_system_prompt if provider in ["anthropic", "google"] else None,
        **provider_specific_kwargs
    }
    # Remove None values as some clients might not handle them gracefully
    client_args = {k: v for k, v in client_args.items() if v is not None}


    if provider == "openai": client_func = openai_client.generate_completion
    elif provider == "anthropic": client_func = claude_client.generate_completion
    elif provider == "google": client_func = gemini_client.generate_completion
    else:
        error_msg = f"No integration client implemented for provider: {provider} (model: {model})"
        print(f"Error for project {project_id}: {error_msg}")
        yield f'data: {json.dumps({"error": True, "message": error_msg, "type": "RoutingError"})}\n\n'
        return

    # --- 5. Execute Client Call & Handle Streaming (Unchanged from previous correct version) ---
    final_assistant_content = ""; final_model_name_used = actual_model_id; error_occurred = False
    try:
        stream_generator = await client_func(**client_args)
        async for chunk_dict in stream_generator:
            if isinstance(chunk_dict, dict):
                 sse_event_string = f'data: {json.dumps(chunk_dict)}\n\n'
                 yield sse_event_string
                 if chunk_dict.get("delta"): final_assistant_content += chunk_dict["delta"]
                 if chunk_dict.get("model_name"): final_model_name_used = chunk_dict["model_name"]
                 if chunk_dict.get("error"): error_occurred = True; print(f"Stream Error from Client: {chunk_dict.get('message')}")
            else: print(f"Warning: Orchestrator received non-dict chunk: {type(chunk_dict)}")
    except Exception as e:
        error_occurred = True; print(f"Unexpected Error processing stream for {provider}: {e}"); import traceback; traceback.print_exc()
        error_msg = f"Stream processing error: {str(e)}"; yield f'data: {json.dumps({"error": True, "message": error_msg, "type": type(e).__name__})}\n\n'


    # --- 6. Save Assistant Message (Unchanged from previous correct version) ---
    if not error_occurred and final_assistant_content:
        try:
            assistant_message_schema = schemas.MessageCreate(
                project_id=project_id, user_id=user.id, role=schemas.MessageRole.ASSISTANT,
                content=final_assistant_content.strip(), model=final_model_name_used
            )
            msg_repo.create(obj_in=assistant_message_schema)
            print(f"Saved assistant message for project {project_id}")
        except Exception as e: print(f"Error saving assistant message for project {project_id}: {e}")
    elif error_occurred: print(f"Skipping assistant message save for project {project_id} due to stream error.")
    else: print(f"Assistant response empty for project {project_id}, not saving.")