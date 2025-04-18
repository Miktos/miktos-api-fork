# miktos_backend/repositories/base_repository.py
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.orm import Session as SQLAlchemySession

# Import Base as a type
from models.database_models import Base

# Define TypeVars for Generics
ModelType = TypeVar("ModelType", bound=Base)  # type: ignore    
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]): # Added UpdateSchemaType here too
    # Define type hints for instance variables
    model: Type[ModelType]
    db: SQLAlchemySession # Use SQLAlchemySession type hint

    def __init__(self, model: Type[ModelType], db: SQLAlchemySession):
        """
        Base repository with default methods to Create, Read, Update, Delete (CRUD).

        **Parameters**
        * `model`: A SQLAlchemy model class (e.g., User, Project)
        * `db`: A SQLAlchemy database session dependency
        """
        self.model = model
        self.db = db

    def get(self, item_id: Any) -> Optional[ModelType]:
        """Get a record by its primary key ID."""
        # Use .get() for primary key lookup if your ID column is named 'id' and is the PK
        # return self.db.get(self.model, item_id) # Preferred way if PK is simple
        # Or use filter if PK name is different or composite
        return self.db.query(self.model).filter(self.model.id == item_id).first()

    def get_multi(self, *, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Get multiple records with pagination."""
        return self.db.query(self.model).offset(skip).limit(limit).all()

    def create(self, *, obj_in: CreateSchemaType) -> ModelType:
        """
        Create a new record in the database.
        Assumes the CreateSchemaType fields match the ModelType fields.
        Override in subclasses for specific logic (like password hashing).
        """
        # Use model_dump() for Pydantic V2+
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data) # Create model instance
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(
        self, *, db_obj: ModelType, obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """
        Update an existing database record.
        """
        # Encode the existing database object to a dictionary
        # Use jsonable_encoder only if necessary for complex nested objects,
        # otherwise accessing attributes directly might be simpler.
        obj_data = jsonable_encoder(db_obj) # Or just use db_obj.__dict__ if simple

        # Get update data from Pydantic schema or dict
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            # Use model_dump() for Pydantic V2+
            update_data = obj_in.model_dump(exclude_unset=True) # Exclude fields not provided

        # Iterate over fields in the existing object's data
        for field in obj_data:
            if field in update_data:
                # Update the attribute on the SQLAlchemy model instance
                setattr(db_obj, field, update_data[field])

        self.db.add(db_obj) # Add the updated object to the session
        self.db.commit()
        self.db.refresh(db_obj) # Refresh to get any DB-generated updates
        return db_obj

    def remove(self, *, item_id: Any) -> Optional[ModelType]:
        """
        Delete a record from the database by its primary key ID.
        """
        # Use db.get() if appropriate (see self.get method)
        # obj = self.db.get(self.model, item_id)
        # Or use filter
        obj = self.db.query(self.model).filter(self.model.id == item_id).first()

        if obj:
            self.db.delete(obj)
            self.db.commit()
            # Return the deleted object (transient state) or None if not found
            return obj
        return None