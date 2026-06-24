from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SocketClient:
    websocket: WebSocket
    user_id: Optional[str] = None
    service_type: Optional[str] = None
    room: Optional[str] = None
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RealtimeManager:
    """
    =========================================================
    REALTIME MANAGER (WEBSOCKET LAYER)
    =========================================================

    Responsibilities:
    - Accept websocket connections
    - Track connected clients
    - Broadcast live dispatch events
    - Support per-room / per-service subscriptions
    - Keep transport logic separate from dispatch business logic

    This layer is transport-only:
    - no ranking
    - no matching
    - no repository logic
    """

    def __init__(self) -> None:
        self._clients: Set[SocketClient] = set()
        self._lock = asyncio.Lock()

    # =========================================================
    # CONNECTION LIFECYCLE
    # =========================================================

    async def connect(
        self,
        websocket: WebSocket,
        *,
        user_id: Optional[str] = None,
        service_type: Optional[str] = None,
        room: Optional[str] = None,
    ) -> SocketClient:
        await websocket.accept()

        client = SocketClient(
            websocket=websocket,
            user_id=str(user_id).strip() if user_id else None,
            service_type=str(service_type).strip().lower() if service_type else None,
            room=str(room).strip().lower() if room else None,
        )

        async with self._lock:
            self._clients.add(client)

        logger.info(
            "WebSocket connected | user_id=%s | service_type=%s | room=%s",
            client.user_id,
            client.service_type,
            client.room,
        )
        return client

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            target = None
            for client in self._clients:
                if client.websocket is websocket:
                    target = client
                    break

            if target is not None:
                self._clients.remove(target)
                logger.info(
                    "WebSocket disconnected | user_id=%s | service_type=%s | room=%s",
                    target.user_id,
                    target.service_type,
                    target.room,
                )

    # =========================================================
    # MESSAGE SENDING
    # =========================================================

    async def send_personal(
        self,
        websocket: WebSocket,
        payload: Dict[str, Any],
    ) -> None:
        await websocket.send_text(self._encode(payload))

    async def send_to_user(
        self,
        user_id: str,
        payload: Dict[str, Any],
    ) -> int:
        return await self._broadcast(
            payload,
            predicate=lambda client: client.user_id == str(user_id).strip(),
        )

    async def send_to_service_type(
        self,
        service_type: str,
        payload: Dict[str, Any],
    ) -> int:
        normalized = str(service_type).strip().lower()
        return await self._broadcast(
            payload,
            predicate=lambda client: client.service_type == normalized,
        )

    async def send_to_room(
        self,
        room: str,
        payload: Dict[str, Any],
    ) -> int:
        normalized = str(room).strip().lower()
        return await self._broadcast(
            payload,
            predicate=lambda client: client.room == normalized,
        )

    async def broadcast(
        self,
        payload: Dict[str, Any],
    ) -> int:
        return await self._broadcast(payload, predicate=lambda _: True)

    # =========================================================
    # DISPATCH-SPECIFIC HELPERS
    # =========================================================

    async def publish_location_update(
            self,
            *,
            user_id: str,
            service_type: str,
            latitude: float,
            longitude: float,
            is_active: bool = True,
            speed_kmh: Optional[float] = None,
            heading: Optional[float] = None,
            accuracy_meters: Optional[float] = None,
    ) -> int:

        payload = {
            "event": "location.updated",
            "timestamp": self._now(),
            "data": {
                "user_id": str(user_id),
                "service_type": str(service_type).strip().lower(),
                "latitude": float(latitude),
                "longitude": float(longitude),
                "is_active": bool(is_active),
                "speed_kmh": speed_kmh,
                "heading": heading,
                "accuracy_meters": accuracy_meters,
            },
        }

        return await self.send_to_service_type(service_type, payload)

    async def publish_request_event(
            self,
            *,
            event_type: str,
            data: Dict[str, Any],
            service_type: Optional[str] = None,
            room: Optional[str] = None,
    ) -> int:

        payload = {
            "event": event_type,
            "timestamp": self._now(),
            "data": data,
        }

        if room:
            return await self.send_to_room(room, payload)

        if service_type:
            return await self.send_to_service_type(service_type, payload)

        return await self.broadcast(payload)
    async def publish_assignment_event(
            self,
            *,
            request_id: str,
            donor_id: str,
            score: Optional[float] = None,
            eta_minutes: Optional[int] = None,
            service_type: Optional[str] = None,
    ) -> int:

        payload = {
            "event": "request.assigned",
            "timestamp": self._now(),
            "data": {
                "request_id": str(request_id),
                "donor_id": str(donor_id),
                "score": score,
                "eta_minutes": eta_minutes,
            },
        }

        if service_type:
            return await self.send_to_service_type(service_type, payload)

        return await self.broadcast(payload)

    async def publish_cluster_update(
            self,
            *,
            service_type: str,
            clusters: list[dict[str, Any]],
    ) -> int:

        payload = {
            "event": "clusters.updated",
            "timestamp": self._now(),
            "data": {
                "service_type": str(service_type).strip().lower(),
                "clusters": clusters,
            },
        }

        return await self.send_to_service_type(service_type, payload)

    # =========================================================
    # INTROSPECTION / HEALTH
    # =========================================================

    async def count_clients(self) -> int:
        async with self._lock:
            return len(self._clients)

    async def count_clients_for_service(self, service_type: str) -> int:
        normalized = str(service_type).strip().lower()
        async with self._lock:
            return sum(1 for c in self._clients if c.service_type == normalized)

    async def snapshot(self) -> list[dict[str, Any]]:
        async with self._lock:
            return [
                {
                    "user_id": c.user_id,
                    "service_type": c.service_type,
                    "room": c.room,
                    "connected_at": c.connected_at.isoformat(),
                    "last_seen_at": c.last_seen_at.isoformat(),
                }
                for c in self._clients
            ]

    # =========================================================
    # INTERNAL BROADCAST ENGINE
    # =========================================================

    async def _broadcast(
        self,
        payload: Dict[str, Any],
        *,
        predicate,
    ) -> int:
        message = self._encode(payload)
        sent = 0
        dead_clients: list[SocketClient] = []

        async with self._lock:
            clients = list(self._clients)

        for client in clients:
            if not predicate(client):
                continue

            try:
                await client.websocket.send_text(message)
                client.last_seen_at = datetime.now(timezone.utc)
                sent += 1
            except WebSocketDisconnect:
                dead_clients.append(client)
            except Exception as exc:
                logger.exception("WebSocket send failure: %s", exc)
                dead_clients.append(client)

        if dead_clients:
            async with self._lock:
                for client in dead_clients:
                    self._clients.discard(client)

        return sent

    # =========================================================
    # SERIALIZATION / HELPERS
    # =========================================================

    def _encode(self, payload: Dict[str, Any]) -> str:
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=self._json_default,
        )

    def _json_default(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()