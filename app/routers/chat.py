from __future__ import annotations
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status, HTTPException
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, get_async_session
from app.crud.chat import get_or_create_room, create_message
from app.schemas.chat import ChatRoomCreate, ChatRoomOut, MessageCreate, MessageOut
from app.api.dependencies import get_current_user  # To secure the endpoints

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/chat", tags=["Chat & Signaling"])


# -----------------------------
# 1. Connection Manager
# -----------------------------
class ConnectionManager:
    """
    Orchestrates real-time message broadcasting for modular service requests.
    Supports Doctor/Nurse consults and Blood Request coordination.
    """

    def __init__(self):
        # Maps room_id to a list of active WebSocket connections
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
                pass  # Connection already removed

    async def broadcast(self, room_id: int, message_dict: dict):
        """Sends message to all connected parties (patient, provider, admin)."""
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                try:
                    await connection.send_json(message_dict)
                except Exception as e:
                    logger.error(f"Failed to send broadcast: {e}")


manager = ConnectionManager()


# -----------------------------
# 2. REST Endpoints
# -----------------------------

@router.post("/rooms/", response_model=ChatRoomOut, status_code=status.HTTP_200_OK)
async def open_room(
        r: ChatRoomCreate,
        current_user=Depends(get_current_user),  # Secure the room creation
        db: AsyncSession = Depends(get_async_session)
):
    """
    Opens an existing room or creates a new one based on request_type and request_id.
    Ensures coordination between patients and healthcare providers.
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
        token: str | None = None  # Standard way to pass Firebase JWT in WS headers
):
    """
    Real-time WebSocket bridge.
    Handles message persistence and immediate broadcasting.
    """
    await manager.connect(room_id, websocket)

    try:
        # 2026 Security: WebSockets should still logically belong to a user session
        async with AsyncSessionLocal() as session:
            while True:
                # 1. Receive JSON data from mobile/web client
                # Expected format: {"sender_id": "UID...", "sender_type": "patient", "content": "..."}
                data = await websocket.receive_json()

                # 2. Validation: Ensure room_id is injected from the URL path
                data["room_id"] = room_id

                # 3. Save message to database (using the String UID sender_id)
                msg_in = MessageCreate(**data)
                msg = await create_message(session, msg_in)

                # IMPORTANT: In SQLAlchemy async, we must commit here for the
                # broadcast to be "visible" to other queries if needed.
                await session.commit()

                # 4. Prepare data for broadcast
                out = MessageOut.model_validate(msg).model_dump()

                # Convert datetime to ISO string for JSON serialization
                out["created_at"] = out["created_at"].isoformat()

                # 5. Send to everyone in the room
                await manager.broadcast(room_id, out)

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from room {room_id}")
        manager.disconnect(room_id, websocket)

    except Exception as e:
        logger.error(f"WebSocket Error in room {room_id}: {e}")
        manager.disconnect(room_id, websocket)