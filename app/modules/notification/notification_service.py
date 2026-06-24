# =========================================================
# FILE: app/services/notification_service.py
# =========================================================

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.firebase_client import (
    is_firebase_ready,
    send_fcm_to_device,
    send_fcm_to_topic,
)

from app.services.user.analytics_service import (
    analytics_service,
)

from app.utils.datetime_utils import (
    datetime_to_timestamp,
    utc_iso,
    utc_now,
)

logger = logging.getLogger(__name__)

FCM_BATCH_SIZE = 400


# =========================================================
# AUDIT CONTEXT
# =========================================================
@dataclass(slots=True)
class NotificationAuditContext:
    event: str
    notification_id: str
    correlation_id: str
    topic: Optional[str]
    service_type: Optional[str]
    category: Optional[str]
    listing_id: Optional[str]
    user_id: Optional[str]
    status: str
    message_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp or utc_iso()
        return data


# =========================================================
# SERVICE
# =========================================================
class NotificationService:
    """
    =========================================================
    ENTERPRISE NOTIFICATION SERVICE
    =========================================================

    Responsibilities:
    ---------------------------------------------------------
    - Topic notifications
    - Direct FCM delivery
    - Call signaling
    - Notification audit trail
    - Analytics tracking
    - Batch sending
    - Rate limiting integration
    =========================================================
    """

    def __init__(
        self,
        repo: Optional[Any] = None,
        redis_client: Optional[Any] = None,
        rate_limiter: Optional[Any] = None,
    ):
        self.repo = repo
        self.redis = redis_client
        self.rate_limiter = rate_limiter

    # =====================================================
    # HELPERS
    # =====================================================
    def _clean(
        self,
        value: Any,
        fallback: str = "",
    ) -> str:
        if value is None:
            return fallback

        value = str(value).strip()

        return value or fallback

    def _topic(
        self,
        category: str,
    ) -> str:
        return f"category_{category.upper()}"

    # =====================================================
    # ANALYTICS
    # =====================================================
    async def _track_event(
        self,
        db: Optional[AsyncSession],
        *,
        user_id: Optional[str],
        event_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:

        if not db:
            return

        try:
            await analytics_service.track_event(
                db=db,
                user_id=uuid.UUID(user_id) if user_id else None,
                event_name=event_name,
                metadata=metadata or {},
            )

        except Exception as exc:
            logger.warning(
                "[ANALYTICS_FAIL] %s",
                exc,
            )

    # =====================================================
    # AUDIT
    # =====================================================
    async def _audit(
        self,
        ctx: NotificationAuditContext,
        db: Optional[AsyncSession] = None,
    ) -> None:

        payload = ctx.to_dict()

        logger.info(
            "[NOTIF_AUDIT] %s",
            payload,
        )

        await self._track_event(
            db=db,
            user_id=ctx.user_id,
            event_name=ctx.event,
            metadata=payload,
        )

        if not self.repo:
            return

        for method in (
            "save_notification_audit",
            "log_notification_event",
            "record_notification_event",
        ):
            fn = getattr(
                self.repo,
                method,
                None,
            )

            if callable(fn):
                try:
                    result = fn(payload)

                    if asyncio.iscoroutine(result):
                        await result

                except Exception as exc:
                    logger.warning(
                        "[AUDIT_REPO_FAIL] %s",
                        exc,
                    )

                return

    # =====================================================
    # TRIGGER SERVICE NOTIFICATIONS
    # =====================================================
    async def trigger_service_notifications(
        self,
        *,
        service_type: str,
        category: str,
        listing_id: str,
        user_id: uuid.UUID,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:

        service_type = self._clean(service_type).lower()
        category = self._clean(category).upper()
        listing_id = self._clean(listing_id)

        if (
            not service_type
            or not category
            or not listing_id
            or not user_id
        ):
            raise ValueError(
                "Invalid notification inputs",
            )

        notification_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())

        topic = self._topic(category)

        # =================================================
        # AUDIT START
        # =================================================
        await self._audit(
            NotificationAuditContext(
                event="notification.request",
                notification_id=notification_id,
                correlation_id=correlation_id,
                topic=topic,
                service_type=service_type,
                category=category,
                listing_id=listing_id,
                user_id=str(user_id),
                status="started",
            ),
            db=db,
        )

        # =================================================
        # RATE LIMIT
        # =================================================
        if self.rate_limiter:
            allowed = await self.rate_limiter.allow_topic(
                topic,
            )

            if not allowed:
                return {
                    "status": "rate_limited",
                    "notification_id": notification_id,
                    "correlation_id": correlation_id,
                    "topic": topic,
                }

        # =================================================
        # FIREBASE STATUS
        # =================================================
        if not is_firebase_ready():
            logger.warning(
                "Firebase not ready. "
                "firebase_client fallback init will run.",
            )

        # =================================================
        # PAYLOAD
        # =================================================
        data = {
            "notification_id": notification_id,
            "correlation_id": correlation_id,
            "service_type": service_type,
            "category": category,
            "listing_id": listing_id,
            "sender_id": str(user_id),
            "timestamp": utc_iso(),
        }

        # =================================================
        # SEND TOPIC PUSH
        # =================================================
        message_id = await self.send_push_to_topic(
            topic=topic,
            title=f"New {service_type.title()} Request",
            body=f"New {category.lower()} request available",
            data=data,
            notification_id=notification_id,
            correlation_id=correlation_id,
            db=db,
        )

        status = "sent" if message_id else "failed"

        # =================================================
        # AUDIT COMPLETE
        # =================================================
        await self._audit(
            NotificationAuditContext(
                event="notification.completed",
                notification_id=notification_id,
                correlation_id=correlation_id,
                topic=topic,
                service_type=service_type,
                category=category,
                listing_id=listing_id,
                user_id=str(user_id),
                status=status,
                message_id=message_id,
            ),
            db=db,
        )

        return {
            "status": status,
            "notification_id": notification_id,
            "correlation_id": correlation_id,
            "topic": topic,
            "message_id": message_id,
        }

    # =====================================================
    # SEND PUSH TO TOPIC
    # =====================================================
    async def send_push_to_topic(
        self,
        *,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        notification_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Optional[str]:

        topic = self._clean(topic)
        title = self._clean(title)
        body = self._clean(body)

        if not topic or not title or not body:
            return None

        try:
            msg_id = await asyncio.to_thread(
                send_fcm_to_topic,
                topic=topic,
                title=title,
                body=body,
                data=data or {},
            )

            if msg_id:
                await self._audit(
                    NotificationAuditContext(
                        event="notification.sent",
                        notification_id=notification_id
                        or str(uuid.uuid4()),
                        correlation_id=correlation_id
                        or str(uuid.uuid4()),
                        topic=topic,
                        service_type=(data or {}).get(
                            "service_type",
                        ),
                        category=(data or {}).get(
                            "category",
                        ),
                        listing_id=(data or {}).get(
                            "listing_id",
                        ),
                        user_id=(data or {}).get(
                            "sender_id",
                        ),
                        status="sent",
                        message_id=msg_id,
                    ),
                    db=db,
                )

            else:
                await self._audit(
                    NotificationAuditContext(
                        event="notification.failed",
                        notification_id=notification_id
                        or str(uuid.uuid4()),
                        correlation_id=correlation_id
                        or str(uuid.uuid4()),
                        topic=topic,
                        status="failed",
                        error="No message id returned",
                    ),
                    db=db,
                )

            return msg_id

        except Exception as exc:
            logger.exception(
                "[TOPIC_PUSH_ERROR]",
            )

            await self._audit(
                NotificationAuditContext(
                    event="notification.failed",
                    notification_id=notification_id
                    or str(uuid.uuid4()),
                    correlation_id=correlation_id
                    or str(uuid.uuid4()),
                    topic=topic,
                    status="failed",
                    error=str(exc),
                ),
                db=db,
            )

            return None

    # =====================================================
    # CALL SIGNAL
    # =====================================================
    async def send_call_signal(
        self,
        *,
        fcm_token: str,
        session_id: str,
        caller_name: str,
        call_mode: str,
        room_name: str,
        token_repo: Optional[Any] = None,
        db: Optional[AsyncSession] = None,
    ) -> Optional[str]:

        fcm_token = self._clean(fcm_token)

        if not fcm_token:
            return None

        notification_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())

        payload = {
            "notification_id": notification_id,
            "correlation_id": correlation_id,
            "type": "CALL",
            "session_id": session_id,
            "caller_name": caller_name,
            "call_mode": call_mode,
            "room_name": room_name,
            "timestamp": str(
                datetime_to_timestamp(
                    utc_now(),
                )
            ),
        }

        try:
            msg_id = await asyncio.to_thread(
                send_fcm_to_device,
                token=fcm_token,
                title=f"{caller_name} is calling",
                body=f"Incoming {call_mode} call",
                data=payload,
            )

            # =============================================
            # TOKEN INVALID
            # =============================================
            if msg_id == "UNREGISTERED":

                if (
                    token_repo
                    and hasattr(token_repo, "delete_token")
                ):
                    await token_repo.delete_token(
                        fcm_token,
                    )

                await self._audit(
                    NotificationAuditContext(
                        event="call.failed",
                        notification_id=notification_id,
                        correlation_id=correlation_id,
                        topic=None,
                        service_type="rtc",
                        category="CALL",
                        listing_id=session_id,
                        user_id=None,
                        status="unregistered",
                        error="token removed",
                    ),
                    db=db,
                )

                return "deleted"

            # =============================================
            # SUCCESS
            # =============================================
            if msg_id:
                await self._audit(
                    NotificationAuditContext(
                        event="call.sent",
                        notification_id=notification_id,
                        correlation_id=correlation_id,
                        topic=None,
                        service_type="rtc",
                        category="CALL",
                        listing_id=session_id,
                        user_id=None,
                        status="sent",
                        message_id=msg_id,
                    ),
                    db=db,
                )

                return msg_id

            return None

        except Exception as exc:
            logger.exception(
                "[CALL_SIGNAL_ERROR]",
            )

            await self._audit(
                NotificationAuditContext(
                    event="call.failed",
                    notification_id=notification_id,
                    correlation_id=correlation_id,
                    topic=None,
                    service_type="rtc",
                    category="CALL",
                    listing_id=session_id,
                    user_id=None,
                    status="failed",
                    error=str(exc),
                ),
                db=db,
            )

            return None

    # =====================================================
    # MULTICAST PUSH
    # =====================================================
    async def send_push_to_many(
        self,
        *,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        token_repo: Optional[Any] = None,
    ) -> Dict[str, Any]:

        tokens = [
            token
            for token in tokens
            if self._clean(token)
        ]

        if not tokens:
            return {
                "status": "empty",
                "success": 0,
                "failed": 0,
                "total": 0,
            }

        tasks = [
            asyncio.to_thread(
                send_fcm_to_device,
                token=token,
                title=title,
                body=body,
                data=data or {},
            )
            for token in tokens
        ]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        success = 0
        failed = 0

        for token, result in zip(tokens, results):

            if isinstance(result, Exception):
                failed += 1
                continue

            if result == "UNREGISTERED":

                failed += 1

                if (
                    token_repo
                    and hasattr(token_repo, "delete_token")
                ):
                    try:
                        await token_repo.delete_token(token)

                    except Exception:
                        logger.warning(
                            "Failed deleting invalid token: %s",
                            token[:12],
                        )

                continue

            if result:
                success += 1
            else:
                failed += 1

        return {
            "status": "done",
            "success": success,
            "failed": failed,
            "total": len(tokens),
        }

    # =====================================================
    # HEALTH CHECK
    # =====================================================
    async def health_check(
        self,
    ) -> Dict[str, Any]:

        return {
            "firebase": is_firebase_ready(),
            "redis": self.redis is not None,
            "rate_limiter": self.rate_limiter is not None,
            "time": utc_iso(),
        }


notification_service = NotificationService()