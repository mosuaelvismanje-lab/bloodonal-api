from __future__ import annotations
import asyncio
import logging
from firebase_admin import messaging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


async def send_push_async(
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Async wrapper for Firebase messaging.
    Uses thread pooling to keep the FastAPI event loop free for signaling.
    """
    try:
        # ✅ Ensure all data values are strings (FCM requirement)
        fcm_data = {k: str(v) for k, v in data.items()} if data else None

        msg = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            token=token,
            data=fcm_data
        )

        # messaging.send is a blocking call; offload to thread
        message_id = await asyncio.to_thread(messaging.send, msg)
        return message_id
    except Exception as e:
        logger.error(f"FCM direct send failed for token {token[:10]}...: {e}")
        return None


async def send_multicast_push_async(
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None
):
    """
    ✅ NEW: Batch notification for multiple donors.
    Highly efficient for regional alerts where many donors match a query.
    """
    if not tokens:
        return

    try:
        fcm_data = {k: str(v) for k, v in data.items()} if data else None

        # Multicast handles up to 500 tokens in a single request
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=fcm_data,
            tokens=tokens,
        )

        response = await asyncio.to_thread(messaging.send_multicast, message)

        logger.info(f"FCM Multicast: {response.success_count} success, {response.failure_count} failure")
        return response
    except Exception as e:
        logger.error(f"FCM Multicast failed: {e}")
        return None


async def send_topic_push_async(
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Broadcasts to a global topic (e.g., 'blood_alerts_southwest').
    """
    try:
        fcm_data = {k: str(v) for k, v in data.items()} if data else None

        msg = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            topic=topic,
            data=fcm_data
        )
        message_id = await asyncio.to_thread(messaging.send, msg)
        return message_id
    except Exception as e:
        logger.error(f"FCM topic send failed for topic {topic}: {e}")
        return None