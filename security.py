# miktos_backend/security.py

from datetime import datetime, timedelta, timezone # Ensure timezone is imported
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from config.settings import settings # Import your settings

# --- Password Hashing ---
# Use CryptContext for handling password hashing and verification
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashes a plain password."""
    return pwd_context.hash(password)

# --- JWT Token Handling ---
ALGORITHM = "HS256"
# Use ACCESS_TOKEN_EXPIRE_MINUTES from settings if defined, otherwise default
ACCESS_TOKEN_EXPIRE_MINUTES = getattr(settings, 'ACCESS_TOKEN_EXPIRE_MINUTES', 30) # Default to 30 minutes

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

# Note: The get_current_user dependency logic is typically placed within the
#       auth router file (api/auth.py) or sometimes in a dedicated dependencies.py,
#       as it often requires access to database sessions and user repositories.
#       It's less common to put the full dependency function here in security.py,
#       though helper functions for decoding might live here.