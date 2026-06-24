# =========================================================
# FILE: app/api/routes/notification_routes.py
# =========================================================

from __future__ import annotations

import logging
from typing import Any, Dict
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from app.core.container import Container
from app.dependencies.container import get_container

from app.serializers.notification_serializer import (
    notification_serializer,
)

from app.utils.datetime_utils import (
    utc_iso,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


# =====================================================
# HELPERS
# =====================================================
def _normalize_text(value: str) -> str:
    return value.strip()


def _build_topic(category: str) -> str:
    return f"category_{category.upper()}"


def _safe_response(
    result: Dict[str, Any],
    *,
    service_type: str,
    category: str,
    listing_id: str,
    user_id: UUID,
    topic: str,
) -> Dict[str, Any]:
    """
    Normalize enterprise response payload.
    """

    return {
        "notification_id": result.get("notification_id"),
        "correlation_id": result.get("correlation_id"),
        "message_id": result.get("message_id"),
        "status": result.get("status", "sent"),
        "topic": result.get("topic", topic),
        "service_type": service_type,
        "category": category,
        "listing_id": listing_id,
        "user_id": str(user_id),
        "timestamp": utc_iso(),
    }


# =====================================================
# 🚀 TRIGGER SERVICE NOTIFICATIONS
# =====================================================
@router.post(
    "/trigger",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Dict[str, Any],
)
async def trigger_notification(
    service_type: str = Query(
        ...,
        min_length=2,
        max_length=50,
    ),
    category: str = Query(
        ...,
        min_length=2,
        max_length=50,
    ),
    listing_id: str = Query(
        ...,
        min_length=1,
        max_length=255,
    ),
    user_id: UUID = Query(...),
    container: Container = Depends(get_container),
):
    """
    =====================================================
    ENTERPRISE NOTIFICATION TRIGGER
    =====================================================

    Features:
    - input normalization
    - topic generation
    - enterprise logging
    - rate limiting
    - serializer-safe responses
    - audit-friendly payloads
    """

    try:
        # =================================================
        # NORMALIZE INPUT
        # =================================================
        service_type_clean = _normalize_text(
            service_type
        ).lower()

        category_clean = _normalize_text(
            category
        ).upper()

        listing_id_clean = _normalize_text(
            listing_id
        )

        topic = _build_topic(category_clean)

        # =================================================
        # VALIDATION
        # =================================================
        if not service_type_clean:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="service_type is required",
            )

        if not category_clean:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="category is required",
            )

        if not listing_id_clean:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="listing_id is required",
            )

        # =================================================
        # RESOLVE SERVICES
        # =================================================
        notification_service = getattr(
            container,
            "notification_service",
            None,
        )

        if notification_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Notification service unavailable",
            )

        # =================================================
        # RATE LIMIT CHECK
        # =================================================
        rate_limiter = getattr(
            container,
            "rate_limiter",
            None,
        )

        if rate_limiter:
            allowed = await rate_limiter.allow_topic(
                topic
            )

            if not allowed:
                logger.warning(
                    "[RATE_LIMIT_BLOCK] "
                    "topic=%s user=%s listing=%s",
                    topic,
                    user_id,
                    listing_id_clean,
                )

                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please wait.",
                )

        # =================================================
        # TRIGGER PUSH NOTIFICATION
        # =================================================
        result = await notification_service.trigger_service_notifications(
            service_type=service_type_clean,
            category=category_clean,
            listing_id=listing_id_clean,
            user_id=user_id,
        )

        # =================================================
        # SAFE META RESPONSE
        # =================================================
        meta = _safe_response(
            result,
            service_type=service_type_clean,
            category=category_clean,
            listing_id=listing_id_clean,
            user_id=user_id,
            topic=topic,
        )

        # =================================================
        # SERIALIZED PUSH PAYLOAD
        # =================================================
        serialized_notification = (
            notification_serializer.to_push_payload(
                title=f"New {service_type_clean.title()} Request",
                body=f"New {category_clean.lower()} request available",
                data=meta,
            )
        )

        logger.info(
            "[NOTIFICATION_SENT] "
            "type=%s category=%s listing=%s user=%s",
            service_type_clean,
            category_clean,
            listing_id_clean,
            user_id,
        )

        # =================================================
        # FINAL RESPONSE
        # =================================================
        return {
            "success": True,
            "status": meta["status"],
            "notification": serialized_notification,
            "meta": meta,
        }

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "[NOTIFICATION_ERROR] %s",
            exc,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Notification dispatch failed",
        )