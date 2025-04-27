# api/projects.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Annotated, Dict, Any
import uuid

# --- Corrected Imports ---
from dependencies import get_db
from models.database_models import User, Project, ContextStatus, Message
from api.auth import get_current_user

# Import Repositories
from repositories.project_repository import ProjectRepository
from repositories.message_repository import MessageRepository

# --- Import Schemas Explicitly ---
from schemas.project import ProjectCreate, ProjectUpdate, ProjectRead # Explicit import

# Import Services and Session Factory
from services import git_service
from config.database import SessionLocal

# Import Pydantic BaseModel for debug schema
from pydantic import BaseModel as PydanticBaseModel

# Router Setup
router = APIRouter(
    prefix="/api/v1/projects",
    tags=["Projects"]
)

# Helper function to convert SQLAlchemy model to dict with proper serialization
def serialize_project(project: Project) -> Dict[str, Any]:
    """Convert a project SQLAlchemy model to a JSON-serializable dict"""
    if not project:
        return None
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "context_notes": project.context_notes,
        "repository_url": project.repository_url,
        "owner_id": str(project.owner_id),
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
        "context_status": project.context_status.value if project.context_status else ContextStatus.NONE.value
    }

# Helper function to convert a list of models to dicts
def serialize_projects(projects: List[Project]) -> List[Dict[str, Any]]:
    """Convert a list of project SQLAlchemy models to a list of dicts"""
    return [serialize_project(project) for project in projects]

# Helper function to convert message SQLAlchemy model to dict
def serialize_message(message: Message) -> Dict[str, Any]:
    """Convert a message SQLAlchemy model to a JSON-serializable dict"""
    return {
        "id": str(message.id),
        "project_id": str(message.project_id),
        "user_id": str(message.user_id) if message.user_id else None,
        "role": message.role,
        "content": message.content,
        "model": message.model,
        "message_metadata": message.message_metadata,
        "created_at": message.created_at.isoformat() if message.created_at else None
    }

# --- Debug Endpoint ---
class DebugSchema(PydanticBaseModel):
    field_a: str
    repository_url: Optional[str] = None
    another_field: Optional[int] = None

@router.post("/debug-repo-url", tags=["Debug"], status_code=200)
async def debug_repo_url_endpoint(payload: DebugSchema):
    """Endpoint solely for debugging repository_url parsing."""
    print(f"--- [DEBUG ENDPOINT /debug-repo-url] ---")
    print(f"Received payload object type: {type(payload)}")
    print(f"Received payload object repr: {payload!r}")
    has_repo_url_attr = hasattr(payload, 'repository_url')
    repo_url_value = getattr(payload, 'repository_url', 'ATTRIBUTE_MISSING')
    print(f"hasattr(payload, 'repository_url'): {has_repo_url_attr}")
    print(f"getattr(payload, 'repository_url', 'ATTRIBUTE_MISSING'): {repo_url_value}")
    dumped_data = payload.model_dump()
    print(f"Payload model_dump(): {dumped_data}")
    print(f"--- [END DEBUG ENDPOINT] ---")
    return {"received_dump": dumped_data, "has_attr": has_repo_url_attr, "attr_value": repo_url_value}


# --- Create Project Endpoint ---
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_project(
    request: Request,
    project_in: ProjectCreate,
    *,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """
    Create a new project owned by the current user.
    Triggers background processing if repository_url is provided.
    """
    # Debug logging
    try:
        body_json = await request.json()
        print(f"[API DEBUG] Raw request body JSON: {body_json}")
    except Exception as e:
        raw_body = await request.body()
        print(f"[API DEBUG] Error reading request body as JSON: {e}, Raw Body: {raw_body!r}")

    print(f"[API /projects POST] User {current_user.id} creating project. Raw input model repr: {project_in!r}")
    try:
        input_data = project_in.model_dump()
        print(f"[API DEBUG] Project input fields after model_dump(): {input_data}")
    except Exception as e:
        print(f"[API DEBUG] ERROR during project_in.model_dump(): {e}")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid input data: {e}")

    # Create project in DB
    project_repo = ProjectRepository(db=db)
    try:
        created_project = project_repo.create_with_owner(
            obj_in=project_in,
            owner_id=current_user.id
        )
        print(f"[API /projects POST] Project created in DB. ID: {created_project.id}, Repo URL: {created_project.repository_url}")
        # Refresh to get latest DB state (good practice)
        db.refresh(created_project)
    except Exception as e:
        print(f"[API /projects POST] ERROR creating project in DB: {e}")
        db.rollback() # Rollback on error
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create project in database: {str(e)}")

    # Handle background task
    if created_project and created_project.repository_url:
        if created_project.context_status == ContextStatus.PENDING:
            print(f"[API /projects POST] Queuing background task for project {created_project.id} and URL {created_project.repository_url}")
            try:
                # Skip actual task execution in test environment if needed
                if hasattr(db, '_is_test_db') and getattr(db, '_is_test_db', False):
                     print(f"[API /projects POST] Test mode detected, skipping actual background task execution")
                else:
                     background_tasks.add_task(
                         git_service.clone_or_update_repository,
                         project_id=str(created_project.id),
                         repo_url=str(created_project.repository_url),
                         session_factory=SessionLocal
                     )
                print(f"[API /projects POST] Background task added successfully.")
            except Exception as e:
                print(f"[API /projects POST] ERROR adding background task: {e}")
        else:
            print(f"[API /projects POST] Project created with Repo URL, but status is {created_project.context_status}, not PENDING. Skipping initial background task.")
    else:
        print(f"[API /projects POST] No repository URL found on created project (or status not PENDING), skipping background task.")

    # Prepare response
    print(f"[API /projects POST] Preparing response.")
    result = serialize_project(created_project)
    print(f"[API DEBUG] Final response data: {result}")

    # REMOVED: db.commit() - Let the dependency fixture handle commit/rollback
    return JSONResponse(content=result, status_code=status.HTTP_201_CREATED)


@router.get("/", response_model=None)
async def get_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    *,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """ Get all projects owned by the current user. """
    project_repo = ProjectRepository(db=db)
    projects = project_repo.get_multi_by_owner(
        owner_id=current_user.id, skip=skip, limit=limit
    )
    result = serialize_projects(projects)
    print(f"[API DEBUG] Get projects response count: {len(result)}")
    # REMOVED: db.commit()
    return JSONResponse(content=result)


# --- Corrected get_project endpoint ---
@router.get("/{project_id}", response_model=None)
async def get_project(
    project_id: uuid.UUID, # Use correct type hint
    *,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Get a specific project by ID"""
    print(f"[API DEBUG] Getting project with ID: {project_id} for user {current_user.id}")
    project_repo = ProjectRepository(db=db)
    # Use the repository method directly
    project = project_repo.get_by_id_for_owner(project_id=project_id, owner_id=current_user.id)

    if not project:
        print(f"[API DEBUG] Project {project_id} not found or not owned by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or not owned by current user"
        )

    result = serialize_project(project)
    print(f"[API DEBUG] Get project response: {result}")
    # REMOVED: db.commit()
    return JSONResponse(content=result)


@router.patch("/{project_id}", response_model=None)
async def update_project(
    project_id: uuid.UUID,
    request: Request,
    project_update: ProjectUpdate,
    *,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """ Update a project's details (must be owned by the current user). """
    print(f"[API DEBUG] Updating project {project_id} for user {current_user.id}")
    # Debug logging
    try: body_json = await request.json(); print(f"[API DEBUG] Raw request body JSON: {body_json}")
    except Exception as e: raw_body = await request.body(); print(f"[API DEBUG] Error reading request body as JSON: {e}, Raw Body: {raw_body!r}")

    print(f"[API /projects PATCH] User {current_user.id} updating project {project_id}. Raw input model repr: {project_update!r}")
    try: update_data = project_update.model_dump(exclude_unset=True); print(f"[API DEBUG] Update project input fields after model_dump(exclude_unset=True): {update_data}")
    except Exception as e: print(f"[API DEBUG] ERROR during project_update.model_dump(): {e}"); raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid update data: {e}")
    if not update_data: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update data provided.")

    project_repo = ProjectRepository(db=db)
    db_project = project_repo.get_by_id_for_owner(project_id=project_id, owner_id=current_user.id)
    if not db_project: print(f"[API DEBUG] Project {project_id} not found or not owned by user {current_user.id} for update"); raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or not owned by current user to update")

    original_repo_url = db_project.repository_url
    repo_url_provided_in_update = 'repository_url' in update_data

    try:
        # Call the correct repository method that handles context_status logic
        updated_project = project_repo.update_with_owner_check(
            project_id=project_id,      # Pass the project_id from path param
            owner_id=current_user.id, # Pass the owner_id from auth dependency
            obj_in=project_update       # Pass the Pydantic input model
        )
        # The repository method now handles commit and refresh internally
        # db.refresh(updated_project) # Refresh is done inside update_with_owner_check

        # Add a check just in case (shouldn't happen if get_by_id_for_owner passed before)
        if updated_project is None:
            print(f"[API /projects PATCH] ERROR: update_with_owner_check returned None unexpectedly for project {project_id}")
            # If the initial get succeeded but update returns None, it implies an internal issue or race condition.
            # 404 might still be appropriate, or 500 depending on how you view it.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project disappeared during update process")

        print(f"[API /projects PATCH] Project update processed by repository. ID: {updated_project.id}, New Repo URL: {updated_project.repository_url}, New Status: {updated_project.context_status}")

    except HTTPException as http_exc:
        # Re-raise HTTPExceptions directly (like 404 from repo)
        raise http_exc
    except Exception as e:
        print(f"[API /projects PATCH] ERROR processing project update: {e}")
        # db.rollback() # Repository method should handle rollback on its commit failure
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to process project update: {str(e)}")

    # Handle background task
    should_trigger_background_task = False
    if repo_url_provided_in_update and updated_project.repository_url != original_repo_url:
        print(f"[API /projects PATCH] Repository URL changed from '{original_repo_url}' to '{updated_project.repository_url}'.")
        if updated_project.context_status == ContextStatus.PENDING: should_trigger_background_task = True
        else: print(f"[API /projects PATCH] Repo URL changed, but status is {updated_project.context_status}, not PENDING. Background task check deferred.")
    if should_trigger_background_task and updated_project.repository_url:
        print(f"[API /projects PATCH] Queuing background task for updated project {updated_project.id}")
        try:
             if hasattr(db, '_is_test_db') and getattr(db, '_is_test_db', False): print(f"[API /projects PATCH] Test mode detected, skipping actual background task execution")
             else: background_tasks.add_task(git_service.clone_or_update_repository, project_id=str(updated_project.id), repo_url=str(updated_project.repository_url), session_factory=SessionLocal)
             print(f"[API /projects PATCH] Background task added successfully.")
        except Exception as e: print(f"[API /projects PATCH] ERROR adding background task: {e}")
    elif repo_url_provided_in_update: print(f"[API /projects PATCH] Repo URL provided, but conditions not met to trigger background task (URL same or status not PENDING).")
    else: print(f"[API /projects PATCH] No repository URL in update data or conditions not met, skipping background task trigger.")

    # Prepare response
    print(f"[API /projects PATCH] Preparing response.")
    result = serialize_project(updated_project)
    print(f"[API DEBUG] Final update response: {result}")

    # REMOVED: db.commit()
    return JSONResponse(content=result)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    *,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """ Delete a project (must be owned by the current user). """
    print(f"[API DEBUG] Deleting project {project_id} for user {current_user.id}")
    project_repo = ProjectRepository(db=db)
    deleted_project = project_repo.remove_with_owner_check(
        project_id=project_id,
        owner_id=current_user.id
    )
    if not deleted_project:
        print(f"[API DEBUG] Project {project_id} not found or not owned by user {current_user.id} for deletion")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or not owned by current user to delete")

    print(f"[API /projects DELETE] Queuing background task to remove repo data for project {project_id}")
    try:
        if hasattr(db, '_is_test_db') and getattr(db, '_is_test_db', False): print(f"[API /projects DELETE] Test mode detected, skipping actual background task execution")
        else: background_tasks.add_task(git_service.remove_repository, project_id=str(project_id))
        print(f"[API /projects DELETE] Background task added successfully.")
    except Exception as e: print(f"[API /projects DELETE] ERROR adding background task: {e}")

    # REMOVED: db.commit() - delete is typically committed by repo method or fixture
    return None


@router.get("/{project_id}/messages", response_model=None)
async def get_project_messages(
    project_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    *,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """ Get all messages for a specific project (must be owned by the current user). """
    print(f"[API DEBUG] Getting messages for project {project_id} for user {current_user.id}")
    project_repo = ProjectRepository(db=db)
    project = project_repo.get_by_id_for_owner(project_id=project_id, owner_id=current_user.id)
    if not project: print(f"[API DEBUG] Project {project_id} not found or not owned by user {current_user.id} for message retrieval"); raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or not owned by current user")

    message_repo = MessageRepository(db=db)
    messages = message_repo.get_multi_by_project(project_id=project_id, skip=skip, limit=limit)
    result = [serialize_message(message) for message in messages]
    # REMOVED: db.commit()
    return JSONResponse(content=result)