import logging
from datetime import datetime, timedelta
from typing import List, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.repositories.notification_repository import NotificationRepository
from app.repositories.token_repository import TokenRepository
from app.services.notification_service import NotificationService
from app.schemas.notification import NotificationDto, PushNotification, FcmTokenUpdate

logger = logging.getLogger(__name__)

# ✅ FIXED: Changed prefix to "/notifications" to avoid the "/v1/v1" error in logs
router = APIRouter(prefix="/notifications", tags=["notifications"])

# --- In-Memory Rate Limiting for Global Topics ---
# This prevents spamming the global broadcast channel.
last_broadcasts: Dict[str, datetime] = {}
COOLDOWN_SECONDS = 30

# --- Dependency Injection ---
async def get_notification_service(
    session: AsyncSession = Depends(get_async_session),
) -> NotificationService:
    repo = NotificationRepository(session)
    return NotificationService(repo)

async def get_token_repository(
    session: AsyncSession = Depends(get_async_session),
) -> TokenRepository:
    return TokenRepository(session)

# --------------------------------------------------------------------------
# ✅ GET /history/{user_id} - Notification Inbox
# --------------------------------------------------------------------------
@router.get("/history/{user_id}", response_model=List[NotificationDto])
async def get_notification_history(
    user_id: str,
    notifier: NotificationService = Depends(get_notification_service),
):
    """
    Returns the list of past notifications for a user or topic.
    """
    try:
        items = await notifier.repo.list_for_user(user_id)
        return items
    except Exception as exc:
        logger.exception("Failed to list notifications for user=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch notifications",
        )

# --------------------------------------------------------------------------
# ✅ POST /send - The Broadcast/Push Logic (With Rate Limiting)
# --------------------------------------------------------------------------
@router.post("/send", response_model=Dict[str, Any])
async def send_push(
    payload: PushNotification,
    notifier: NotificationService = Depends(get_notification_service),
    token_repo: TokenRepository = Depends(get_token_repository),
):
    """
    Sends a push notification and persists it to history.
    - Uses Rate Limiting for topic-based broadcasts.
    - Automatically cleans up unregistered FCM tokens.
    """
    # 1. Topic Cooldown Logic
    if payload.topic:
        last_time = last_broadcasts.get(payload.topic)
        if last_time and (datetime.now() - last_time) < timedelta(seconds=COOLDOWN_SECONDS):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Topic '{payload.topic}' is on cooldown. Please wait {COOLDOWN_SECONDS}s."
            )
        last_broadcasts[payload.topic] = datetime.now()

    try:
        # 2. Execute Notification through Service
        result = await notifier.create_and_notify(
            user_id=payload.user_id or "unknown",
            sub_type="generic",
            location="N/A",
            phone="N/A",
            message=payload.body,
            title=payload.title,
            data=payload.data,
            token_repo=token_repo,  # Required for automatic token cleanup
            topic=payload.topic
        )
        return result
    except Exception as exc:
        logger.exception("Push notification workflow failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Push notification failed",
        )

# --------------------------------------------------------------------------
# ✅ POST /token - Save/Upsert Device Token
# --------------------------------------------------------------------------
@router.post("/token", status_code=status.HTTP_204_NO_CONTENT)
async def update_token(
    payload: FcmTokenUpdate,
    repo: TokenRepository = Depends(get_token_repository),
):
    """
    Registers or updates an FCM token for a user.
    """
    try:
        await repo.upsert(payload.user_id, payload.token)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        logger.exception("Failed to update FCM token for user=%s", payload.user_id)
        # Detailed error for debugging the timezone/data issues
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(exc)}"
        )

# --------------------------------------------------------------------------
# ✅ GET /token/{user_id} - Debugging
# --------------------------------------------------------------------------
@router.get("/token/{user_id}", response_model=List[str])
async def get_registered_tokens(
    user_id: str,
    repo: TokenRepository = Depends(get_token_repository),
):
    """
    Utility endpoint to see which tokens are currently registered for a user.
    """
    try:
        return await repo.get_tokens(user_id)
    except Exception as exc:
        logger.exception("Failed to fetch tokens for user=%s", user_id)
        raise HTTPException(status_code=500, detail="Could not fetch tokens")