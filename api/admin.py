# miktos_backend/api/admin.py
import datetime
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dependencies import get_db
from models.database_models import User
from api.auth import get_current_user, is_admin
from services.response_cache_service import response_cache
from repositories.project_repository import ProjectRepository
from repositories.message_repository import MessageRepository
from repositories.user_repository import UserRepository

# Create an API router
router = APIRouter(
    prefix="/admin",
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

@router.post(
    "/cache/invalidate/{model_id}",
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