# utils/password_utils.py
from passlib.context import CryptContext

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    print(f"--- [Verify Password DEBUG] Verifying plain='{plain_password}' against hash='{hashed_password}' ---")
    try:
        result = pwd_context.verify(plain_password, hashed_password)
        print(f"--- [Verify Password DEBUG] Password verification result: {result} ---")
        return result
    except Exception as e:
        print(f"--- [Verify Password DEBUG] ERROR during password verification: {e} ---")
        return False

def get_password_hash(password: str) -> str:
    """Hashes a plain password."""
    return pwd_context.hash(password)