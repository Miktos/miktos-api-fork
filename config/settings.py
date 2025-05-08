# miktos_backend/config/settings.py
import os
from typing import Dict, Optional, Any, List
from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings

# Load environment variables from .env file
load_dotenv()

class LoggingSettings(BaseModel):
    """Configuration for logging."""
    LEVEL: str = Field(default="INFO", description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string"
    )


class DatabaseSettings(BaseModel):
    """Configuration for database connections."""
    URL: str = Field(
        default="sqlite:///./miktos_local.db",
        description="Database connection string"
    )
    POOL_SIZE: int = Field(default=5, description="Connection pool size")
    MAX_OVERFLOW: int = Field(default=10, description="Maximum overflow connections")
    ECHO: bool = Field(default=False, description="Echo SQL commands (for debugging)")


class AuthSettings(BaseModel):
    """Configuration for authentication."""
    JWT_SECRET: str = Field(
        default="dev_secret_key_change_in_production", 
        description="Secret key for JWT token signing"
    )
    TOKEN_EXPIRY_DAYS: int = Field(default=30, description="JWT token expiry in days")
    ALGORITHM: str = Field(default="HS256", description="JWT signing algorithm")

    @validator("JWT_SECRET")
    def jwt_secret_must_be_secure(cls, v: str) -> str:
        if v == "dev_secret_key_change_in_production" and os.getenv("ENVIRONMENT", "").lower() == "production":
            raise ValueError("JWT_SECRET must be changed in production environment")
        return v


class AIProviderSettings(BaseModel):
    """Configuration for AI provider APIs."""
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
    ANTHROPIC_API_KEY: str = Field(default="", description="Anthropic API key")
    GOOGLE_API_KEY: str = Field(default="", description="Google API key")
    
    DEFAULT_MODEL: str = Field(
        default="openai/gpt-4o",
        description="Default model to use when none is specified"
    )
    DEFAULT_TEMPERATURE: float = Field(
        default=0.7,
        description="Default temperature parameter for model generation",
        ge=0.0,
        le=1.0
    )
    DEFAULT_MAX_TOKENS: int = Field(
        default=1000,
        description="Default maximum tokens for model generation",
        ge=1
    )


class CORSSettings(BaseModel):
    """Configuration for CORS (Cross-Origin Resource Sharing)."""
    ALLOW_ORIGINS: List[str] = Field(
        default=["*"],
        description="List of allowed origins (use ['*'] for development only)"
    )
    ALLOW_METHODS: List[str] = Field(
        default=["*"],
        description="List of allowed HTTP methods"
    )
    ALLOW_HEADERS: List[str] = Field(
        default=["*"],
        description="List of allowed HTTP headers"
    )
    
    @validator("ALLOW_ORIGINS")
    def validate_origins_in_production(cls, v: List[str]) -> List[str]:
        if "*" in v and os.getenv("ENVIRONMENT", "").lower() == "production":
            print("WARNING: CORS is configured to allow all origins ('*') in a production environment.")
        return v


class CacheSettings(BaseModel):
    """Configuration for caching."""
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    RESPONSE_CACHE_ENABLED: bool = Field(
        default=True, 
        description="Enable response caching to reduce API costs and latency"
    )
    DEFAULT_TTL: int = Field(
        default=3600, 
        description="Default cache TTL in seconds"
    )


class Settings(BaseSettings):
    """Main settings class that combines all configuration sections."""
    # Application settings
    APP_NAME: str = Field(default="Miktos AI Orchestration Platform", description="Application name")
    VERSION: str = Field(default="0.2.0", description="API version")
    ENVIRONMENT: str = Field(default="development", description="Environment (development, testing, production)")
    DEBUG: bool = Field(default=False, description="Debug mode")
    PORT: int = Field(default=8000, description="Server port")
    
    # Direct access to API keys for backwards compatibility
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None)
    GOOGLE_API_KEY: Optional[str] = Field(default=None)
    DATABASE_URL: Optional[str] = Field(default=None)
    JWT_SECRET: Optional[str] = Field(default=None)
    TOKEN_EXPIRY_DAYS: Optional[int] = Field(default=None)
    LOG_LEVEL: Optional[str] = Field(default=None)
    REDIS_URL: Optional[str] = Field(default=None)
    RESPONSE_CACHE_ENABLED: Optional[bool] = Field(default=None)
    DEFAULT_TTL: Optional[int] = Field(default=None)
    
    # Component settings
    LOGGING: LoggingSettings = Field(default_factory=LoggingSettings)
    DATABASE: DatabaseSettings = Field(default_factory=DatabaseSettings)
    AUTH: AuthSettings = Field(default_factory=AuthSettings)
    AI_PROVIDERS: AIProviderSettings = Field(default_factory=AIProviderSettings)
    CORS: CORSSettings = Field(default_factory=CORSSettings)
    CACHE: CacheSettings = Field(default_factory=CacheSettings)
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"  # This allows nested settings like LOGGING__LEVEL=DEBUG in .env
        case_sensitive = False  # Allow case-insensitive environment variable matching

    def is_development(self) -> bool:
        """Check if the environment is development."""
        return self.ENVIRONMENT.lower() == "development"
        
    def is_production(self) -> bool:
        """Check if the environment is production."""
        return self.ENVIRONMENT.lower() == "production"
        
    def is_testing(self) -> bool:
        """Check if the environment is testing."""
        return self.ENVIRONMENT.lower() == "testing"

    def model_post_init(self, __context):
        """Process settings after initialization to handle legacy environment variables."""
        # Update nested settings with direct environment variables if provided
        if self.OPENAI_API_KEY:
            self.AI_PROVIDERS.OPENAI_API_KEY = self.OPENAI_API_KEY
        if self.ANTHROPIC_API_KEY:
            self.AI_PROVIDERS.ANTHROPIC_API_KEY = self.ANTHROPIC_API_KEY
        if self.GOOGLE_API_KEY:
            self.AI_PROVIDERS.GOOGLE_API_KEY = self.GOOGLE_API_KEY
        if self.DATABASE_URL:
            self.DATABASE.URL = self.DATABASE_URL
        if self.JWT_SECRET:
            self.AUTH.JWT_SECRET = self.JWT_SECRET
        if self.TOKEN_EXPIRY_DAYS:
            self.AUTH.TOKEN_EXPIRY_DAYS = self.TOKEN_EXPIRY_DAYS
        if self.LOG_LEVEL:
            self.LOGGING.LEVEL = self.LOG_LEVEL
        if self.REDIS_URL:
            self.CACHE.REDIS_URL = self.REDIS_URL
        if self.RESPONSE_CACHE_ENABLED is not None:
            self.CACHE.RESPONSE_CACHE_ENABLED = self.RESPONSE_CACHE_ENABLED
        if self.DEFAULT_TTL:
            self.CACHE.DEFAULT_TTL = self.DEFAULT_TTL


# Create settings instance
settings = Settings(
    # Load from environment variables
    APP_NAME=os.getenv("APP_NAME", "Miktos AI Orchestration Platform"),
    VERSION=os.getenv("VERSION", "0.2.0"),
    ENVIRONMENT=os.getenv("ENVIRONMENT", "development"),
    DEBUG=os.getenv("DEBUG", "False").lower() == "true",
    PORT=int(os.getenv("PORT", "8000")),
    
    # Database settings
    DATABASE=DatabaseSettings(
        URL=os.getenv("DATABASE_URL", "sqlite:///./miktos_local.db"),
        POOL_SIZE=int(os.getenv("DB_POOL_SIZE", "5")),
        MAX_OVERFLOW=int(os.getenv("DB_MAX_OVERFLOW", "10")),
        ECHO=os.getenv("DB_ECHO", "False").lower() == "true",
    ),
    
    # Auth settings
    AUTH=AuthSettings(
        JWT_SECRET=os.getenv("JWT_SECRET", "dev_secret_key_change_in_production"),
        TOKEN_EXPIRY_DAYS=int(os.getenv("TOKEN_EXPIRY_DAYS", "30")),
        ALGORITHM=os.getenv("JWT_ALGORITHM", "HS256"),
    ),
    
    # AI Provider settings
    AI_PROVIDERS=AIProviderSettings(
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),
        ANTHROPIC_API_KEY=os.getenv("ANTHROPIC_API_KEY", ""),
        GOOGLE_API_KEY=os.getenv("GOOGLE_API_KEY", ""),
        DEFAULT_MODEL=os.getenv("DEFAULT_MODEL", "openai/gpt-4o"),
        DEFAULT_TEMPERATURE=float(os.getenv("DEFAULT_TEMPERATURE", "0.7")),
        DEFAULT_MAX_TOKENS=int(os.getenv("DEFAULT_MAX_TOKENS", "1000")),
    ),
    
    # CORS settings
    CORS=CORSSettings(
        ALLOW_ORIGINS=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
        ALLOW_METHODS=os.getenv("CORS_ALLOW_METHODS", "*").split(","),
        ALLOW_HEADERS=os.getenv("CORS_ALLOW_HEADERS", "*").split(","),
    ),
    
    # Logging settings
    LOGGING=LoggingSettings(
        LEVEL=os.getenv("LOG_LEVEL", "INFO"),
        FORMAT=os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
    ),
    
    # Cache settings
    CACHE=CacheSettings(
        REDIS_URL=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        RESPONSE_CACHE_ENABLED=os.getenv("RESPONSE_CACHE_ENABLED", "True").lower() == "true",
        DEFAULT_TTL=int(os.getenv("DEFAULT_TTL", "3600")),
    ),
)

# For backwards compatibility - expose these at the module level
# This allows existing code to still use settings.OPENAI_API_KEY etc.
OPENAI_API_KEY = settings.AI_PROVIDERS.OPENAI_API_KEY 
ANTHROPIC_API_KEY = settings.AI_PROVIDERS.ANTHROPIC_API_KEY
GOOGLE_API_KEY = settings.AI_PROVIDERS.GOOGLE_API_KEY
DATABASE_URL = settings.DATABASE.URL
JWT_SECRET = settings.AUTH.JWT_SECRET
TOKEN_EXPIRY_DAYS = settings.AUTH.TOKEN_EXPIRY_DAYS
DEBUG = settings.DEBUG
PORT = settings.PORT
LOG_LEVEL = settings.LOGGING.LEVEL