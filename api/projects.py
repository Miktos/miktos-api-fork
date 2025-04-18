# miktos_backend/api/projects.py
from fastapi import APIRouter, Depends, HTTPException, Query, status # Added status
from sqlalchemy.orm import Session
from typing import List, Optional # Added Optional

# Import Dependency Functions and User Model
from config.database import get_db
from api.auth import get_current_user # Import dependency to get the logged-in user
from models.database_models import User # Import the User model for type hinting

# --- Import Schemas ---
from schemas.user import ProjectCreate, ProjectRead, ProjectUpdate

# --- Import Repository CLASS ---
from repositories.project_repository import ProjectRepository # Import the class

# --- Define Router ---
# Define the prefix here for all project routes
router = APIRouter(
    prefix="/api/v1/projects", # Define prefix here
    tags=["Projects"]
)

# Get all projects for the current logged-in user
@router.get("/", response_model=List[ProjectRead]) # Path relative to prefix
async def get_user_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve projects for the current authenticated user."""
    # Instantiate the repository
    project_repo = ProjectRepository(db=db)
    # Call the correct method from the instance
    projects = project_repo.get_multi_by_owner(owner_id=str(current_user.id), skip=skip, limit=limit)
    return projects

# Create a new project for the current logged-in user
@router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED) # Path relative to prefix
async def create_new_project(
    project: ProjectCreate, # Request body with project details
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new project owned by the current authenticated user."""
    # Instantiate the repository
    project_repo = ProjectRepository(db=db)
    # Call the method that handles creation and owner assignment
    # Ensure current_user.id is converted to string if your DB expects strings for IDs
    created_project = project_repo.create_with_owner(
        obj_in=project, owner_id=str(current_user.id)
    )
    return created_project

# Get a specific project by ID, ensuring it belongs to the current user
@router.get("/{project_id}", response_model=ProjectRead) # Path relative to prefix
async def get_project(
    project_id: str, # Path parameter
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve a specific project by ID, verifying ownership."""
    # Instantiate the repository
    project_repo = ProjectRepository(db=db)
    # Call the method that verifies ownership
    project = project_repo.get_by_id_for_owner(project_id=project_id, owner_id=str(current_user.id))
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or not owned by user")
    return project

# Update a project, ensuring it belongs to the current user
@router.patch("/{project_id}", response_model=ProjectRead) # Path relative to prefix
async def update_project(
    project_id: str, # Path parameter
    project_update: ProjectUpdate, # Request body with updates
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a specific project, verifying ownership."""
    # Instantiate the repository
    project_repo = ProjectRepository(db=db)
    # Call the method that verifies ownership before updating
    updated_project = project_repo.update_with_owner_check(
        project_id=project_id, owner_id=str(current_user.id), obj_in=project_update
    )
    if updated_project is None:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or not owned by user")
    return updated_project

# Delete a project, ensuring it belongs to the current user
@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT) # Path relative to prefix
async def delete_project(
    project_id: str, # Path parameter
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a specific project, verifying ownership."""
    # Instantiate the repository
    project_repo = ProjectRepository(db=db)
    # Call the method that verifies ownership before deleting
    deleted_project = project_repo.remove_with_owner_check(project_id=project_id, owner_id=str(current_user.id))
    if deleted_project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or not owned by user")
    # No response body needed for 204
    return None