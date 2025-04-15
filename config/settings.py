# miktos_backend/config/settings.py

import os
from dotenv import load_dotenv
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# This makes sure the .env file is found correctly relative to this settings file.
# It goes up two levels from settings.py (config -> miktos_backend -> miktos root)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / '.env'

# Load the environment variables from the .env file
load_dotenv(dotenv_path=ENV_PATH)

# --- API Key Configuration ---
# Retrieve API keys from environment variables.
# os.getenv('VARIABLE_NAME') returns None if the variable is not set,
# which is safer than os.environ['VARIABLE_NAME'] which raises an error.

OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY: str | None = os.getenv("GOOGLE_API_KEY")

# --- Optional: Add simple validation ---
# You can add checks here to ensure keys are loaded, although
# the individual clients using them should also handle missing keys.
# Example (optional):
# if not OPENAI_API_KEY:
#     print("Warning: OPENAI_API_KEY environment variable not set.")
# if not ANTHROPIC_API_KEY:
#     print("Warning: ANTHROPIC_API_KEY environment variable not set.")
# if not GOOGLE_API_KEY:
#     print("Warning: GOOGLE_API_KEY environment variable not set.")

# --- Other Configuration (Placeholders for later) ---
# Example: Default model, Database URL, etc.
# DEFAULT_MODEL = "openai/gpt-4o"
# DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./miktos_local.db") # Default to local SQLite

print("Configuration loaded.") # Simple confirmation message when this module is imported