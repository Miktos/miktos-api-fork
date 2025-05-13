"""
Server configuration for Miktos backend.

This module provides a dedicated configuration class for server-related settings,
including host, port, workers, timeouts, and shutdown behavior.
"""
import os
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator

class ServerSettings(BaseModel):
    """Configuration for server behavior and resources."""
    
    # Basic server settings
    HOST: str = Field(
        default="127.0.0.1",
        description="Host address to bind the server to"
    )
    PORT: int = Field(
        default=8000,
        description="Port to run the server on"
    )
    WORKERS: int = Field(
        default=4,
        description="Number of worker processes (0 for CPU count)"
    )
    
    # Performance settings
    BACKLOG: int = Field(
        default=2048,
        description="Maximum number of pending connections"
    )
    TIMEOUT: int = Field(
        default=300,
        description="Worker timeout in seconds"
    )
    KEEPALIVE: int = Field(
        default=5,
        description="Keep-alive connection timeout in seconds"
    )

    # Graceful shutdown settings
    GRACEFUL_TIMEOUT: int = Field(
        default=30,
        description="Graceful shutdown timeout in seconds"
    )
    
    # SSL/TLS settings
    USE_SSL: bool = Field(
        default=False,
        description="Enable SSL/TLS"
    )
    SSL_CERT_FILE: Optional[str] = Field(
        default=None,
        description="Path to SSL certificate file"
    )
    SSL_KEY_FILE: Optional[str] = Field(
        default=None,
        description="Path to SSL key file"
    )

    # Logging settings
    ACCESS_LOG: bool = Field(
        default=True,
        description="Enable access logging"
    )
    ACCESS_LOG_FORMAT: str = Field(
        default='%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"',
        description="Access log format"
    )
    
    # Process management
    PID_FILE: str = Field(
        default=".server_pid",
        description="File to store the server PID"
    )
    
    @field_validator("WORKERS")
    @classmethod
    def validate_workers(cls, v: int) -> int:
        """Validate and adjust worker count if needed."""
        import multiprocessing
        
        if v <= 0:
            # Default to number of CPU cores
            return max(multiprocessing.cpu_count(), 2)
        return v
    
    def to_uvicorn_config(self) -> Dict[str, Any]:
        """
        Convert to a dictionary suitable for Uvicorn configuration.
        
        Returns:
            Dictionary with Uvicorn configuration options
        """
        config = {
            "host": self.HOST,
            "port": self.PORT,
            "workers": self.WORKERS,
            "backlog": self.BACKLOG,
            "timeout_keep_alive": self.KEEPALIVE,
            "access_log": self.ACCESS_LOG,
        }
        
        # Add SSL config if enabled
        if self.USE_SSL and self.SSL_CERT_FILE and self.SSL_KEY_FILE:
            config["ssl_certfile"] = self.SSL_CERT_FILE
            config["ssl_keyfile"] = self.SSL_KEY_FILE
        
        return config


# Create a default server config instance
server_config = ServerSettings(
    # Load from environment variables with fallbacks
    HOST=os.getenv("SERVER_HOST", "127.0.0.1"),
    PORT=int(os.getenv("SERVER_PORT", "8000")),
    WORKERS=int(os.getenv("SERVER_WORKERS", "0")),
    BACKLOG=int(os.getenv("SERVER_BACKLOG", "2048")),
    TIMEOUT=int(os.getenv("SERVER_TIMEOUT", "300")),
    KEEPALIVE=int(os.getenv("SERVER_KEEPALIVE", "5")),
    GRACEFUL_TIMEOUT=int(os.getenv("SERVER_GRACEFUL_TIMEOUT", "30")),
    USE_SSL=os.getenv("SERVER_USE_SSL", "False").lower() == "true",
    SSL_CERT_FILE=os.getenv("SERVER_SSL_CERT_FILE"),
    SSL_KEY_FILE=os.getenv("SERVER_SSL_KEY_FILE"),
    ACCESS_LOG=os.getenv("SERVER_ACCESS_LOG", "True").lower() == "true",
    PID_FILE=os.getenv("SERVER_PID_FILE", ".server_pid"),
)
