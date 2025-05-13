# miktos_backend/repositories/user_repository.py
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, Union

# Import the SQLAlchemy model
from models.database_models import User
# Import the BaseRepository
from repositories.base_repository import BaseRepository
# Import the necessary Pydantic schemas
from schemas.user import UserCreate, UserUpdate

# Import from utils rather than from security
from utils.password_utils import verify_password, get_password_hash

class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    def __init__(self, db: Session):
        """
        User specific repository providing user-related CRUD operations.
        """
        # Initialize the BaseRepository with the User model
        super().__init__(model=User, db=db)

    # --- User Specific Getters ---
    def get_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
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
        hashed_password = get_password_hash(obj_in.password)

        # Create the SQLAlchemy model instance
        db_obj = self.model(
            username=obj_in.username,
            email=obj_in.email,
            hashed_password=hashed_password,
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
            hashed_password = get_password_hash(update_data["password"])
            update_data["hashed_password"] = hashed_password
            del update_data["password"]  # Don't store plain password field

        # Use the BaseRepository's update method to apply changes
        return super().update(db_obj=db_obj, obj_in=update_data)

    # --- User Authentication Methods ---
    def authenticate(self, identifier: str, password: str) -> Optional[User]:
        """
        Authenticate a user by identifier (checking email first, then username) and password.
        """
        print(f"\n--- [Authenticate Method DEBUG] Attempting auth for identifier: '{identifier}' (Session ID: {id(self.db)}) ---")
        user: Optional[User] = None  # Initialize user

        # Try finding user by email first
        print(f"--- [Authenticate Method DEBUG] Checking by email: '{identifier}' ---")
        user = self.get_by_email(identifier)
        if user:
            print(f"--- [Authenticate Method DEBUG] Found user by email: ID={user.id}, Email={user.email}, HashedPwd={user.hashed_password}")
        else:
            print(f"--- [Authenticate Method DEBUG] Not found by email.")
            # If not found by email, try finding by username (if username exists on model)
            if hasattr(self.model, 'username'):
                print(f"--- [Authenticate Method DEBUG] Checking by username: '{identifier}' ---")
                user = self.get_by_username(identifier)
                if user:
                    print(f"--- [Authenticate Method DEBUG] Found user by username: ID={user.id}, Username={user.username}, HashedPwd={user.hashed_password}")
                else:
                    print(f"--- [Authenticate Method DEBUG] Not found by username either.")

        # If user not found by either method
        if not user:
            print(f"--- [Authenticate Method DEBUG] FINAL: User not found for identifier '{identifier}'. Returning None. ---")
            return None  # User not found

        # If user found, verify password
        print(f"--- [Authenticate Method DEBUG] User found (ID: {user.id}). Verifying password...")
        is_valid_password = verify_password(password, user.hashed_password)
        if not is_valid_password:
            print(f"--- [Authenticate Method DEBUG] Password verification FAILED for user {user.id}.")
            return None  # Incorrect password

        print(f"--- [Authenticate Method DEBUG] Password verification PASSED for user {user.id}. Returning user object. ---")
        return user  # Authentication successful

    # --- Admin Statistics Methods ---
    def count(self) -> int:
        """Count total number of users."""
        return self.db.query(self.model).count()

    def count_active(self) -> int:
        """Count number of active users."""
        return self.db.query(self.model).filter(self.model.is_active == True).count()