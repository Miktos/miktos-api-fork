"""
Health check endpoints for the API.
These endpoints provide detailed information about the application's health status.
"""

import os
import platform
import sys
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_db
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


class ComponentStatus(BaseModel):
    """Status of an individual component."""

    name: str = Field(..., description="Name of the component")
    status: str = Field(..., description="Status of the component (healthy, degraded, unhealthy)")
    details: Dict[str, Any] = Field(
        default_factory=dict, description="Additional details about the component"
    )


class HealthStatus(BaseModel):
    """Overall health status of the API."""

    status: str = Field(..., description="Overall status of the API (healthy, degraded, unhealthy)")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Timestamp of the health check"
    )
    components: List[ComponentStatus] = Field(
        default_factory=list, description="Status of individual components"
    )
    environment: str = Field(..., description="Environment the API is running in")


async def _check_database(db: AsyncSession) -> ComponentStatus:
    """
    Check database connectivity.

    Args:
        db: Database session

    Returns:
        Component status for the database
    """
    details = {}
    status_value = "healthy"

    try:
        # Simple query to check database connectivity
        from sqlalchemy import text

        # Handle both async and sync cases for test compatibility
        try:
            result = await db.execute(text("SELECT 1"))
        except (TypeError, AttributeError):
            # Fall back to sync execution for test environments
            try:
                result = db.execute(text("SELECT 1"))
                # Check if result is awaitable
                if hasattr(result, "__await__"):
                    result = await result
            except Exception as inner_e:
                logger.error("DB execution fallback failed", exc_info=inner_e)
                raise

        # Extract the scalar value
        try:
            if hasattr(result, "scalar"):
                result_scalar = result.scalar()
            else:
                # Handle various result objects
                result_scalar = result.first()[0] if hasattr(result, "first") else 1

            details["connected"] = True
            details["query_result"] = result_scalar
        except Exception as scalar_e:
            logger.error("Failed to extract scalar from result", exc_info=scalar_e)
            details["connected"] = True
            details["query_result"] = "query executed but result extraction failed"

    except Exception as e:
        logger.error("Database health check failed", exc_info=e)
        details["connected"] = False
        details["error"] = str(e)
        status_value = "unhealthy"

    return ComponentStatus(name="database", status=status_value, details=details)


async def _check_filesystem() -> ComponentStatus:
    """
    Check filesystem access and space.

    Returns:
        Component status for the filesystem
    """
    details = {}
    status_value = "healthy"

    try:
        # Check if we can write to the filesystem
        test_file_path = "health_check_test_file.txt"
        with open(test_file_path, "w") as f:
            f.write("test")
        os.remove(test_file_path)
        details["write_access"] = True

        # Get disk usage
        if hasattr(os, "statvfs"):
            stats = os.statvfs(".")
            free_space_mb = stats.f_frsize * stats.f_bavail / 1024 / 1024
            details["free_space_mb"] = round(free_space_mb, 2)

            # Mark as degraded if less than 100MB available
            if free_space_mb < 100:
                status_value = "degraded"

    except Exception as e:
        logger.error("Filesystem health check failed", exc_info=e)
        details["error"] = str(e)
        status_value = "unhealthy"

    return ComponentStatus(name="filesystem", status=status_value, details=details)


@router.get("/health", response_model=HealthStatus, tags=["system"])
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthStatus:
    """
    Basic health check endpoint.

    Returns:
        A simplified health status of the API
    """
    logger.debug("Processing health check request")

    # Get version from environment variable or default to "development"
    version = os.environ.get("API_VERSION", "0.1.0")
    environment = os.environ.get("ENVIRONMENT", "development")

    # Check individual components
    db_status = await _check_database(db)
    fs_status = await _check_filesystem()

    components = [db_status, fs_status]

    # Determine overall status (unhealthy if any component is unhealthy)
    overall_status = "healthy"
    for component in components:
        if component.status == "unhealthy":
            overall_status = "unhealthy"
            break
        elif component.status == "degraded" and overall_status == "healthy":
            overall_status = "degraded"

    return HealthStatus(
        status=overall_status, version=version, components=components, environment=environment
    )


class DetailedStatus(HealthStatus):
    """Detailed status information including system details."""

    system_info: Dict[str, Any] = Field(default_factory=dict, description="System information")
    python_info: Dict[str, Any] = Field(default_factory=dict, description="Python information")
    uptime_seconds: Optional[float] = Field(None, description="API uptime in seconds")


_start_time = datetime.now(UTC)


@router.get("/status", response_model=DetailedStatus, tags=["system"])
async def detailed_status(db: AsyncSession = Depends(get_db)) -> DetailedStatus:
    """
    Detailed status check with system information.

    Returns:
        Detailed status information about the API and system
    """
    logger.debug("Processing detailed status request")

    # Get basic health info first
    health = await health_check(db)

    # Calculate uptime
    uptime = (datetime.now(UTC) - _start_time).total_seconds()

    # Collect system information
    system_info = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "hostname": platform.node(),
    }

    # Collect Python information
    python_info = {
        "implementation": platform.python_implementation(),
        "version": sys.version,
        "path": sys.path,
    }

    # Create detailed status
    detailed = DetailedStatus(
        status=health.status,
        version=health.version,
        timestamp=health.timestamp,
        components=health.components,
        environment=health.environment,
        system_info=system_info,
        python_info=python_info,
        uptime_seconds=uptime,
    )

    return detailed
