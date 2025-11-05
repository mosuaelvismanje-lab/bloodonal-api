# app/crud/chat.py

from sqlalchemy.orm import Session
from app.models.chat import ChatRoom, Message
from app.schemas.chat import ChatRoomCreate, MessageCreate
from typing import List, Optional

def get_or_create_room(db: Session, rt: str, rid: int) -> ChatRoom:
    room = db.query(ChatRoom).filter_by(request_type=rt, request_id=rid).first()
    if not room:
        room = ChatRoom(request_type=rt, request_id=rid)
        db.add(room); db.commit(); db.refresh(room)
    return room

def list_messages(db: Session, room_id: int, skip: int=0, limit: int=100) -> List[Message]:
    return (
        db.query(Message)
          .filter(Message.room_id == room_id)
          .order_by(Message.created_at)
          .offset(skip).limit(limit)
          .all()
    )

def create_message(db: Session, msg_in: MessageCreate) -> Message:
    msg = Message(**msg_in.model_dump())
    db.add(msg); db.commit(); db.refresh(msg)
    return msg
