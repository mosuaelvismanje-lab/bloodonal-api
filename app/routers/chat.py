from __future__ import annotations
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status, HTTPException
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, get_async_session
from app.crud.chat import get_or_create_room, create_message
from app.schemas.chat import ChatRoomCreate, ChatRoomOut, MessageCreate, MessageOut
from app.api.dependencies import get_current_user  # Used for REST endpoints

logger = logging.getLogger(__name__)

# ✅ OPTION A: Clean prefix. Versioning (/v1) handled in main.py
router = APIRouter(prefix="/chat", tags=["Chat & Signaling"])


# -----------------------------
# 1. Connection Manager
# -----------------------------
class ConnectionManager:
    """
    Orchestrates real-time message broadcasting for modular service requests.
    """

    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, room_id: int, ws: WebSocket):
        await ws.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(ws)

    def disconnect(self, room_id: int, ws: WebSocket):
        if room_id in self.active_connections:
            try:
                self.active_connections[room_id].remove(ws)
                if not self.active_connections[room_id]:
                    del self.active_connections[room_id]
            except ValueError:
                pass

    async def broadcast(self, room_id: int, message_dict: dict):
        if room_id in self.active_connections:
            # Create a copy of the list to avoid "RuntimeError: dictionary changed size"
            for connection in list(self.active_connections[room_id]):
                try:
                    await connection.send_json(message_dict)
                except Exception as e:
                    logger.error(f"Failed to send broadcast to a client: {e}")
                    # Auto-cleanup failed connections
                    self.disconnect(room_id, connection)


manager = ConnectionManager()


# -----------------------------
# 2. REST Endpoints
# -----------------------------

@router.post("/rooms/", response_model=ChatRoomOut, status_code=status.HTTP_200_OK)
async def open_room(
        r: ChatRoomCreate,
        current_user=Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """
    Opens/Creates a chat room for coordination.
    """
    room = await get_or_create_room(
        db=db,
        request_type=r.request_type,
        request_id=r.request_id
    )
    return room


# -----------------------------
# 3. WebSocket Endpoint
# -----------------------------

@router.websocket("/rooms/{room_id}/ws")
async def ws_chat(
        room_id: int,
        websocket: WebSocket,
        token: str | None = None
):
    """
    Real-time WebSocket bridge with per-message transaction handling.
    """
    # NOTE: You should ideally verify the 'token' here against Firebase
    # before calling manager.connect() to prevent unauthorized access.

    await manager.connect(room_id, websocket)

    try:
        while True:
            # 1. Receive JSON data
            data = await websocket.receive_json()

            # 2. Process transaction in a fresh session scope
            # This is critical for high-latency/VPN resilience.
            async with AsyncSessionLocal() as session:
                try:
                    data["room_id"] = room_id

                    # 3. Persistence
                    msg_in = MessageCreate(**data)
                    msg = await create_message(session, msg_in)
                    await session.commit()
                    await session.refresh(msg)

                    # 4. Prepare and Broadcast
                    out = MessageOut.model_validate(msg).model_dump()
                    out["created_at"] = out["created_at"].isoformat()

                    await manager.broadcast(room_id, out)

                except Exception as tx_error:
                    await session.rollback()
                    logger.error(f"Message transaction failed: {tx_error}")
                    await websocket.send_json({"error": "Failed to save message"})

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from room {room_id}")
        manager.disconnect(room_id, websocket)

    except Exception as e:
        logger.error(f"WebSocket fatal error in room {room_id}: {e}")
        manager.disconnect(room_id, websocket)