# miktos_backend/repositories/activity_repository.py
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, UTC  # Added UTC

# Import the SQLAlchemy models
from models.database_models import UserActivity
# Import the BaseRepository
from repositories.base_repository import BaseRepository
# Import the necessary Pydantic schemas
from schemas.activity import ActivityCreate, ActivityUpdate

class ActivityRepository(BaseRepository[UserActivity, ActivityCreate, ActivityUpdate]):
    def __init__(self, db: Session):
        """
        User activity repository for tracking and analyzing user actions.
        
        **Parameters**
        * `db`: A SQLAlchemy database session dependency
        """
        super().__init__(model=UserActivity, db=db)

    # --- Activity Tracking Methods ---
    
    def record_activity(self, user_id: str, activity_type: str, endpoint: str = None, details: dict = None) -> UserActivity:
        """
        Record a new user activity.
        
        Args:
            user_id: The ID of the user
            activity_type: Type of activity (login, api_call, etc.)
            endpoint: The API endpoint accessed (for api_call type)
            details: Additional details about the activity
            
        Returns:
            The created UserActivity record
        """
        details = details or {}
        
        activity = UserActivity(
            user_id=user_id,
            activity_type=activity_type,
            endpoint=endpoint,
            details=details,
            timestamp=datetime.now(UTC)  # Changed from datetime.utcnow()
        )
        
        self.db.add(activity)
        self.db.commit()
        self.db.refresh(activity)
        return activity
    
    # --- Admin Analytics Methods ---
    
    def count_activities_by_type(self, days: int = 7) -> Dict[str, int]:
        """
        Count activities by type for the specified number of days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Dictionary with activity types as keys and counts as values
        """
        since = datetime.now(UTC) - timedelta(days=days)  # Changed from datetime.utcnow()
        
        results = self.db.query(
            UserActivity.activity_type,
            func.count(UserActivity.id).label('count')
        ).filter(
            UserActivity.timestamp >= since
        ).group_by(
            UserActivity.activity_type
        ).all()
        
        return {activity_type: count for activity_type, count in results}
    
    def get_active_users(self, days: int = 1) -> List[Dict[str, Any]]:
        """
        Get list of active users for the specified number of days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of dictionaries with user_id and activity_count
        """
        since = datetime.now(UTC) - timedelta(days=days)  # Changed from datetime.utcnow()
        
        results = self.db.query(
            UserActivity.user_id,
            func.count(UserActivity.id).label('count')
        ).filter(
            UserActivity.timestamp >= since
        ).group_by(
            UserActivity.user_id
        ).order_by(
            desc('count')
        ).all()
        
        return [{"user_id": user_id, "activity_count": count} for user_id, count in results]
    
    def get_popular_endpoints(self, days: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most popular API endpoints.
        
        Args:
            days: Number of days to look back
            limit: Maximum number of endpoints to return
            
        Returns:
            List of dictionaries with endpoint and access_count
        """
        since = datetime.now(UTC) - timedelta(days=days)  # Changed from datetime.utcnow()
        
        results = self.db.query(
            UserActivity.endpoint,
            func.count(UserActivity.id).label('count')
        ).filter(
            UserActivity.timestamp >= since,
            UserActivity.endpoint.isnot(None)
        ).group_by(
            UserActivity.endpoint
        ).order_by(
            desc('count')
        ).limit(limit).all()
        
        return [{"endpoint": endpoint, "access_count": count} for endpoint, count in results]
    
    def get_user_activity_timeline(self, user_id: str, days: int = 7) -> Dict[str, int]:
        """
        Get activity timeline for a specific user.
        
        Args:
            user_id: The ID of the user
            days: Number of days to look back
            
        Returns:
            Dictionary with dates as keys and activity counts as values
        """
        since = datetime.now(UTC) - timedelta(days=days)  # Changed from datetime.utcnow()
        
        # Create a date-only column for grouping
        date_trunc = func.date_trunc('day', UserActivity.timestamp).label('day')
        
        results = self.db.query(
            date_trunc,
            func.count(UserActivity.id).label('count')
        ).filter(
            UserActivity.user_id == user_id,
            UserActivity.timestamp >= since
        ).group_by(
            date_trunc
        ).order_by(
            date_trunc
        ).all()
        
        return {day.strftime("%Y-%m-%d"): count for day, count in results}
