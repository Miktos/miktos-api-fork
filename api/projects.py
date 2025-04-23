# miktos_backend/api/projects.py
print("--- Loading api/projects.py ---") # Debug Load

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional

# --- Import Dependency Functions and User Model ---
from dependencies import get_db
from api.auth import get_current_user # Use the actual function name
from models.database_models import User, ContextStatus
from config.database import SessionLocal # Import your session factory

# --- Import Schemas ---
import schemas

# --- Import Repository CLASSES ---
from repositories.project_repository import ProjectRepository
from repositories.message_repository import MessageRepository

# --- Import Services ---
from services.git_service import clone_or_update_repository, remove_repository

print("--- Imports complete in api/projects.py ---") # Debug Load

# --- Define Router ---
router = APIRouter(
    # Prefix applied in main.py
    tags=["Projects"]
)
print("--- Defined projects router in api/projects.py ---") # Debug Load

# === Existing Project CRUD Endpoints (with Background Tasks) ===

@router.get(
    "/",
    response_model=List[schemas.ProjectRead],
    summary="Get User's Projects"
)
async def get_user_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user), # Corrected dependency name
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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user), # Corrected dependency name
    db: Session = Depends(get_db)
):
    """
    Create a new project owned by the current authenticated user.
    If a repository_url is provided, cloning will start in the background.
    """
    print(f"[Endpoint Call] create_new_project called for user {current_user.id}") # Endpoint log
    project_repo = ProjectRepository(db=db)
    # Assuming create_with_owner correctly handles new fields and status
    created_project = project_repo.create_with_owner(
        obj_in=project, owner_id=str(current_user.id)
    )

    # --- Trigger background clone if URL provided ---
    if created_project.repository_url:
        # --- ADDED DEBUG PRINTS ---
        print(f"--- DEBUG: Repository URL found: {created_project.repository_url}")
        print(f"--- DEBUG: Attempting to add background task for project {created_project.id} ---")
        try:
            # Ensure SessionLocal is correctly imported and is the factory
            if not SessionLocal:
                 print("--- DEBUG: ERROR SessionLocal is not defined or imported correctly! ---")
                 raise ValueError("SessionLocal factory is not available for background task.")

            background_tasks.add_task(
                clone_or_update_repository,
                project_id=str(created_project.id),
                repo_url=str(created_project.repository_url),
                session_factory=SessionLocal
            )
            print(f"--- DEBUG: Successfully added background task for project {created_project.id} ---")
        except Exception as e:
            print(f"--- DEBUG: ERROR adding background task: {e} ---")
            # Consider how to handle this error - maybe return a specific status?
        # --- END ADDED DEBUG PRINTS ---
    else:
         print(f"--- DEBUG: No repository URL found for project {created_project.id}, skipping background task. ---")
    # ----------------------------------------------

    print(f"--- DEBUG: Returning response for project {created_project.id} ---")
    return created_project

@router.get(
    "/{project_id}",
    response_model=schemas.ProjectRead,
    summary="Get Specific Project"
)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user), # Corrected dependency name
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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user), # Corrected dependency name
    db: Session = Depends(get_db)
):
    """
    Update a specific project, verifying ownership.
    If the repository_url is added or changed, cloning/updating starts in the background.
    """
    project_repo = ProjectRepository(db=db)
    updated_project = project_repo.update_with_owner_check(
        project_id=project_id, owner_id=str(current_user.id), obj_in=project_update
    )
    if updated_project is None:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or not owned by user")

    if updated_project.context_status == ContextStatus.PENDING and updated_project.repository_url:
         print(f"API: Adding background task to clone/update repo for project {updated_project.id} due to URL change.")
         background_tasks.add_task(
             clone_or_update_repository,
             project_id=str(updated_project.id),
             repo_url=str(updated_project.repository_url),
             session_factory=SessionLocal
         )
    return updated_project

@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Project"
)
async def delete_project(
    project_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user), # Corrected dependency name
    db: Session = Depends(get_db)
):
    """
    Delete a specific project, verifying ownership.
    The associated repository clone will be removed in the background.
    """
    project_repo = ProjectRepository(db=db)
    project_to_delete = project_repo.get_by_id_for_owner(project_id=project_id, owner_id=str(current_user.id))
    if project_to_delete is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or not owned by user")

    print(f"API: Adding background task to remove repo for project {project_id}")
    background_tasks.add_task(remove_repository, project_id=project_id)

    db.delete(project_to_delete)
    db.commit()
    return None

@router.get(
    "/{project_id}/messages",
    response_model=List[schemas.MessageRead],
    summary="Get Project Chat History",
    tags=["Messages"] # Changed tag for clarity
)
def read_project_messages(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # Corrected dependency name
):
    """
    Retrieves the chat message history for a specific project owned by the current user.
    """
    project_repo = ProjectRepository(db=db)
    project = project_repo.get_by_id_for_owner(project_id=project_id, owner_id=str(current_user.id))
    if project is None:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or not owned by user")

    msg_repo = MessageRepository(db=db)
    try:
        messages = msg_repo.get_multi_by_project(
            project_id=project_id,
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

print("--- Finished loading api/projects.py ---") # Debug Load