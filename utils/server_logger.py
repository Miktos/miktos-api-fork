"""
Specialized logging utility for server management operations.

This module provides structured logging specifically for the server lifecycle management,
allowing for better traceability and diagnostics of server operations.
"""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Define log levels as constants
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL

# Default formatting
DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] - %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Define server operation types for structured logging
OP_START = "START"
OP_STOP = "STOP"
OP_STATUS = "STATUS"
OP_CONFIG = "CONFIG"
OP_ERROR = "ERROR"

class ServerLogger:
    """Logger specifically configured for server management operations."""
    
    def __init__(
        self, 
        name="server_manager",
        log_level=INFO,
        log_format=DEFAULT_LOG_FORMAT,
        date_format=DEFAULT_DATE_FORMAT,
        log_to_file=True,
        log_dir="logs",
        log_file="server_operations.log"
    ):
        """
        Initialize a new server logger.
        
        Args:
            name: Logger name
            log_level: Minimum level to log
            log_format: Format string for log messages
            date_format: Format string for timestamps
            log_to_file: Whether to log to a file in addition to console
            log_dir: Directory to store log files
            log_file: Name of the log file
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)
        self.logger.propagate = False
        
        # Clear any existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(log_format, date_format))
        self.logger.addHandler(console_handler)
        
        # File handler (optional)
        if log_to_file:
            # Create log directory if it doesn't exist
            log_path = Path(log_dir)
            log_path.mkdir(exist_ok=True, parents=True)
            
            # Create rotating file handler
            file_handler = logging.FileHandler(
                filename=log_path / log_file,
                mode='a',
                encoding='utf-8'
            )
            file_handler.setFormatter(logging.Formatter(log_format, date_format))
            self.logger.addHandler(file_handler)
    
    def server_operation(self, op_type, message, details=None, level=INFO):
        """
        Log a server operation with structured details.
        
        Args:
            op_type: Type of operation (START, STOP, etc.)
            message: Primary log message
            details: Dictionary with additional details
            level: Log level for this message
        """
        if details is None:
            details = {}
            
        # Add standard metadata
        structured_data = {
            "timestamp": datetime.now().isoformat(),
            "operation": op_type,
            "pid": os.getpid(),
            **details
        }
        
        # Format as JSON-like for easier parsing
        details_str = ", ".join(f"{k}={v}" for k, v in structured_data.items())
        full_message = f"{message} | {details_str}"
        
        # Log at the specified level
        self.logger.log(level, full_message)
    
    # Convenience methods for common operations
    def start(self, message, details=None):
        """Log server start operation."""
        self.server_operation(OP_START, message, details, INFO)
    
    def stop(self, message, details=None):
        """Log server stop operation."""
        self.server_operation(OP_STOP, message, details, INFO)
    
    def status(self, message, details=None):
        """Log server status check."""
        self.server_operation(OP_STATUS, message, details, INFO)
    
    def config(self, message, details=None):
        """Log server configuration."""
        self.server_operation(OP_CONFIG, message, details, DEBUG)
    
    def warning(self, message, details=None):
        """Log server warning."""
        self.server_operation(OP_ERROR, message, details, WARNING)
    
    def error(self, message, details=None):
        """Log server error."""
        self.server_operation(OP_ERROR, message, details, ERROR)


# Create a default instance
server_logger = ServerLogger()
