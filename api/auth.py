# miktos_backend/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Annotated, Optional

# Import repository/models/schemas etc.
from repositories.user_repository import UserRepository
from models.database_models import User
from schemas.user import UserCreate, UserRead
from schemas.token import Token, TokenData

# Import utils/config
from datetime import datetime, timedelta
from jose import JWTError, jwt
from config.settings import settings
from config.database import get_db
import security # Assuming security.py is at the root or correctly importable

router = APIRouter(
    tags=["Authentication"] # Prefix is applied in main.py
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token") # Path relative to API root

# --- Dependency to get current user ---
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[security.ALGORITHM])
        user_identifier: str = payload.get("sub") # Expecting user ID (as string) in 'sub'
        if user_identifier is None:
            print("[AUTH DEBUG] JWT decode error: 'sub' claim missing") # Debug
            raise credentials_exception

        user_id = user_identifier # Use the ID directly
        print(f"[AUTH DEBUG] Extracted user_id from token: {user_id}") # Debug

        user_repo = UserRepository(db)

        # --- FIX: Call the specific get_by_id method from UserRepository ---
        print(f"[AUTH DEBUG] Calling user_repo.get_by_id with user_id={user_id}") # Debug
        user = user_repo.get_by_id(user_id=user_id) # Use the specific method
        print(f"[AUTH DEBUG] Result of get_by_id: {'User found' if user else 'User not found'}") # Debug
        # --- END FIX ---

    except JWTError as e:
        print(f"[AUTH DEBUG] JWT decode error: {e}") # Debug
        raise credentials_exception
    except Exception as e:
        # Log unexpected errors during user lookup
        print(f"[AUTH ERROR] Error fetching user during token validation: {e}") # Debug
        # Optionally log the full traceback here
        # import traceback
        # traceback.print_exc()
        raise credentials_exception # Re-raise as unauthorized for security

    if user is None:
        print(f"[AUTH DEBUG] User not found in DB for id: {user_id}") # Debug
        raise credentials_exception

    # Check for active status if applicable
    if hasattr(user, 'is_active') and not user.is_active:
         print(f"[AUTH DEBUG] Authentication failed: User {user_id} is inactive.") # Debug
         raise HTTPException(status_code=400, detail="Inactive user")

    print(f"[AUTH DEBUG] get_current_user returning user: {user.id}") # Debug
    return user

# --- Login endpoint (Should be correct now) ---
@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db)
):
    # ... (Keep the previous corrected version of this function) ...
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

# --- Register new user (Should be correct now) ---
@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    # ... (Keep the previous corrected version of this function) ...
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

# --- Get current user info (Should be correct now) ---
@router.get("/users/me", response_model=UserRead)
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    print(f"Endpoint read_users_me called for user: {current_user.id}")
    return current_user