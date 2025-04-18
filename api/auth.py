# miktos_backend/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Annotated, Optional # Use Annotated for newer Python versions if needed

# Import the specific CLASS and base repository if needed for type hints elsewhere
from repositories.user_repository import UserRepository
from models.database_models import User # Import your User model if needed for type hints

from schemas.user import UserCreate, UserRead
from schemas.token import Token, TokenData # Import your token schemas

from datetime import datetime, timedelta # Keep datetime imports
from jose import JWTError, jwt # Keep jose imports
from config.settings import settings # Keep settings import
from config.database import get_db # Keep get_db import

router = APIRouter(
    prefix="/api/v1/auth", # Keep the prefix
    tags=["Authentication"]
)

# OAuth2 scheme - Use the correct tokenUrl relative to the API root
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# --- Helper Functions (Keep as they are) ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.TOKEN_EXPIRY_DAYS)
    to_encode.update({"exp": expire})
    # Ensure settings.JWT_SECRET is loaded correctly
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")
    return encoded_jwt

# --- Dependency to get current user (Revised) ---
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        # Use the correct subject claim key ('sub') used during token creation
        user_identifier: str = payload.get("sub")
        if user_identifier is None:
            raise credentials_exception
        # Assuming 'sub' contains the user ID directly based on your login logic
        # If 'sub' contains email, you'd need TokenData(email=user_identifier) and get by email
        token_data = TokenData(user_id=user_identifier) # Make sure TokenData schema expects user_id
    except JWTError:
        raise credentials_exception

    # --- FIX: Instantiate Repository and use its method ---
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id=token_data.user_id) # Use get_by_id method
    # --- END FIX ---

    if user is None:
        raise credentials_exception
    # Check if user is active (if you have an is_active field)
    # if not user.is_active:
    #     raise HTTPException(status_code=400, detail="Inactive user")
    return user # Return the user object fetched from DB

# --- Login endpoint (Revised) ---
@router.post("/token", response_model=Token) # Endpoint path relative to prefix
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), # Use OAuth2PasswordRequestForm directly
    db: Session = Depends(get_db)
):
    # --- FIX: Instantiate Repository and use its authenticate method ---
    user_repo = UserRepository(db)
    # Use the authenticate method which handles getting user and verifying password
    user = user_repo.authenticate(email=form_data.username, password=form_data.password)
    # --- END FIX ---

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token with user ID as the subject
    # Ensure user object has an 'id' attribute
    access_token = create_access_token(data={"sub": str(user.id)}) # Convert ID to string if needed
    return {"access_token": access_token, "token_type": "bearer"}

# --- Register new user (Revised) ---
@router.post("/register", response_model=UserRead) # Endpoint path relative to prefix
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    # --- FIX: Instantiate Repository and use its methods ---
    user_repo = UserRepository(db)
    db_user = user_repo.get_by_email(email=user.email) # Use instance method
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Use the create method from the instance
    created_user = user_repo.create(obj_in=user)
    # --- END FIX ---
    return created_user # Return the newly created user object

# --- Get current user info (Revised - uses revised dependency) ---
@router.get("/me", response_model=UserRead) # Endpoint path relative to prefix
async def read_users_me(current_user: User = Depends(get_current_user)): # Type hint with your User model
    # The get_current_user dependency already fetches and returns the user object
    return current_user