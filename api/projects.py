# miktos_backend/api/projects.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

# --- Import Dependency Functions and User Model ---
# Assuming get_db is defined in 'dependencies.py'
from dependencies import get_db
# Import get_current_user from the auth module
from api.auth import get_current_user # <--- CORRECT NAME
from models.database_models import User # Import the User model for type hinting

# --- Import Schemas ---
import schemas

# --- Import Repository CLASSES ---
from repositories.project_repository import ProjectRepository
from repositories.message_repository import MessageRepository

# --- Define Router ---
router = APIRouter(
    tags=["Projects"] # Tag for grouping in API docs
)

# === Existing Project CRUD Endpoints ===

@router.get(
    "/",
    response_model=List[schemas.ProjectRead],
    summary="Get User's Projects"
)
async def get_user_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user), # Correct name
    db: Session = Depends(get_db)
):
    """Retrieve projects for the current authenticated user."""
    project_repo = ProjectRepository(db=db)
    projects = project_repo.get_multi_by_owner(owner_id=str(current_user.id), skip=skip, limit=limit)
    return projects

@router.post(
    "/",
    response_model=schemas.ProjectRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create New Project"
)
async def create_new_project(
    project: schemas.ProjectCreate,
    current_user: User = Depends(get_current_user), # Correct name
    db: Session = Depends(get_db)
):
    """Create a new project owned by the current authenticated user."""
    project_repo = ProjectRepository(db=db)
    created_project = project_repo.create_with_owner(
        obj_in=project, owner_id=str(current_user.id)
    )
    return created_project

@router.get(
    "/{project_id}",
    response_model=schemas.ProjectRead,
    summary="Get Specific Project"
)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user), # Correct name
    db: Session = Depends(get_db)
):
    """Retrieve a specific project by ID, verifying ownership."""
    project_repo = ProjectRepository(db=db)
    project = project_repo.get_by_id_for_owner(project_id=project_id, owner_id=str(current_user.id))
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or not owned by user")
    return project

@router.patch(
    "/{project_id}",
    response_model=schemas.ProjectRead,
    summary="Update Project"
)
async def update_project(
    project_id: str,
    project_update: schemas.ProjectUpdate,
    current_user: User = Depends(get_current_user), # Correct name
    db: Session = Depends(get_db)
):
    """Update a specific project, verifying ownership."""
    project_repo = ProjectRepository(db=db)
    updated_project = project_repo.update_with_owner_check(
        project_id=project_id, owner_id=str(current_user.id), obj_in=project_update
    )
    if updated_project is None:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or not owned by user")
    return updated_project

@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Project"
)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user), # Correct name
    db: Session = Depends(get_db)
):
    """Delete a specific project, verifying ownership."""
    project_repo = ProjectRepository(db=db)
    deleted_project = project_repo.remove_with_owner_check(project_id=project_id, owner_id=str(current_user.id))
    if deleted_project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or not owned by user")
    return None

# === NEW Endpoint for Project Messages ===

@router.get(
    "/{project_id}/messages",
    response_model=List[schemas.MessageRead],
    summary="Get Project Chat History",
    tags=["Projects", "Messages"]
)
def read_project_messages(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # Correct name
):
    """
    Retrieves the chat message history for a specific project owned by the current user.
    Messages are returned ordered by timestamp (oldest first).
    """
    msg_repo = MessageRepository(db=db)
    try:
        messages = msg_repo.get_multi_by_project(
            project_id=project_id,
            user_id=str(current_user.id),
            ascending=True
        )
        return messages
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error fetching messages for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching project messages."
        )