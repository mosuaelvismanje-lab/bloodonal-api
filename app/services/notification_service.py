from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

from firebase_admin import messaging, _apps, initialize_app
from firebase_admin.exceptions import FirebaseError

logger = logging.getLogger(__name__)


class NotificationService:
    """
    2026 Production Standard Notification Service.
    Orchestrates persistence, bulk topic pushes, and high-priority RTC signaling.
    """

    def __init__(self, repo: Any = None):
        self.repo = repo

    def _ensure_firebase_initialized(self):
        """Lazy initialization to prevent 'App already exists' errors in Uvicorn workers."""
        if not _apps:
            try:
                initialize_app()
                logger.info("[FCM_INIT] Firebase Admin initialized.")
            except Exception as e:
                logger.error("[FCM_INIT_FAIL] Firebase failed: %s", e)

    # ---------------------------------------------------------
    # 🚀 The Orchestrator Hook
    # ---------------------------------------------------------
    async def trigger_service_notifications(
            self,
            service_type: str,
            category: str,
            listing_id: str,
            user_id: uuid.UUID
    ):
        """
        Routes notifications based on the service category (e.g., 'BLOOD' -> Topic).
        Ensures all nearby donors or providers are notified instantly.
        """
        self._ensure_firebase_initialized()

        topic_name = f"category_{category.upper()}"
        title = f"New {service_type.replace('_', ' ').title()} Request"
        body = f"A new {category.lower()} request is available in your area."

        data = {
            "listing_id": str(listing_id),
            "service_type": service_type,
            "category": category,
            "click_action": "FLUTTER_NOTIFICATION_CLICK",
            "sender_id": str(user_id)
        }

        await self.send_push_to_topic(topic_name, title, body, data)
        logger.info(f"[NOTIF_DISPATCH] Service {listing_id} notified via topic {topic_name}")

    # ---------------------------------------------------------
    # 📞 High-Priority RTC Signaling (Critical for Video/Audio)
    # ---------------------------------------------------------
    async def send_call_signal(
            self,
            fcm_token: str,
            session_id: str,
            caller_name: str,
            call_mode: str,
            room_name: str,
            token_repo: Optional[Any] = None,
    ) -> Optional[str]:
        """
        Signals an incoming Jitsi/RTC call.
        Uses High Priority to wake up devices even in Doze/Battery-Saving mode.
        """
        if not fcm_token: return None
        self._ensure_firebase_initialized()

        # All values must be strings for FCM data payload
        call_payload = {
            "type": "INCOMING_CALL",
            "session_id": str(session_id),
            "caller_name": str(caller_name),
            "call_mode": str(call_mode),
            "room_name": str(room_name),
            "timestamp": str(int(datetime.now(timezone.utc).timestamp()))
        }

        message = messaging.Message(
            token=fcm_token,
            data=call_payload,
            # Priority high and TTL 0 ensures the message is delivered NOW or not at all.
            android=messaging.AndroidConfig(priority="high", ttl=0),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(aps=messaging.Aps(content_available=True, priority=10))
            )
        )

        try:
            return await asyncio.to_thread(messaging.send, message)
        except messaging.UnregisteredError:
            # Automatic cleanup of stale tokens to keep the DB connection pool clean
            if token_repo and hasattr(token_repo, "delete_token"):
                await token_repo.delete_token(fcm_token)
            return "deleted"
        except Exception as e:
            logger.error(f"[RTC_ERROR] {str(e)}")
            return None

    # ---------------------------------------------------------
    # 🛰 Standard Pushes
    # ---------------------------------------------------------
    async def send_push_to_topic(
            self,
            topic: str,
            title: str,
            body: str,
            data: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        if not topic: return None
        self._ensure_firebase_initialized()

        message = messaging.Message(
            topic=topic,
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
        )

        try:
            return await asyncio.to_thread(messaging.send, message)
        except Exception as e:
            logger.error(f"[TOPIC_ERROR] {topic}: {str(e)}")
            return None

    async def send_push_to_many(
            self,
            tokens: List[str],
            title: str,
            body: str,
            data: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Uses messaging.send_each for 2026 performance standards.
        Optimized for bulk donor alerts.
        """
        if not tokens: return {"status": "empty", "success": 0}
        self._ensure_firebase_initialized()

        # Firebase limits send_each to 500 messages per call
        # We chunk them to avoid hitting SDK limits
        chunk_size = 400
        total_success = 0

        fcm_data = {k: str(v) for k, v in (data or {}).items()}

        for i in range(0, len(tokens), chunk_size):
            batch = tokens[i:i + chunk_size]
            messages = [
                messaging.Message(
                    token=token,
                    notification=messaging.Notification(title=title, body=body),
                    data=fcm_data
                ) for token in batch
            ]

            try:
                response = await asyncio.to_thread(messaging.send_each, messages)
                total_success += response.success_count
            except Exception as e:
                logger.error(f"[FCM_BATCH_ERROR] Chunk {i}: {str(e)}")

        return {"status": "dispatched", "success": total_success}


# Single instance for the application to prevent multiple initialization attempts
notification_service = NotificationService()