# File: app/services/notification_service.py
import asyncio
import logging
from typing import Optional, Dict, List, Any

from firebase_admin import messaging, _apps, initialize_app  # type: ignore
from firebase_admin.exceptions import FirebaseError

from app.models.notification import Notification as NotificationModel
from app.repositories.notification_repository import NotificationRepository

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service responsible for:
      - persisting notifications (via NotificationRepository or fallback)
      - sending FCM pushes via firebase_admin.messaging (async wrapper)
    """

    def __init__(self, repo: NotificationRepository):
        """
        repo: an instance of NotificationRepository (async-friendly)
        """
        self.repo = repo

    # -------------------------
    # Low-level FCM send
    # -------------------------
    async def send_push(
        self,
        fcm_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """
        Send a push to a single FCM device token.

        Returns the message_id returned by Firebase on success, or None on failure.
        """
        if not fcm_token:
            logger.warning("send_push called with empty fcm_token")
            return None

        # Ensure firebase is initialized (this will raise if no credentials)
        if not _apps:
            logger.debug("Firebase app not initialized (no apps found) — attempting to initialize default app")
            try:
                initialize_app()
            except Exception as e:
                logger.exception("Failed to initialize firebase default app inside NotificationService: %s", e)
                return None

        message = messaging.Message(
            token=fcm_token,
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
        )

        try:
            # firebase_admin.messaging.send is synchronous; run it in a thread to avoid blocking the event loop
            message_id = await asyncio.to_thread(messaging.send, message)
            logger.info("FCM message sent successfully message_id=%s to token=%s", message_id, fcm_token)
            return message_id
        except FirebaseError as fe:
            logger.exception("FirebaseError while sending push to token=%s: %s", fcm_token, fe)
            return None
        except Exception as e:
            logger.exception("Unexpected error while sending push to token=%s: %s", fcm_token, e)
            return None

    # -------------------------
    # Send to many tokens
    # -------------------------
    async def send_push_to_many(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Optional[str]]:
        """
        Send the same notification to multiple tokens concurrently.
        Returns a dict mapping token -> message_id (or None on failure).
        """
        tasks = [self.send_push(t, title, body, data) for t in tokens]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return {token: msg_id for token, msg_id in zip(tokens, results)}

    # -------------------------
    # Create notification + notify
    # -------------------------
    async def create_and_notify(
        self,
        user_id: str,
        sub_type: str,
        location: str,
        phone: str,
        message: str,
        title: Optional[str] = None,
        data: Optional[Dict[str, str]] = None,
        token_repo: Optional[Any] = None,  # expected to provide get_tokens(user_id) -> List[str]
    ) -> dict:
        """
        Persist a notification and optionally send push notifications to the user's devices.

        - If NotificationRepository implements `create_notification(...)` it will be used.
        - Otherwise this function will attempt to create the Notification row directly using the repo's session.
        - If token_repo is provided and has `get_tokens(user_id)`, those tokens are used for push delivery.

        Returns a dict with keys:
          - "notification": NotificationModel (or minimal dict representation)
          - "push_results": dict mapping token->message_id (if token_repo supplied), otherwise {}
        """
        # 1) Persist notification
        notif = None
        try:
            create_fn = getattr(self.repo, "create_notification", None)
            if create_fn and asyncio.iscoroutinefunction(create_fn):
                notif = await create_fn(user_id=user_id, sub_type=sub_type, location=location, phone=phone, message=message, title=title)
            elif create_fn:
                # sync create_notification -- run in thread
                notif = await asyncio.to_thread(create_fn, user_id, sub_type, location, phone, message, title)
            else:
                # Fallback: manual insert using repo._session and NotificationModel
                # This assumes repo exposes _session (as in repository pattern used earlier)
                session = getattr(self.repo, "_session", None)
                if session is None:
                    raise RuntimeError("NotificationRepository does not expose create_notification and _session is not available for fallback insert")
                notif_obj = NotificationModel(
                    user_id=user_id,
                    title=title,
                    sub_type=sub_type,
                    location=location,
                    phone=phone,
                    message=message,
                    timestamp=int(__import__("time").time() * 1000),
                    read=False
                )
                session.add(notif_obj)
                await session.commit()
                await session.refresh(notif_obj)
                notif = notif_obj
        except Exception as e:
            logger.exception("Failed to persist notification for user_id=%s: %s", user_id, e)
            raise

        # 2) If token_repo provided, fetch tokens and send pushes
        push_results: Dict[str, Optional[str]] = {}
        if token_repo:
            try:
                get_tokens = getattr(token_repo, "get_tokens", None) or getattr(token_repo, "get_tokens_by_user", None)
                if get_tokens:
                    # support both async and sync token_repo implementations
                    if asyncio.iscoroutinefunction(get_tokens):
                        tokens = await get_tokens(user_id)
                    else:
                        tokens = await asyncio.to_thread(get_tokens, user_id)
                    if tokens:
                        push_results = await self.send_push_to_many(tokens, title or sub_type, message, data)
                    else:
                        logger.info("No FCM tokens found for user_id=%s", user_id)
                else:
                    logger.warning("token_repo provided but no get_tokens method found")
            except Exception as e:
                logger.exception("Failed to fetch tokens or send pushes for user_id=%s: %s", user_id, e)

        # Return stored notification and push outcomes
        # Convert ORM to dict if it's a SQLAlchemy model (simple mapping)
        notif_out = notif
        try:
            # best-effort mapping to primitive types for JSON-safe return
            notif_out = {
                "id": str(getattr(notif, "id")),
                "user_id": getattr(notif, "user_id"),
                "title": getattr(notif, "title", None),
                "sub_type": getattr(notif, "sub_type", None),
                "location": getattr(notif, "location", None),
                "phone": getattr(notif, "phone", None),
                "message": getattr(notif, "message", None),
                "timestamp": getattr(notif, "timestamp", None),
                "read": getattr(notif, "read", False),
            }
        except Exception:
            # fallback: return the raw object
            logger.debug("Could not convert notif ORM to dict; returning raw object")

        return {"notification": notif_out, "push_results": push_results}
