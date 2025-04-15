# miktos_backend/repositories/base_repository.py

from sqlalchemy.orm import Session
from typing import Generic, TypeVar, Type, List, Optional, Dict, Any, Union
from pydantic import BaseModel

# Generic type for SQLAlchemy models
ModelType = TypeVar("ModelType")
# Generic type for Pydantic schemas
SchemaType = TypeVar("SchemaType", bound=BaseModel)

class BaseRepository(Generic[ModelType, SchemaType]):
    """Base class for all repositories."""
    
    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db = db
    
    def get(self, id: int) -> Optional[ModelType]:
        """Get an item by ID."""
        return self.db.query(self.model).filter(self.model.id == id).first()
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Get all items with pagination."""
        return self.db.query(self.model).offset(skip).limit(limit).all()
    
    def create(self, obj_in: Union[SchemaType, Dict[str, Any]]) -> ModelType:
        """Create a new item."""
        if isinstance(obj_in, dict):
            obj_data = obj_in
        else:
            obj_data = obj_in.dict(exclude_unset=True)
        
        db_obj = self.model(**obj_data)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def update(self, db_obj: ModelType, obj_in: Union[SchemaType, Dict[str, Any]]) -> ModelType:
        """Update an existing item."""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def delete(self, id: int) -> bool:
        """Delete an item by ID."""
        obj = self.db.query(self.model).get(id)
        if not obj:
            return False
        self.db.delete(obj)
        self.db.commit()
        return True