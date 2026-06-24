from __future__ import annotations

import logging
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect

from app.core.realtime.manager import RealtimeManager

logger = logging.getLogger(__name__)


class DispatchWebSocketHandler:
    """
    Handles ALL dispatch websocket logic (Uber-style separation)
    """

    def __init__(self, manager: RealtimeManager):
        self.manager = manager

    async def connect(self, websocket: WebSocket, service_type: str):
        room = f"dispatch:{service_type}"

        await self.manager.connect(
            websocket,
            service_type=service_type,
            room=room,
        )

        logger.info("Dispatch websocket connected: %s", room)

        try:
            await self._listen(websocket, service_type, room)

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected: %s", room)
            await self.manager.disconnect(websocket)

        except Exception as exc:
            logger.exception("WebSocket error: %s", exc)
            await self.manager.disconnect(websocket)

    async def _listen(
        self,
        websocket: WebSocket,
        service_type: str,
        room: str,
    ):
        """
        Core message loop
        """

        while True:
            message = await websocket.receive_text()
            normalized = message.strip().lower()

            # ============================
            # HEARTBEAT
            # ============================
            if normalized in {"ping", "heartbeat"}:
                await websocket.send_json(
                    {
                        "type": "pong",
                        "serviceType": service_type,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                continue

            # ============================
            # SUBSCRIBE
            # ============================
            if normalized == "subscribe":
                await websocket.send_json(
                    {
                        "type": "subscribed",
                        "room": room,
                        "serviceType": service_type,
                    }
                )
                continue

            # ============================
            # STATUS
            # ============================
            if normalized == "status":
                await websocket.send_json(
                    {
                        "type": "status",
                        "room": room,
                        "connected": True,
                        "serviceType": service_type,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                continue