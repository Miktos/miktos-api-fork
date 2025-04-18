# miktos_backend/repositories/project_repository.py
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, Union
from models.database_models import Project
from repositories.base_repository import BaseRepository
from schemas.user import ProjectCreate, ProjectUpdate

class ProjectRepository(BaseRepository[Project, ProjectCreate]):
    def __init__(self, db: Session):
        super().__init__(Project, db)
    
    def get_by_id(self, project_id: str, owner_id: Optional[str] = None) -> Optional[Project]:
        """Get a project by ID, optionally filtering by owner"""
        query = self.db.query(Project).filter(Project.id == project_id)
        if owner_id:
            query = query.filter(Project.owner_id == owner_id)
        return query.first()
    
    def get_user_projects(self, user_id: str, skip: int = 0, limit: int = 100) -> List[Project]:
        """Get all projects for a specific user"""
        return self.db.query(Project).filter(Project.owner_id == user_id).offset(skip).limit(limit).all()
    
    def create_for_user(self, user_id: str, obj_in: ProjectCreate) -> Project:
        """Create a new project for a user"""
        db_obj = Project(
            name=obj_in.name,
            description=obj_in.description,
            context_notes=obj_in.context_notes,
            owner_id=user_id
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def update_for_user(self, project_id: str, user_id: str, obj_in: Union[ProjectUpdate, Dict[str, Any]]) -> Optional[Project]:
        """Update a project, verifying ownership"""
        db_obj = self.get_by_id(project_id, owner_id=user_id)
        if not db_obj:
            return None
        
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        
        return super().update(db_obj, update_data)
    
    def delete_for_user(self, project_id: str, user_id: str) -> bool:
        """Delete a project, verifying ownership"""
        db_obj = self.get_by_id(project_id, owner_id=user_id)
        if not db_obj:
            return False
        
        self.db.delete(db_obj)
        self.db.commit()
        return True