# miktos_backend/api/projects.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from config.database import get_db
from schemas.user import ProjectCreate, ProjectRead, ProjectUpdate
from repositories import project_repository
from api.auth import get_current_user
from models.database_models import User

router = APIRouter(tags=["Projects"])

# Get all user projects
@router.get("/projects", response_model=List[ProjectRead])
async def get_user_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    projects = project_repository.get_user_projects(db, user_id=current_user.id, skip=skip, limit=limit)
    return projects

# Create a new project
@router.post("/projects", response_model=ProjectRead, status_code=201)
async def create_new_project(
    project: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return project_repository.create_project(db, project, owner_id=current_user.id)

# Get a specific project
@router.get("/projects/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = project_repository.get_project_by_id(db, project_id, owner_id=current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

# Update a project
@router.patch("/projects/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    updated_project = project_repository.update_project(db, project_id, project_data, owner_id=current_user.id)
    if not updated_project:
        raise HTTPException(status_code=404, detail="Project not found")
    return updated_project

# Delete a project
@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    success = project_repository.delete_project(db, project_id, owner_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return None