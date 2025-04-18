# miktos_backend/repositories/message_repository.py
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, Union # Added Union for potential update override

# Import the SQLAlchemy model
from models.database_models import Message
# Import the BaseRepository
from repositories.base_repository import BaseRepository
# Import the necessary Pydantic schemas
# Assuming MessageUpdate is defined in schemas.user (or schemas.message)
from schemas.user import MessageCreate, MessageUpdate # Or from schemas.message

class MessageRepository(BaseRepository[Message, MessageCreate, MessageUpdate]): # <-- Add MessageUpdate
    def __init__(self, db: Session):
        """
        Message specific repository providing message-related operations.

        **Parameters**
        * `db`: A SQLAlchemy database session dependency
        """
        # Initialize the BaseRepository with the Message model
        super().__init__(model=Message, db=db)

    # --- Message Specific Getters ---

    def get_multi_by_project(
        self, *, project_id: str, skip: int = 0, limit: int = 100, ascending: bool = True
    ) -> List[Message]:
        """
        Get all messages for a specific project, ordered by creation time.
        """
        query = self.db.query(self.model).filter(self.model.project_id == project_id)
        if ascending:
            query = query.order_by(self.model.created_at.asc())
        else:
            query = query.order_by(self.model.created_at.desc())
        return query.offset(skip).limit(limit).all()

    # --- Overriding or Specific Create/Update/Store ---

    # The 'create' method inherited from BaseRepository might be sufficient
    # if MessageCreate fields directly map to Message model fields.
    # If you need specific logic (like setting default metadata), override it.
    # def create(self, *, obj_in: MessageCreate) -> Message:
    #     # Add specific message creation logic if needed
    #     # Otherwise, the base method will use obj_in.model_dump()
    #     return super().create(obj_in=obj_in)

    # Example custom method (renamed from your create_message)
    # This is often preferred over overriding 'create' if the base 'create' works
    # for simple cases, but you need specific logic sometimes.
    def create_message_with_details(self, obj_in: MessageCreate) -> Message:
        """Create a new message in a project (example specific method)."""
        db_obj = self.model( # Use self.model
            project_id=obj_in.project_id,
            role=obj_in.role,
            content=obj_in.content,
            model=obj_in.model
            # Add any other default fields or logic here
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    # The 'update' method from BaseRepository likely handles basic updates.
    # Override only if you need very specific message update logic.
    # def update(self, *, db_obj: Message, obj_in: Union[MessageUpdate, Dict[str, Any]]) -> Message:
    #     # Add specific update logic if needed
    #     return super().update(db_obj=db_obj, obj_in=obj_in)

    # --- Bulk Operations ---

    def store_conversation(
        self, project_id: str, messages_data: List[Dict[str, Any]], default_model: Optional[str] = None
    ) -> List[Message]:
        """
        Store a list of messages efficiently in a project.
        Expects a list of dictionaries, each with 'role' and 'content'.
        """
        db_messages_to_add = []
        for msg_data in messages_data:
            role = msg_data.get("role")
            # Assign model only if it's an assistant message and a default is provided
            model_name = default_model if role == "assistant" and default_model else msg_data.get("model")

            db_message = self.model(
                project_id=project_id,
                role=role,
                content=msg_data.get("content"),
                model=model_name
                # Add other fields like metadata if applicable
            )
            db_messages_to_add.append(db_message)

        if db_messages_to_add:
            # Add all messages in bulk to the session
            self.db.add_all(db_messages_to_add)
            self.db.commit()
            # Refresh objects to get IDs, created_at, etc.
            # Note: Refreshing after bulk add might require querying them back
            # For simplicity, returning the transient objects might be sufficient
            # or you might query them back based on some criteria if needed immediately.
            # For now, let's just return them as they are after commit (may lack IDs).
            # To get IDs, you'd need to query:
            # self.db.flush() # Flushes to get potential IDs before commit
            # ids = [msg.id for msg in db_messages_to_add]
            # self.db.commit()
            # return self.db.query(self.model).filter(self.model.id.in_(ids)).all()

        return db_messages_to_add # Return list of added objects