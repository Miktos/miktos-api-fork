# repositories/project_repository.py
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, Union

# Import the SQLAlchemy model and Enum
from models.database_models import Project, ContextStatus # <-- Import ContextStatus
# Import the BaseRepository
from repositories.base_repository import BaseRepository
# Import the necessary Pydantic schemas
from schemas.project import ProjectCreate, ProjectUpdate # <-- Corrected schema import path if needed

class ProjectRepository(BaseRepository[Project, ProjectCreate, ProjectUpdate]):
    def __init__(self, db: Session):
        super().__init__(model=Project, db=db)

    # --- Project Specific Getters (with owner check) ---
    # get_by_id_for_owner and get_multi_by_owner remain the same

    def get_by_id_for_owner(self, *, project_id: str, owner_id: str) -> Optional[Project]:
        return self.db.query(self.model)\
                 .filter(self.model.id == project_id, self.model.owner_id == owner_id)\
                 .first()

    def get_multi_by_owner(self, *, owner_id: str, skip: int = 0, limit: int = 100) -> List[Project]:
        return (
            self.db.query(self.model)
            .filter(self.model.owner_id == owner_id)
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    # --- Override Base Methods or Add Specific Logic ---

    def create_with_owner(self, *, obj_in: ProjectCreate, owner_id: str) -> Project:
        """
        Create a new project, assign ownership, and set initial context status.
        """
        print(f"[REPO DEBUG - create_with_owner] Input obj_in: {obj_in}") # <-- DEBUG
        obj_in_data = obj_in.model_dump(exclude_unset=True)
        print(f"[REPO DEBUG - create_with_owner] obj_in_data after dump: {obj_in_data}") # <-- DEBUG

        # Determine initial status
        has_repo_url = obj_in_data.get("repository_url") is not None
        initial_context_status = ContextStatus.PENDING if has_repo_url else ContextStatus.NONE
        print(f"[REPO DEBUG - create_with_owner] has_repo_url={has_repo_url}, initial_context_status={initial_context_status.value}") # <-- DEBUG

        # Convert repository_url to string *if it exists*
        if "repository_url" in obj_in_data and obj_in_data["repository_url"]:
             print(f"[REPO DEBUG - create_with_owner] Converting repository_url to string...") # <-- DEBUG
             obj_in_data["repository_url"] = str(obj_in_data["repository_url"])
             print(f"[REPO DEBUG - create_with_owner] repository_url in obj_in_data is now: {obj_in_data.get('repository_url')}") # <-- DEBUG

        # Create the SQLAlchemy model instance
        print(f"[REPO DEBUG - create_with_owner] Initializing self.model with data: {obj_in_data}, owner_id: {owner_id}, context_status: {initial_context_status}") # <-- DEBUG
        try:
            db_obj = self.model(
                **obj_in_data,
                owner_id=owner_id,
                context_status=initial_context_status
            )
            print(f"[REPO DEBUG - create_with_owner] Initialized db_obj. repository_url: {getattr(db_obj, 'repository_url', 'Not Set')}") # <-- DEBUG
        except Exception as e:
            print(f"[REPO DEBUG - ERROR] Failed to initialize self.model: {e}") # <-- DEBUG
            raise e # Re-raise the error

        # Add, commit, refresh
        try:
            print(f"[REPO DEBUG - create_with_owner] Adding to session...") # <-- DEBUG
            self.db.add(db_obj)
            print(f"[REPO DEBUG - create_with_owner] Committing...") # <-- DEBUG
            self.db.commit()
            print(f"[REPO DEBUG - create_with_owner] Committed. Refreshing object...") # <-- DEBUG
            self.db.refresh(db_obj)
            print(f"[REPO DEBUG - create_with_owner] Refreshed.") # <-- DEBUG
            print(f"[REPO DEBUG - create_with_owner] db_obj.repository_url AFTER refresh: {getattr(db_obj, 'repository_url', 'Not Found')}") # <-- DEBUG
        except Exception as e:
            print(f"[REPO DEBUG - ERROR] DB Add/Commit/Refresh failed: {e}") # <-- DEBUG
            self.db.rollback() # Rollback on error
            raise e # Re-raise the error

        print(f"[REPO DEBUG - create_with_owner] Returning db_obj.") # <-- DEBUG
        return db_obj