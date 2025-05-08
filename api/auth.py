# miktos_backend/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Annotated, Optional

# Import models and schemas
from models.database_models import User
from schemas.user import UserCreate, UserRead
from schemas.token import Token, TokenData

# Import repositories with modified imports
from repositories.user_repository import UserRepository

# Import utils/config
from datetime import datetime, timedelta
from jose import JWTError, jwt
from config.settings import settings
from config.database import get_db

# Import security functions
from utils.password_utils import verify_password, get_password_hash
import security  # Import other security functions

router = APIRouter(
    tags=["Authentication"]  # Prefix is applied in main.py
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")  # Path relative to API root

# Use the get_current_user from security.py to avoid duplication
get_current_user = security.get_current_user

# Admin check dependency
async def is_admin(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Dependency to check if the current user is an admin.
    Raises a 403 Forbidden exception if the user is not an admin.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Admin access required."
        )
    return current_user

# --- Login endpoint ---
@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db)
):
    print(f"Attempting login for identifier: {form_data.username}")
    user_repo = UserRepository(db)
    user = user_repo.authenticate(identifier=form_data.username, password=form_data.password)
    if not user:
        print(f"Authentication failed for: {form_data.username}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
    print(f"Authentication successful for user: {user.id}")
    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(data={"sub": str(user.id)}, expires_delta=access_token_expires)
    print(f"Generated token for user: {user.id}")
    return {"access_token": access_token, "token_type": "bearer"}

# --- Register new user ---
@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    print(f"Attempting registration for email: {user_in.email}")
    user_repo = UserRepository(db)
    db_user_email = user_repo.get_by_email(email=user_in.email)
    if db_user_email:
        print(f"Registration failed: Email {user_in.email} already exists.")
        raise HTTPException(status_code=400, detail="Email already registered")
    if hasattr(user_in, 'username') and user_in.username:
        db_user_username = user_repo.get_by_username(username=user_in.username)
        if db_user_username:
            print(f"Registration failed: Username {user_in.username} already exists.")
            raise HTTPException(status_code=400, detail="Username already registered")
    created_user = user_repo.create(obj_in=user_in)
    print(f"Successfully registered user: {created_user.id}")
    return created_user

# --- Get current user info ---
@router.get("/users/me", response_model=UserRead)
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    print(f"Endpoint read_users_me called for user: {current_user.id}")
    return current_user