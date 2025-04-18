# schemas/token.py
from pydantic import BaseModel
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    # Based on your get_current_user logic which extracts 'sub' as user_id
    user_id: Optional[str] = None
