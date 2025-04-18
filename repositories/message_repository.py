# miktos_backend/repositories/message_repository.py
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from models.database_models import Message
from repositories.base_repository import BaseRepository
from schemas.user import MessageCreate

class MessageRepository(BaseRepository[Message, MessageCreate]):
    def __init__(self, db: Session):
        super().__init__(Message, db)
    
    def get_project_messages(self, project_id: str, skip: int = 0, limit: int = 100) -> List[Message]:
        """Get all messages for a specific project"""
        return self.db.query(Message).filter(Message.project_id == project_id).order_by(Message.created_at).offset(skip).limit(limit).all()
    
    def create_message(self, obj_in: MessageCreate) -> Message:
        """Create a new message in a project"""
        db_obj = Message(
            project_id=obj_in.project_id,
            role=obj_in.role,
            content=obj_in.content,
            model=obj_in.model
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def store_conversation(self, project_id: str, messages: List[dict], model: Optional[str] = None) -> List[Message]:
        """Store a full conversation (multiple messages) in a project"""
        db_messages = []
        for msg in messages:
            db_message = Message(
                project_id=project_id,
                role=msg.get("role"),
                content=msg.get("content"),
                model=model if msg.get("role") == "assistant" else None
            )
            self.db.add(db_message)
            db_messages.append(db_message)
        
        self.db.commit()
        # Refresh all
        for msg in db_messages:
            self.db.refresh(msg)
        
        return db_messages