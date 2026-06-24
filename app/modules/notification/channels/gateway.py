from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime

from app.modules.notification.schemas import NotificationCreate
from app.modules.notification.notification_service import NotificationService

logger = logging.getLogger(__name__)


class NotificationGatewayImpl:
    """
    =========================================================
    🔔 NOTIFICATION GATEWAY (ENTERPRISE LAYER)
    =========================================================
    Bridges:
    ✔ Blood Request Service
    ✔ Matching System
    ✔ NotificationService (DB + FCM)
    ✔ Flutter App (NotificationItem model)
    """

    def __init__(self, notification_service: NotificationService | None = None):
        self.notification_service = notification_service or NotificationService()

    # =========================================================
    # 🩸 BLOOD REQUEST CREATED
    # =========================================================
    async def notify_blood_request_created(
        self,
        *,
        request_id: str,
        user_id: UUID,
        blood_group: str,
        location: str,
    ):
        notification = self._build_notification(
            event="blood.request.created",
            service_type="blood",
            category="BLOOD_REQUEST",
            listing_id=request_id,
            user_id=str(user_id),
            title=f"🩸 Blood Request ({blood_group})",
            message=f"New blood request in {location}",
            body=f"Urgent need: {blood_group}",
            sub_type="created",
            status="received",
            location=location,
        )

        return await self._dispatch(notification)

    # =========================================================
    # ❤️ MATCH FOUND
    # =========================================================
    async def notify_match_found(
        self,
        *,
        request_id: str,
        donor_id: str,
        user_id: UUID,
        blood_group: str,
    ):
        notification = self._build_notification(
            event="blood.match.found",
            service_type="blood",
            category="MATCH",
            listing_id=request_id,
            user_id=str(user_id),
            sender_id=donor_id,
            title="❤️ Match Found",
            message=f"Compatible donor found for {blood_group}",
            body="A donor is ready to help",
            sub_type="match_found",
            status="sent",
        )

        return await self._dispatch(notification)

    # =========================================================
    # ✔ REQUEST ACCEPTED
    # =========================================================
    async def notify_request_accepted(
        self,
        *,
        request_id: str,
        donor_id: str,
        user_id: UUID,
    ):
        notification = self._build_notification(
            event="blood.request.accepted",
            service_type="blood",
            category="ACCEPTED",
            listing_id=request_id,
            user_id=str(user_id),
            sender_id=donor_id,
            title="✔ Request Accepted",
            message="A donor accepted your request",
            body="Donation in progress",
            sub_type="accepted",
            status="sent",
        )

        return await self._dispatch(notification)

    # =========================================================
    # 🎉 COMPLETED
    # =========================================================
    async def notify_request_completed(
        self,
        *,
        request_id: str,
        user_id: UUID,
    ):
        notification = self._build_notification(
            event="blood.request.completed",
            service_type="blood",
            category="COMPLETED",
            listing_id=request_id,
            user_id=str(user_id),
            title="🎉 Request Completed",
            message="Your request is completed",
            body="Donation successful",
            sub_type="completed",
            status="delivered",
        )

        return await self._dispatch(notification)

    # =========================================================
    # ❌ CANCELLED
    # =========================================================
    async def notify_request_cancelled(
        self,
        *,
        request_id: str,
        user_id: UUID,
    ):
        notification = self._build_notification(
            event="blood.request.cancelled",
            service_type="blood",
            category="CANCELLED",
            listing_id=request_id,
            user_id=str(user_id),
            title="❌ Request Cancelled",
            message="Your request was cancelled",
            body="No longer active",
            sub_type="cancelled",
            status="cancelled",
        )

        return await self._dispatch(notification)

    # =========================================================
    # 🧱 BUILD NOTIFICATION (USES PYDANTIC SCHEMA)
    # =========================================================
    def _build_notification(
        self,
        *,
        event: str,
        service_type: str,
        category: str,
        listing_id: str,
        user_id: str,
        title: str,
        message: str,
        body: str,
        sub_type: str,
        status: str,
        sender_id: Optional[str] = None,
        location: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> NotificationCreate:

        correlation_id = str(uuid4())

        return NotificationCreate(
            id=str(uuid4()),
            notification_id=str(uuid4()),
            correlation_id=correlation_id,

            event=event,
            status=status,

            title=title,
            message=message,
            body=body,
            sub_type=sub_type,

            service_type=service_type,
            category=category,
            listing_id=listing_id,

            user_id=user_id,
            sender_id=sender_id or "",

            location=location or "",
            phone=phone or "",

            timestamp=datetime.utcnow(),

            data={
                "event": event,
                "service_type": service_type,
                "category": category,
                "listing_id": listing_id,
                "correlation_id": correlation_id,
            },
        )

    # =========================================================
    # 🚀 DISPATCH
    # =========================================================
    async def _dispatch(self, notification: NotificationCreate):
        try:
            result = await self.notification_service.send(notification)

            logger.info(
                "[NOTIFICATION_DISPATCHED] event=%s service_type=%s category=%s",
                notification.event,
                notification.service_type,
                notification.category,
            )

            return {
                "success": True,
                "data": notification.model_dump(),
                "result": result,
            }

        except Exception as e:
            logger.exception("[NOTIFICATION_GATEWAY_ERROR]")

            return {
                "success": False,
                "error": str(e),
                "data": notification.model_dump(),
            }