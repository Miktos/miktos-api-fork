# repositories/project_repository.py
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, Union

# Import the SQLAlchemy model and Enum
from models.database_models import Project, ContextStatus
# Import the BaseRepository
from repositories.base_repository import BaseRepository
# Import the necessary Pydantic schemas
from schemas.project import ProjectCreate, ProjectUpdate

class ProjectRepository(BaseRepository[Project, ProjectCreate, ProjectUpdate]):
    def __init__(self, db: Session):
        super().__init__(model=Project, db=db)

    # --- Project Specific Getters (with owner check) ---
    def get_by_id_for_owner(self, *, project_id: str, owner_id: str) -> Optional[Project]:
        """Get a project by ID only if it belongs to the specified owner"""
        return self.db.query(self.model)\
                 .filter(self.model.id == project_id, self.model.owner_id == owner_id)\
                 .first()

    def get_multi_by_owner(self, *, owner_id: str, skip: int = 0, limit: int = 100) -> List[Project]:
        """Get multiple projects belonging to a specific owner"""
        return (
            self.db.query(self.model)
            .filter(self.model.owner_id == owner_id)
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    # --- Owner-checked CRUD Operations ---
    def create_with_owner(self, *, obj_in: ProjectCreate, owner_id: str) -> Project:
        """
        Create a new project, assign ownership, and set initial context status.
        """
        print(f"[REPO DEBUG - create_with_owner] Input obj_in: {obj_in}")
        obj_in_data = obj_in.model_dump(exclude_unset=True)
        print(f"[REPO DEBUG - create_with_owner] obj_in_data after dump: {obj_in_data}")

        # Determine initial status
        has_repo_url = obj_in_data.get("repository_url") is not None
        initial_context_status = ContextStatus.PENDING if has_repo_url else ContextStatus.NONE
        print(f"[REPO DEBUG - create_with_owner] has_repo_url={has_repo_url}, initial_context_status={initial_context_status.value}")

        # Convert repository_url to string *if it exists*
        if "repository_url" in obj_in_data and obj_in_data["repository_url"]:
             print(f"[REPO DEBUG - create_with_owner] Converting repository_url to string...")
             obj_in_data["repository_url"] = str(obj_in_data["repository_url"])
             print(f"[REPO DEBUG - create_with_owner] repository_url in obj_in_data is now: {obj_in_data.get('repository_url')}")

        # Create the SQLAlchemy model instance
        print(f"[REPO DEBUG - create_with_owner] Initializing self.model with data: {obj_in_data}, owner_id: {owner_id}, context_status: {initial_context_status}")
        try:
            db_obj = self.model(
                **obj_in_data,
                owner_id=owner_id,
                context_status=initial_context_status
            )
            print(f"[REPO DEBUG - create_with_owner] Initialized db_obj. repository_url: {getattr(db_obj, 'repository_url', 'Not Set')}")
        except Exception as e:
            print(f"[REPO DEBUG - ERROR] Failed to initialize self.model: {e}")
            raise e # Re-raise the error

        # Add, commit, refresh
        try:
            print(f"[REPO DEBUG - create_with_owner] Adding to session...")
            self.db.add(db_obj)
            print(f"[REPO DEBUG - create_with_owner] Committing...")
            self.db.commit()
            print(f"[REPO DEBUG - create_with_owner] Committed. Refreshing object...")
            self.db.refresh(db_obj)
            print(f"[REPO DEBUG - create_with_owner] Refreshed.")
            print(f"[REPO DEBUG - create_with_owner] db_obj.repository_url AFTER refresh: {getattr(db_obj, 'repository_url', 'Not Found')}")
        except Exception as e:
            print(f"[REPO DEBUG - ERROR] DB Add/Commit/Refresh failed: {e}")
            self.db.rollback() # Rollback on error
            raise e # Re-raise the error

        print(f"[REPO DEBUG - create_with_owner] Returning db_obj.")
        return db_obj
    
          
    def update_with_owner_check(self, *, project_id: str, owner_id: str, obj_in: Union[ProjectUpdate, Dict[str, Any]]) -> Optional[Project]:
        """
        Update a project but first verify it belongs to the specified owner.
        Also sets context_status to PENDING if repository_url is added or changed.
        """
        db_obj = self.get_by_id_for_owner(project_id=project_id, owner_id=owner_id)
        if not db_obj:
            return None

        old_repo_url = db_obj.repository_url
        old_status = db_obj.context_status # Store old status for logging

        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        repo_url_changed = "repository_url" in update_data and update_data["repository_url"] != old_repo_url
        adding_repo_url = old_repo_url is None and "repository_url" in update_data and update_data["repository_url"]

        needs_pending_status = repo_url_changed or adding_repo_url

        # Update fields from input data directly onto the object
        changes_made = False
        for field, value in update_data.items():
             if hasattr(db_obj, field) and getattr(db_obj, field) != value:
                 setattr(db_obj, field, value)
                 changes_made = True
                 print(f"[REPO DEBUG - update] Set {field} to {value}")

        # Set status if required
        # *** COMPARE ENUM VALUES ***
        if needs_pending_status and db_obj.context_status.value != ContextStatus.PENDING.value:
             db_obj.context_status = ContextStatus.PENDING
             changes_made = True
             print(f"[REPO DEBUG - update] Set context_status from {old_status.value if old_status else 'None'} to PENDING") # Log value
        # *** END ENUM VALUE COMPARISON ***

        # Only commit if changes were actually made
        if changes_made:
            try:
                 self.db.add(db_obj)
                 self.db.commit()
                 self.db.refresh(db_obj)
                 print(f"[REPO DEBUG - update] Commit successful. Refreshed status: {db_obj.context_status.value if db_obj.context_status else 'None'}") # Log value
            except Exception as e:
                 print(f"[REPO DEBUG - update] Commit/Refresh Error: {e}")
                 self.db.rollback()
                 raise e
        else:
             print("[REPO DEBUG - update] No actual changes detected, skipping commit.")

        return db_obj
    
    def remove_with_owner_check(self, *, project_id: str, owner_id: str) -> Optional[Project]:
        """
        Delete a project but first verify it belongs to the specified owner.
        Returns the deleted project object for reference before deletion.
        """
        # First get the project and check ownership
        db_obj = self.get_by_id_for_owner(project_id=project_id, owner_id=owner_id)
        if not db_obj:
            return None
        
        # Store project for return
        deleted_project = db_obj
        
        # Delete the project
        self.db.delete(db_obj)
        self.db.commit()
        
        return deleted_project

    # --- Admin Statistics Methods ---
    def count(self) -> int:
        """Count total number of projects."""
        return self.db.query(self.model).count()

    def count_by_status(self) -> Dict[str, int]:
        """Count projects by context status."""
        result = {}
        for status in ContextStatus:
            count = self.db.query(self.model).filter(
                self.model.context_status == status
            ).count()
            result[status.name] = count
        return result