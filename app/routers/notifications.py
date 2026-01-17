# File: app/routers/notifications.py
import asyncio
import inspect
import logging
from typing import List, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.repositories.notification_repository import NotificationRepository
from app.repositories.token_repository import TokenRepository
from app.services.notification_service import NotificationService
from app.schemas.notification import NotificationDto, PushNotification, FcmTokenUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


async def _maybe_await(func: Any, *args, **kwargs):
    """
    If func is async, await it. If it's sync, run it in a thread to avoid blocking.
    Returns the underlying function result.
    """
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return await asyncio.to_thread(func, *args, **kwargs)


async def get_notification_service(
    session: AsyncSession = Depends(get_async_session),
) -> NotificationService:
    """
    Build and return a NotificationService wired with NotificationRepository.
    """
    repo = NotificationRepository(session)
    svc = NotificationService(repo)
    return svc


async def get_token_repository(
    session: AsyncSession = Depends(get_async_session),
) -> TokenRepository:
    """Dependency for TokenRepository."""
    return TokenRepository(session)


@router.get("/", response_model=List[NotificationDto])
async def list_notifications(
    user_id: str,
    notifier: NotificationService = Depends(get_notification_service),
):
    """
    List notifications for a user.
    """
    try:
        list_fn = getattr(notifier.repo, "list_for_user", None)
        if list_fn is None:
            raise AttributeError("NotificationRepository missing list_for_user")
        items = await _maybe_await(list_fn, user_id)
        return items
    except AttributeError:
        logger.error("NotificationRepository missing list_for_user method")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Notification repository misconfigured",
        )
    except Exception as exc:
        logger.exception("Failed to list notifications for user=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch notifications",
        ) from exc


@router.post("/send", response_model=Dict[str, Any])
async def send_push(
    payload: PushNotification,
    notifier: NotificationService = Depends(get_notification_service),
    token_repo: TokenRepository = Depends(get_token_repository),
):
    """
    Create a notification and optionally send push notifications to all user's tokens.
    Treats `topic` as a single FCM token if provided, otherwise fetches tokens from the repository.
    """
    try:
        fcm_tokens: List[str] = []
        if payload.topic:
            fcm_tokens = [payload.topic]  # Single token
        else:
            # fetch all tokens for the user_id if topic not provided
            if hasattr(payload, "user_id") and payload.user_id:
                fcm_tokens = await token_repo.get_tokens(payload.user_id)

        result = await notifier.create_and_notify(
            user_id=getattr(payload, "user_id", "unknown"),
            sub_type="generic",
            location="N/A",
            phone="N/A",
            message=payload.body,
            title=payload.title,
            token_repo=token_repo if fcm_tokens else None,
        )
        return result
    except Exception as exc:
        logger.exception(
            "Failed to send push notification to payload=%s", payload.model_dump()
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Push notification failed",
        ) from exc


@router.post("/token", status_code=status.HTTP_204_NO_CONTENT)
async def update_token(
    payload: FcmTokenUpdate,
    repo: TokenRepository = Depends(get_token_repository),
):
    """
    Save or update a user's FCM token.
    """
    try:
        await repo.upsert(payload.user_id, payload.token)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        logger.exception("Failed to update FCM token for user=%s", payload.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update FCM token",
        ) from exc


@router.get("/token/{user_id}", response_model=List[str])
async def get_tokens(
    user_id: str,
    repo: TokenRepository = Depends(get_token_repository),
):
    """
    Retrieve all stored FCM tokens for a given user.
    Useful for debugging or multi-device support.
    """
    try:
        tokens = await repo.get_tokens(user_id)
        return tokens
    except Exception as exc:
        logger.exception("Failed to fetch FCM tokens for user=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch FCM tokens",
        ) from exc
