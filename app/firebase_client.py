# File: app/firebase_client.py
"""
Firebase helper for server-side FCM & Firestore access.
Compatible with Python 2.7 (no pathlib usage).
"""
import logging
import os

import firebase_admin
from firebase_admin import credentials, firestore, messaging
from firebase_admin.exceptions import FirebaseError

from app.config import settings

logger = logging.getLogger("uvicorn.error")

# Path as string or None
_cred_path = settings.GOOGLE_APPLICATION_CREDENTIALS

# runtime flag
_firebase_ready = False

def _init_firebase():
    """Attempt to initialize Firebase Admin SDK. Return True on success."""
    global _firebase_ready
    if _firebase_ready:
        return True

    if not _cred_path:
        logger.warning(
            "Firebase credentials not configured (GOOGLE_APPLICATION_CREDENTIALS is None). Firebase disabled."
        )
        return False

    if not os.path.isfile(_cred_path):
        logger.warning("Firebase credentials file does not exist at %s. Firebase disabled.", _cred_path)
        return False

    try:
        cred = credentials.Certificate(_cred_path)

        # initialize_app only if no app exists
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized from %s", _cred_path)
        else:
            logger.debug("Firebase Admin SDK already initialized; skipping.")

        # try creating Firestore client
        try:
            _ = firestore.client()
        except Exception:
            logger.exception("Firestore client creation failed after Firebase init — continuing without Firestore.")

        _firebase_ready = True
        return True
    except Exception as exc:
        logger.exception("Failed to initialize Firebase Admin SDK: %s", exc)
        return False

# Try to initialize at import, do NOT raise
_init_firebase()

def send_fcm_to_donor(fcm_token, title, body, data=None):
    """
    Send a push notification via FCM.

    Returns:
        message id (str) on success, or None if Firebase is not configured or sending failed.
    """
    if not _firebase_ready and not _init_firebase():
        logger.warning("send_fcm_to_donor skipped: Firebase not configured.")
        return None

    message = messaging.Message(
        token=fcm_token,
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
    )

    try:
        msg_id = messaging.send(message)
        logger.debug("FCM sent to %s, message_id=%s", fcm_token, msg_id)
        return msg_id
    except FirebaseError as e:
        logger.exception("Failed to send FCM to %s: %s", fcm_token, e)
        return None
    except Exception as e:
        logger.exception("Unexpected error sending FCM to %s: %s", fcm_token, e)
        return None
