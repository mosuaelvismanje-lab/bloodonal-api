# app/routers/chat.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal  # import sessionmaker object
from app.crud.chat import get_or_create_room, list_messages, create_message
from app.schemas.chat import ChatRoomCreate, ChatRoomOut, MessageCreate, MessageOut

router = APIRouter(prefix="/chat", tags=["chat"])

# REST endpoints can remain similar but async
@router.post("/rooms/", response_model=ChatRoomOut)
async def open_room(r: ChatRoomCreate):
    # implement room creation with async DB inside CRUD functions
    room = await get_or_create_room(r)  # ensure this function is async
    return room

# WebSocket manager (same as before)
class ConnectionManager:
    def __init__(self):
        self.active: dict[int, List[WebSocket]] = {}

    async def connect(self, room_id: int, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(room_id, []).append(ws)

    def disconnect(self, room_id: int, ws: WebSocket):
        self.active.get(room_id, []).remove(ws)

    async def broadcast(self, room_id: int, msg: dict):
        for ws in list(self.active.get(room_id, [])):
            await ws.send_json(msg)

manager = ConnectionManager()

@router.websocket("/rooms/{room_id}/ws")
async def ws_chat(room_id: int, websocket: WebSocket):
    await manager.connect(room_id, websocket)
    try:
        async with AsyncSessionLocal() as session:  # create own session for this connection
            while True:
                data = await websocket.receive_json()
                # create_message should be async and accept session
                msg_in = MessageCreate(room_id=room_id, **data)
                msg = await create_message(session, msg_in)
                out = MessageOut.from_orm(msg).model_dump()
                await manager.broadcast(room_id, out)
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)

