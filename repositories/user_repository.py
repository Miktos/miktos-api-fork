# miktos_backend/repositories/user_repository.py

from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, Union
from passlib.context import CryptContext

from models.database import User
from repositories.base_repository import BaseRepository
from schemas.user import UserCreate, UserUpdate

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserRepository(BaseRepository[User, UserCreate]):
    def __init__(self, db: Session):
        super().__init__(User, db)
    
    def get_by_username(self, username: str) -> Optional[User]:
        """Get a user by username."""
        return self.db.query(User).filter(User.username == username).first()
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get a user by email."""
        return self.db.query(User).filter(User.email == email).first()
    
    def create(self, obj_in: UserCreate) -> User:
        """Create a new user with password hashing."""
        db_obj = User(
            username=obj_in.username,
            email=obj_in.email,
            password_hash=self._hash_password(obj_in.password),
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
                update_data["password_hash"] = self._hash_password(update_data.pop("password"))
        else:
            update_data = obj_in.dict(exclude_unset=True)
            if update_data.get("password"):
                update_data["password_hash"] = self._hash_password(update_data.pop("password"))
        
        return super().update(db_obj, update_data)
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user by username and password."""
        user = self.get_by_username(username)
        if not user or not self.verify_password(password, user.password_hash):
            return None
        return user
    
    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash a password for storing."""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a stored password against a provided password."""
        return pwd_context.verify(plain_password, hashed_password)