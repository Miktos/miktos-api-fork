# miktos_backend/config/settings.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    # API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./miktos_local.db")
    
    # Authentication
    JWT_SECRET = os.getenv("JWT_SECRET", "dev_secret_key_change_in_production")
    TOKEN_EXPIRY_DAYS = int(os.getenv("TOKEN_EXPIRY_DAYS", "30"))
    
    # Application settings
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    PORT = int(os.getenv("PORT", "8000"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Create settings instance
settings = Settings()