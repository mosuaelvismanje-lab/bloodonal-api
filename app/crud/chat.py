# app/crud/chat.py
from __future__ import annotations
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_
from app.models.chat import ChatRoom, Message
from app.schemas.chat import MessageCreate

logger = logging.getLogger(__name__)


async def get_or_create_room(
        db: AsyncSession,
        request_type: str,
        request_id: int
) -> ChatRoom:
    """
    Ensures a single chat room exists for a specific service request.
    This is the glue for the Modular Service architecture.
    """
    # 1. Try to find existing room
    query = select(ChatRoom).where(
        and_(
            ChatRoom.request_type == request_type,
            ChatRoom.request_id == request_id
        )
    )
    result = await db.execute(query)
    room = result.scalar_one_or_none()

    if room:
        return room

    # 2. If not found, create it
    new_room = ChatRoom(
        request_type=request_type,
        request_id=request_id
    )
    db.add(new_room)
    await db.commit()
    await db.refresh(new_room)

    logger.info(f"Created new {request_type} chat room for request {request_id}")
    return new_room


async def create_message(db: AsyncSession, obj_in: MessageCreate) -> Message:
    """
    Saves a message to the database.
    Used by the WebSocket router to persist real-time conversations.
    """
    db_obj = Message(
        room_id=obj_in.room_id,
        sender_id=obj_in.sender_id,
        sender_type=obj_in.sender_type,
        content=obj_in.content
    )
    db.add(db_obj)
    # Note: We don't commit here if the router is handling the transaction block,
    # but for WebSockets, we usually commit immediately.
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def get_room_messages(
        db: AsyncSession,
        room_id: int,
        limit: int = 50,
        skip: int = 0
) -> List[Message]:
    """Fetches message history for a room, sorted by oldest first for the UI."""
    query = (
        select(Message)
        .where(Message.room_id == room_id)
        .order_by(Message.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())
