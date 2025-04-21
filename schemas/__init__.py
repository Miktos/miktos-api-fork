# schemas/__init__.py

# Import User related schemas
from .user import (
    UserBase,
    UserCreate,
    UserRead,
    UserUpdate
)

# Import Project related schemas
from .user import (
    ProjectBase,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate
)

# Import Message related schemas
# NOTE: You defined MessageRole in schemas/message.py previously.
# It's better practice to keep schemas for different concepts in separate files.
# If schemas/message.py exists and defines MessageRole, import it from there.
# Otherwise, define MessageRole enum here or preferably in schemas/message.py

# Assuming schemas/message.py defines MessageRole, MessageCreate, MessageRead, MessageUpdate:
try:
    from .message import MessageCreate, MessageRead, MessageUpdate, MessageRole
except ImportError:
    # Fallback if message.py doesn't exist or is structured differently
    # Import the schemas defined within user.py (less ideal structure)
    print("Warning: Could not import from schemas.message.py, importing Message schemas from schemas.user.py")
    from .user import (
         MessageBase, # Import base if needed elsewhere
         MessageCreate as MessageCreateFromUserFile, # Avoid name clash if MessageCreate exists in message.py
         MessageRead as MessageReadFromUserFile,
         MessageUpdate as MessageUpdateFromUserFile
    )
    # Define MessageRole here if it's not in message.py
    import enum
    class MessageRole(str, enum.Enum):
         USER = "user"
         ASSISTANT = "assistant"

# Import Token related schemas (assuming token.py exists)
try:
    from .token import Token, TokenData
except ImportError:
    print("Warning: Could not import from schemas.token.py")
    # Define fallback or handle missing file if necessary
    Token = None
    TokenData = None