# app/routers/notifications.py
import asyncio
import inspect
import logging
from typing import List, Any

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
    The repository/service should ideally accept AsyncSession and implement async methods,
    but this router supports sync implementations as well (they will be run in a thread).
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
        items = await _maybe_await(getattr(notifier, "list_for_user"), user_id)
        return items
    except AttributeError:
        logger.error("NotificationService missing list_for_user method")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Notification service misconfigured",
        )
    except Exception as exc:
        logger.exception("Failed to list notifications for user=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch notifications",
        ) from exc


@router.post("/send", response_model=dict)
async def send_push(
    payload: PushNotification,
    notifier: NotificationService = Depends(get_notification_service),
):
    """
    Accepts a PushNotification (title, body, topic or token).
    Here we treat `topic` as a single-device FCM token for simplicity.
    Returns a dict with message_id on success.
    """
    try:
        send_fn = getattr(notifier, "send_push", None)
        if send_fn is None:
            logger.error("NotificationService missing send_push method")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Notification service misconfigured",
            )

        fcm_token = payload.topic  # treating topic as a single-device token
        title = payload.title
        body = payload.body

        message_id = await _maybe_await(send_fn, fcm_token, title, body)
        return {"message_id": message_id}
    except Exception as exc:
        logger.exception(
            "Failed to send push notification to token=%s", payload.topic
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
