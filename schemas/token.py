# schemas/token.py
from pydantic import BaseModel
from typing import Optional

class Token(BaseModel):
    """Schema for the token response sent to the client after authentication."""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """Schema for the data stored in the token."""
    user_id: Optional[str] = None