# miktos_backend/repositories/user_repository.py

from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, Union
from passlib.context import CryptContext
import bcrypt

from models.database_models import User
from repositories.base_repository import BaseRepository
from schemas.user import UserCreate, UserUpdate

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserRepository(BaseRepository[User, UserCreate]):
    def __init__(self, db: Session):
        super().__init__(User, db)
    
    def get_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_by_username(self, username: str) -> Optional[User]:
        """Get a user by username."""
        return self.db.query(User).filter(User.username == username).first()
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get a user by email."""
        return self.db.query(User).filter(User.email == email).first()
    
    def create(self, obj_in: UserCreate) -> User:
        """Create a new user with password hashing."""
        hashed_password = self._hash_password(obj_in.password)
        
        db_obj = User(
            username=obj_in.username,
            email=obj_in.email,
            hashed_password=hashed_password,
            is_active=True
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def update(self, db_obj: User, obj_in: Union[UserUpdate, Dict[str, Any]]) -> User:
        """Update user data, hashing the password if provided."""
        if isinstance(obj_in, dict):
            update_data = obj_in
            if "password" in update_data:
                update_data["hashed_password"] = self._hash_password(update_data.pop("password"))
        else:
            update_data = obj_in.dict(exclude_unset=True)
            if update_data.get("password"):
                update_data["hashed_password"] = self._hash_password(update_data.pop("password"))
        
        return super().update(db_obj, update_data)
    
    def authenticate(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user by email and password."""
        user = self.get_by_email(email)
        if not user or not self.verify_password(password, user.hashed_password):
            return None
        return user
    
    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash a password for storing."""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a stored password against a provided password."""
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())