# miktos_backend/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from config.settings import settings
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from config.database import get_db
from models.database_models import User
import schemas

# Import from utils instead of defining locally
from utils.password_utils import verify_password, get_password_hash

# --- JWT Token Handling ---
ALGORITHM = "HS256"
# Use ACCESS_TOKEN_EXPIRE_MINUTES from settings if defined, otherwise default
ACCESS_TOKEN_EXPIRE_MINUTES = getattr(settings, 'ACCESS_TOKEN_EXPIRE_MINUTES', 30) # Default to 30 minutes

# Create OAuth2 scheme for token validation
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        # Ensure expire time is timezone-aware (UTC)
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    # Ensure settings.JWT_SECRET is loaded correctly and is a string
    if not settings.JWT_SECRET or not isinstance(settings.JWT_SECRET, str):
        raise ValueError("JWT_SECRET is not configured correctly in settings.")

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

# Direct database query version of get_current_user to avoid circular imports
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    request: Optional[object] = None,  # This will be populated by FastAPI with the request object
) -> User:
    """
    Dependency function to get the current authenticated user based on JWT token.
    Uses direct DB query to avoid circular imports.
    
    Also stores user_id in request.state for use by activity logger middleware.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode the JWT token
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")  # The subject should be the user ID
        if user_id is None:
            raise credentials_exception
        
        # Create token data from the payload
        token_data = schemas.TokenData(user_id=user_id)
    except JWTError:
        # If token is invalid, raise exception
        raise credentials_exception
    
    # Get the user from the database directly without using UserRepository
    user = db.query(User).filter(User.id == token_data.user_id).first()
    
    if user is None:
        # If user doesn't exist, raise exception
        raise credentials_exception
    
    # Store user_id in request state if request is provided
    # This will be used by the activity logger middleware
    if request and hasattr(request, 'state'):
        request.state.user_id = str(user.id)
        
    # User is authenticated, return user object
    return user