# schemas/__init__.py

# Import User related schemas
from .user import (
    UserBase,
    UserCreate,
    UserRead,
    UserUpdate
)

# Import Project related schemas (Corrected import source)
from .project import (
    ProjectCreate,
    ProjectRead,
    ProjectUpdate
    # Add ProjectBase here if it's defined in project.py and needed externally
    # ProjectBase # Uncomment if needed
)

# Import Message related schemas (Simplified import)
from .message import (
    MessageCreate,
    MessageRead,
    MessageUpdate,
    MessageRole # Assuming MessageRole is defined in message.py
    # Add MessageBase here if defined and needed
    # MessageBase # Uncomment if needed
)

# Import Token related schemas
from .token import Token, TokenData

# --- REMOVED TRY/EXCEPT BLOCKS ---
# The previous complex try/except logic is no longer needed
# as we assume message.py and token.py are the definitive sources.
# If these files *might* be missing in some configurations,
# the try/except could be added back, but it's usually cleaner
# to ensure the files exist.