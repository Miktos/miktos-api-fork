# miktos_backend/repositories/project_repository.py
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, Union

# Import the SQLAlchemy model
from models.database_models import Project
# Import the BaseRepository
from repositories.base_repository import BaseRepository
# Import the necessary Pydantic schemas
from schemas.user import ProjectCreate, ProjectUpdate # Ensure ProjectUpdate is imported

class ProjectRepository(BaseRepository[Project, ProjectCreate, ProjectUpdate]): # Added ProjectUpdate
    def __init__(self, db: Session):
        """
        Project specific repository providing project-related CRUD operations,
        often including owner checks.

        **Parameters**
        * `db`: A SQLAlchemy database session dependency
        """
        # Initialize the BaseRepository with the Project model
        super().__init__(model=Project, db=db)

    # --- Project Specific Getters (with owner check) ---

    def get_by_id_for_owner(self, *, project_id: str, owner_id: str) -> Optional[Project]:
        """
        Get a specific project by its ID, ensuring it belongs to the specified owner.
        Returns None if not found or owner mismatch.
        """
        # Use self.model inherited from BaseRepository
        return self.db.query(self.model)\
                 .filter(self.model.id == project_id, self.model.owner_id == owner_id)\
                 .first()

    def get_multi_by_owner(self, *, owner_id: str, skip: int = 0, limit: int = 100) -> List[Project]:
        """
        Get all projects for a specific user (owner).
        """
        # Renamed from get_user_projects for consistency
        # --- Corrected Indentation Start ---
        return ( # Optional: Wrap in parentheses for clarity with multi-line return
            self.db.query(self.model)
            .filter(self.model.owner_id == owner_id)
            .order_by(self.model.created_at.desc()) # Example: order by newest first
            .offset(skip) # Ensure this line has the same indent as .filter and .order_by
            .limit(limit) # Ensure this line has the same indent
            .all()        # Ensure this line has the same indent
        )
        # --- Corrected Indentation End ---

    # --- Override Base Methods or Add Specific Logic ---

    # BaseRepository.create might work if owner_id is part of ProjectCreate schema.
    # If not, this specific method is needed.
    def create_with_owner(self, *, obj_in: ProjectCreate, owner_id: str) -> Project:
        """
        Create a new project and assign ownership.
        """
        # Use model_dump for Pydantic V2+
        obj_in_data = obj_in.model_dump()
        # Create the SQLAlchemy model instance, adding the owner_id
        db_obj = self.model(**obj_in_data, owner_id=owner_id) # Use self.model
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    # Override update to include owner check before calling base update
    def update_with_owner_check(
        self, *, project_id: str, owner_id: str, obj_in: Union[ProjectUpdate, Dict[str, Any]]
    ) -> Optional[Project]:
        """
        Update a project after verifying ownership. Returns None if not found or owner mismatch.
        """
        # First, get the project ensuring the owner matches
        db_obj = self.get_by_id_for_owner(project_id=project_id, owner_id=owner_id)
        if not db_obj:
            return None # Project not found or doesn't belong to this owner

        # If found and owner matches, use the base update method
        # Note: The base update method might need refinement depending on its implementation
        return super().update(db_obj=db_obj, obj_in=obj_in)

    # Override remove to include owner check
    def remove_with_owner_check(self, *, project_id: str, owner_id: str) -> Optional[Project]:
        """
        Delete a project after verifying ownership. Returns the deleted project or None.
        """
        # --- Corrected Indentation Start ---
        # First, get the project ensuring the owner matches
        db_obj = self.get_by_id_for_owner(project_id=project_id, owner_id=owner_id)
        if not db_obj:
            return None # Project not found or doesn't belong to this owner

        # If found and owner matches, delete directly
        self.db.delete(db_obj)
        self.db.commit()
        return db_obj # Return the deleted object (now transient)
        # --- Corrected Indentation End ---