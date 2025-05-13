# miktos_backend/api/admin.py
import datetime
import os
import sys
import time
import signal
import platform
import psutil
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import datetime

from dependencies import get_db
from models.database_models import User
from api.auth import get_current_user, is_admin
from services.response_cache_service import response_cache
from repositories.project_repository import ProjectRepository
from repositories.message_repository import MessageRepository
from repositories.user_repository import UserRepository
from api.health import detailed_status
from server_manager import find_running_servers

# Create an API router
router = APIRouter(
    prefix="",  # Prefix is handled in main.py
    tags=["Admin"],
    dependencies=[Depends(is_admin)],  # All routes require admin permission
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden - Admin access required"}
    }
)

@router.get(
    "/stats",
    summary="Get system statistics",
    description="Returns statistics about the system, including user counts, message counts, and cache usage."
)
async def get_system_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get system statistics including:
    - User counts
    - Message counts
    - Project counts
    - Cache statistics
    - System version and uptime
    """
    # Initialize repositories
    user_repo = UserRepository(db=db)
    project_repo = ProjectRepository(db=db)
    message_repo = MessageRepository(db=db)
    
    # Gather statistics
    stats = {
        "users": {
            "total": user_repo.count(),
            "active": user_repo.count_active()
        },
        "projects": {
            "total": project_repo.count(),
            "by_status": project_repo.count_by_status()
        },
        "messages": {
            "total": message_repo.count(),
            "last_24h": message_repo.count_since(datetime.datetime.now() - datetime.timedelta(days=1))
        },
        "system": {
            "version": "0.2.0",
            "environment": "production",
            "server_time": datetime.datetime.now().isoformat()
        }
    }
    
    # Get cache statistics if Redis is available
    try:
        cache_stats = await response_cache.get_cache_stats()
        stats["cache"] = cache_stats
    except Exception as e:
        stats["cache"] = {"error": str(e)}
    
    return stats

@router.get(
    "/users",
    summary="Get all users",
    description="Returns a list of all users in the system with their basic information."
)
async def get_all_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get list of all users."""
    user_repo = UserRepository(db=db)
    users = user_repo.get_multi()
    
    return [
        {
            "id": str(user.id),
            "email": user.email,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "project_count": len(user.projects)
        }
        for user in users
    ]

@router.get(
    "/users/activity",
    summary="Get user activity data",
    description="Returns user activity statistics and analytics."
)
async def get_user_activity(
    days: int = Query(7, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get user activity data for the admin dashboard.
    
    Args:
        days: Number of days to look back for activity data
        
    Returns:
        A dictionary with various activity metrics
    """
    # Import here to avoid circular imports
    from repositories.activity_repository import ActivityRepository
    
    # Initialize repository
    activity_repo = ActivityRepository(db=db)
    
    # Gather activity statistics
    activity_data = {
        "activity_by_type": activity_repo.count_activities_by_type(days=days),
        "active_users": activity_repo.get_active_users(days=days),
        "popular_endpoints": activity_repo.get_popular_endpoints(days=days),
        "timeframe_days": days,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    return activity_data

@router.post(
    "/cache/invalidate/{model_id:path}",  # Changed to {model_id:path} to allow slashes
    summary="Invalidate cache for a model",
    description="Invalidates all cached responses for the specified model."
)
async def invalidate_cache_for_model(
    model_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Invalidate all cached responses for a specific model.
    
    Args:
        model_id: The model identifier (e.g., "openai/gpt-4")
        
    Returns:
        Information about the cache invalidation operation
    """
    try:
        removed_count = await response_cache.invalidate_cache_for_model(model_id)
        return {
            "success": True,
            "model_id": model_id,
            "entries_removed": removed_count,
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to invalidate cache: {str(e)}"
        )


@router.get(
    "/system/health",
    summary="Get detailed system health",
    description="Returns a comprehensive health check of all system components."
)
async def admin_health_check(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get detailed system health information for administrators.
    
    This endpoint calls the same health check logic used by the public health
    endpoint but provides additional details only visible to administrators.
    """
    try:
        # Import after function definition to avoid circular imports
        from api.health import detailed_status
        health_data = await detailed_status(db)
        
        # Add admin-specific details
        health_data_dict = health_data.model_dump()
        
        # Add server process information
        try:
            import psutil
            import os
            
            # Get the current process
            process = psutil.Process(os.getpid())
            health_data_dict["process_info"] = {
                "pid": process.pid,
                "cpu_percent": process.cpu_percent(),
                "memory_percent": process.memory_percent(),
                "threads": process.num_threads(),
                "open_files": len(process.open_files()),
                "connections": len(process.connections()),
                "create_time": process.create_time(),
            }
        except Exception as proc_err:
            health_data_dict["process_info"] = {"error": str(proc_err)}
            
        return health_data_dict
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system health: {str(e)}"
        )


@router.get(
    "/server/processes",
    summary="Get server processes",
    description="Returns information about all running server processes."
)
async def get_server_processes(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get information about all running server processes.
    
    This endpoint uses psutil to find all server processes and returns
    detailed information about each one.
    """
    try:
        # Import server_manager functions
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from server_manager import find_running_servers
        
        # Get running servers
        servers = find_running_servers()
        server_info = []
        
        for proc in servers:
            try:
                # Extract info directly without using get_server_metadata
                # to avoid circular imports
                host = "127.0.0.1"  # Default
                port = 8000  # Default
                
                # Extract from command line
                for arg in proc.info['cmdline']:
                    if arg.startswith("--host="):
                        host = arg.split("=")[1]
                    elif arg.startswith("--port="):
                        port = arg.split("=")[1]
                
                # Get process information
                proc_info = proc.as_dict(attrs=[
                    'pid', 'create_time', 'num_threads', 
                    'cpu_percent', 'memory_percent'
                ])
                
                # Format uptime
                uptime = time.time() - proc_info['create_time']
                days, remainder = divmod(uptime, 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes, seconds = divmod(remainder, 60)
                uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"
                
                details = {
                    'host': host,
                    'port': port,
                    'pid': proc.pid,
                    'uptime': uptime_str,
                    'uptime_seconds': uptime,
                    'cpu_percent': proc_info['cpu_percent'],
                    'memory_percent': proc_info['memory_percent'],
                    'threads': proc_info['num_threads']
                }
                
                server_info.append(details)
            except Exception as proc_err:
                server_info.append({
                    "pid": proc.pid, 
                    "error": str(proc_err)
                })
        
        return {
            "count": len(servers),
            "servers": server_info,
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get server processes: {str(e)}"
        )
        
        
@router.post(
    "/server/stop/{pid}",
    summary="Stop a specific server process",
    description="Stops a specific server process by PID with graceful shutdown."
)
async def stop_server_process(
    pid: int,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Stop a specific server process using its PID.
    
    Args:
        pid: Process ID of the server to stop
        
    Returns:
        Information about the server stop operation
    """
    try:
        # Check if process exists
        if not psutil.pid_exists(pid):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No process found with PID {pid}"
            )
        
        # Get the process
        proc = psutil.Process(pid)
        
        # Use the standard system signals for graceful shutdown
        if platform.system() == "Windows":
            proc.terminate()
        else:
            # SIGTERM for graceful shutdown
            os.kill(proc.pid, signal.SIGTERM)
            
        # Wait briefly to see if process exits
        grace_period = 5  # Short wait for API response
        deadline = time.time() + grace_period
        success = False
        
        while time.time() < deadline:
            if not psutil.pid_exists(pid):
                success = True
                break
            time.sleep(0.5)
        
        if success or not psutil.pid_exists(pid):
            return {
                "success": True,
                "pid": pid,
                "message": "Server process gracefully stopped",
                "timestamp": datetime.datetime.now().isoformat()
            }
        else:
            # Process still running but return success anyway as shutdown may be in progress
            return {
                "success": True,
                "pid": pid,
                "message": "Shutdown signal sent, server may take time to exit completely",
                "timestamp": datetime.datetime.now().isoformat()
            }
    except psutil.NoSuchProcess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No process found with PID {pid}"
        )
    except psutil.AccessDenied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied when trying to stop process with PID {pid}"
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop server process: {str(e)}"
        )