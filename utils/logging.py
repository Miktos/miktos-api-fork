"""
Structured logging utilities for consistent logging across the application.
"""

import json
import logging
import sys
import traceback
import uuid
from datetime import UTC, datetime  # Added UTC timezone
from typing import Any, Dict, Optional, Union

# Configure default logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


# Custom JSON Encoder that handles UUIDs and other special types
class CustomJSONEncoder(json.JSONEncoder):
    """JSON encoder that can handle UUIDs, datetimes, and other special types."""

    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            # Convert UUID to string
            return str(obj)
        if isinstance(obj, datetime):
            # Convert datetime to ISO format
            return obj.isoformat()
        # Let the base class handle anything we don't specifically handle
        return super().default(obj)


class StructuredLogger:
    """
    Logger that provides structured logging capabilities with consistent formatting.
    """

    def __init__(self, name: str):
        """
        Initialize a structured logger with the given name.

        Args:
            name: The logger name, typically __name__ of the module
        """
        self.logger = logging.getLogger(name)
        self.context: Dict[str, Any] = {}

    def with_context(self, **kwargs) -> "StructuredLogger":
        """
        Add context data to all subsequent log messages.

        Args:
            **kwargs: Key-value pairs to add to the context

        Returns:
            Self, for method chaining
        """
        self.context.update(kwargs)
        return self

    def _format_log(self, message: str, extra: Optional[Dict[str, Any]] = None) -> str:
        """Format the log message with context and extra data as JSON."""
        log_data = {
            "message": message,
            "timestamp": datetime.now(UTC).isoformat(),  # Using now(UTC) instead of utcnow()
        }

        # Add context if present
        if self.context:
            log_data["context"] = self.context

        # Add extra data if present
        if extra:
            log_data["data"] = extra

        # Format as JSON for structured logging systems, using our CustomJSONEncoder
        return json.dumps(log_data, cls=CustomJSONEncoder)

    def debug(self, message: str, **kwargs) -> None:
        """Log a debug message with optional extra data."""
        self.logger.debug(self._format_log(message, kwargs if kwargs else None))

    def info(self, message: str, **kwargs) -> None:
        """Log an info message with optional extra data."""
        self.logger.info(self._format_log(message, kwargs if kwargs else None))

    def warning(self, message: str, **kwargs) -> None:
        """Log a warning message with optional extra data."""
        self.logger.warning(self._format_log(message, kwargs if kwargs else None))

    def error(self, message: str, exc_info: Optional[Exception] = None, **kwargs) -> None:
        """
        Log an error message with optional exception info and extra data.

        Args:
            message: The error message
            exc_info: Optional exception object to include stacktrace
            **kwargs: Additional data to include in the log
        """
        extra_data = kwargs.copy() if kwargs else {}

        if exc_info:
            # Include exception details in structured format
            extra_data["exception"] = {
                "type": exc_info.__class__.__name__,
                "message": str(exc_info),
                "traceback": traceback.format_exc(),
            }

        self.logger.error(self._format_log(message, extra_data))

    def critical(self, message: str, exc_info: Optional[Exception] = None, **kwargs) -> None:
        """
        Log a critical error with optional exception info and extra data.

        Args:
            message: The critical error message
            exc_info: Optional exception object to include stacktrace
            **kwargs: Additional data to include in the log
        """
        extra_data = kwargs.copy() if kwargs else {}

        if exc_info:
            # Include exception details in structured format
            extra_data["exception"] = {
                "type": exc_info.__class__.__name__,
                "message": str(exc_info),
                "traceback": traceback.format_exc(),
            }

        self.logger.critical(self._format_log(message, extra_data))


def get_logger(name: str) -> StructuredLogger:
    """
    Get a configured structured logger.

    Usage:
    ```
    logger = get_logger(__name__)
    logger.info("User logged in", user_id="123")
    ```

    Args:
        name: The logger name, typically __name__ of the module

    Returns:
        A configured StructuredLogger instance
    """
    return StructuredLogger(name)
