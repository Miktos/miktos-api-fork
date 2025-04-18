# miktos_backend/repositories/user_repository.py

from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, Union
from passlib.context import CryptContext
import bcrypt # Using bcrypt directly

# Import the SQLAlchemy model
from models.database_models import User
# Import the BaseRepository
from repositories.base_repository import BaseRepository
# Import the necessary Pydantic schemas
from schemas.user import UserCreate, UserUpdate # UserUpdate is needed here

# Password hashing context (using passlib is generally recommended over direct bcrypt)
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserRepository(BaseRepository[User, UserCreate, UserUpdate]): # <-- Add UserUpdate here
    def __init__(self, db: Session):
        """
        User specific repository providing user-related CRUD operations.

        **Parameters**
        * `db`: A SQLAlchemy database session dependency
        """
        # Initialize the BaseRepository with the User model
        super().__init__(model=User, db=db)

    # --- User Specific Getters (Consider if BaseRepository.get covers ID lookup) ---

    # get_by_id can often be handled by base_repository.get(item_id=user_id)
    # If your PK isn't 'id' or you need specific logic, keep it.
    def get_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        # Example using base method if PK is 'id'
        # return super().get(item_id=user_id)
        # Or keep specific filter if needed
        return self.db.query(self.model).filter(self.model.id == user_id).first()

    def get_by_username(self, username: str) -> Optional[User]:
        """Get a user by username."""
        return self.db.query(self.model).filter(self.model.username == username).first()

    def get_by_email(self, email: str) -> Optional[User]:
        """Get a user by email."""
        return self.db.query(self.model).filter(self.model.email == email).first()

    # --- Override Base Methods for User Specific Logic ---

    def create(self, *, obj_in: UserCreate) -> User:
        """
        Create a new user, hashing the password before saving.
        Overrides BaseRepository.create().
        """
        # Hash the password using the chosen method
        hashed_password = self._hash_password(obj_in.password)

        # Create the SQLAlchemy model instance
        db_obj = self.model( # Use self.model inherited from BaseRepository
            username=obj_in.username,
            email=obj_in.email,
            hashed_password=hashed_password,
            # is_active default is handled by schema or model? Ensure consistency.
            is_active=obj_in.is_active if obj_in.is_active is not None else True
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, *, db_obj: User, obj_in: Union[UserUpdate, Dict[str, Any]]) -> User:
        """
        Update user data, hashing the password if provided.
        Overrides BaseRepository.update().
        """
        # Convert Pydantic schema to dict, excluding unset fields
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            # Use model_dump for Pydantic V2+
            update_data = obj_in.model_dump(exclude_unset=True)

        # If password is being updated, hash it before setting
        if "password" in update_data and update_data["password"]:
            hashed_password = self._hash_password(update_data["password"])
            update_data["hashed_password"] = hashed_password
            del update_data["password"] # Don't store plain password field

        # Use the BaseRepository's update method to apply changes
        return super().update(db_obj=db_obj, obj_in=update_data)

    # --- User Authentication Methods ---

    def authenticate(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user by email and password."""
        user = self.get_by_email(email)
        if not user:
            return None # User not found
        if not self.verify_password(password, user.hashed_password):
            return None # Incorrect password
        return user # Authentication successful

    # --- Password Hashing Utilities ---
    # Note: Using passlib's CryptContext is generally preferred as it handles salt generation
    # and future algorithm upgrades more easily than direct bcrypt usage.

    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash a password for storing using bcrypt."""
        # Ensure password is bytes, generate salt, hash, then decode back to string for DB
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a stored password against a provided password using bcrypt."""
        # Ensure both are bytes for bcrypt comparison
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))