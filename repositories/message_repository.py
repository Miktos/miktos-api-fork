# repositories/message_repository.py
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc # Import asc
from typing import Optional, List, Dict, Any, Union
from fastapi import HTTPException # Import HTTPException for error handling
from fastapi import status # Import status codes

# Import the SQLAlchemy models
from models.database_models import Message, Project # Import Project model for the check
# Import the BaseRepository
from repositories.base_repository import BaseRepository
# Import the necessary Pydantic schemas from the new message module
from schemas.message import MessageCreate, MessageUpdate, MessageRead # Use MessageRead if needed

class MessageRepository(BaseRepository[Message, MessageCreate, MessageUpdate]):
    def __init__(self, db: Session):
        """
        Message specific repository providing message-related operations.

        **Parameters**
        * `db`: A SQLAlchemy database session dependency
        """
        super().__init__(model=Message, db=db)

    # --- Message Specific Getters ---

    def get_multi_by_project(
        self, *, project_id: str, user_id: str, skip: int = 0, limit: int = 100, ascending: bool = True
    ) -> List[Message]:
        """
        Get all messages for a specific project owned by the user, ordered by creation time.

        Raises HTTPException 404 if project not found or not owned by user.
        """
        # --- ADD OWNERSHIP CHECK ---
        project = self.db.query(Project).filter(Project.id == project_id, Project.owner_id == user_id).first()
        if not project:
            # Raise an exception instead of returning empty list for clarity
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or you do not have permission to access it."
            )
        # --- END OWNERSHIP CHECK ---

        # Project exists and belongs to the user, proceed to get messages
        query = self.db.query(self.model).filter(self.model.project_id == project_id)

        if ascending:
            query = query.order_by(self.model.created_at.asc())
        else:
            query = query.order_by(self.model.created_at.desc())

        return query.offset(skip).limit(limit).all()

    # --- Overriding or Specific Create/Update/Store ---

    # We will rely on the BaseRepository's `create` method.
    # It should work correctly with the `MessageCreate` schema.
    # The `create_message_with_details` can be removed or kept if used elsewhere.

    # Remove or comment out if not needed, BaseRepository.create should suffice
    # def create_message_with_details(self, obj_in: MessageCreate) -> Message:
    #     """Create a new message in a project (example specific method)."""
    #     db_obj = self.model( # Use self.model
    #         project_id=obj_in.project_id,
    #         user_id=obj_in.user_id, # Make sure user_id is included if overriding
    #         role=obj_in.role,
    #         content=obj_in.content,
    #         model=obj_in.model,
    #         message_metadata=obj_in.message_metadata
    #     )
    #     self.db.add(db_obj)
    #     self.db.commit()
    #     self.db.refresh(db_obj)
    #     return db_obj

    # --- Bulk Operations ---
    # Keep store_conversation if you plan to use it, but ensure it includes user_id
    def store_conversation(
        self, project_id: str, user_id: str, messages_data: List[Dict[str, Any]], default_model: Optional[str] = None
    ) -> List[Message]:
        """
        Store a list of messages efficiently in a project.
        Expects a list of dictionaries, each with 'role' and 'content'.
        """
        # --- ADD OWNERSHIP CHECK ---
        project = self.db.query(Project).filter(Project.id == project_id, Project.owner_id == user_id).first()
        if not project:
             raise HTTPException(
                 status_code=status.HTTP_404_NOT_FOUND,
                 detail="Project not found or you do not have permission to access it."
             )
        # --- END OWNERSHIP CHECK ---

        db_messages_to_add = []
        for msg_data in messages_data:
            role = msg_data.get("role")
            # Check for model in message data first, then fall back to default for assistant messages
            model_name = msg_data.get("model") or (default_model if role == "assistant" else None)

            db_message = self.model(
                project_id=project_id,
                user_id=user_id, # <-- Add user_id here
                role=role,
                content=msg_data.get("content"),
                model=model_name,
                message_metadata=msg_data.get("message_metadata") # Include metadata if provided
            )
            db_messages_to_add.append(db_message)

        if db_messages_to_add:
            self.db.add_all(db_messages_to_add)
            self.db.commit()
            # Refreshing might be complex after bulk add. Consider if needed.
            # Querying back might be safer if you need the IDs immediately.
            # For now, returning without refresh.
        return db_messages_to_add