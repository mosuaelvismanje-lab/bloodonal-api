from __future__ import annotations

import atexit
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import credentials, messaging
from firebase_admin.exceptions import FirebaseError

# =========================================================
# ENV LOAD
# =========================================================
load_dotenv()

logger = logging.getLogger("bloodonal.firebase")

# =========================================================
# RUNTIME STATE
# =========================================================
_firebase_ready: bool = False
_tmp_cred_file: Optional[str] = None

# =========================================================
# CLEANUP
# =========================================================
def _cleanup_tmp_file() -> None:
    """
    Removes temporary Firebase credential files on shutdown.
    """
    global _tmp_cred_file

    if not _tmp_cred_file:
        return

    try:
        if os.path.exists(_tmp_cred_file):
            os.remove(_tmp_cred_file)
            logger.info(
                "Temporary Firebase credential file removed",
            )
    except Exception as exc:
        logger.warning(
            "Failed to remove temporary Firebase credential file: %s",
            exc,
        )
    finally:
        _tmp_cred_file = None


atexit.register(_cleanup_tmp_file)

# =========================================================
# HELPERS
# =========================================================
def is_firebase_ready() -> bool:
    return _firebase_ready


def _sanitize_private_key(value: str) -> str:
    return value.replace("\\n", "\n").strip()


def _build_temp_credential_file(payload: dict[str, Any]) -> Path:
    """
    Create a temporary Firebase service account file.
    Useful for Render/Neon deployments using ENV secrets.
    """
    global _tmp_cred_file

    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    )

    json.dump(payload, tmp, ensure_ascii=False)
    tmp.flush()
    tmp.close()

    _tmp_cred_file = tmp.name

    logger.info(
        "Temporary Firebase credential file created",
    )

    return Path(tmp.name)


def _load_credential_path() -> Optional[Path]:
    """
    Credential resolution priority:

    1. FIREBASE_CREDENTIALS_PATH
    2. GOOGLE_APPLICATION_CREDENTIALS
    3. FIREBASE_CREDENTIALS_JSON
    """

    # =====================================================
    # FILE PATH
    # =====================================================
    firebase_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if firebase_path:
        path = Path(firebase_path)

        if path.exists() and path.is_file():
            logger.info(
                "Using FIREBASE_CREDENTIALS_PATH",
            )
            return path

    # =====================================================
    # GOOGLE APPLICATION CREDENTIALS
    # =====================================================
    google_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if google_path:
        path = Path(google_path)

        if path.exists() and path.is_file():
            logger.info(
                "Using GOOGLE_APPLICATION_CREDENTIALS",
            )
            return path

    # =====================================================
    # RAW JSON ENV
    # =====================================================
    firebase_json = os.getenv("FIREBASE_CREDENTIALS_JSON")

    if firebase_json:
        try:
            payload = json.loads(firebase_json)

            if (
                "private_key" in payload
                and isinstance(payload["private_key"], str)
            ):
                payload["private_key"] = _sanitize_private_key(
                    payload["private_key"]
                )

            return _build_temp_credential_file(payload)

        except Exception as exc:
            logger.exception(
                "Invalid FIREBASE_CREDENTIALS_JSON: %s",
                exc,
            )
            return None

    logger.warning(
        "Firebase credentials not found",
    )

    return None


# =========================================================
# FIREBASE INIT
# =========================================================
def _init_firebase() -> bool:
    """
    Initializes Firebase Admin SDK safely.

    Supports:
    - Local development
    - Render deployment
    - Docker
    - CI/CD pipelines
    """

    global _firebase_ready

    if _firebase_ready:
        return True

    credential_path = _load_credential_path()

    if credential_path is None:
        logger.warning(
            "Firebase initialization skipped: credentials missing",
        )
        return False

    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(str(credential_path))

            firebase_admin.initialize_app(
                cred,
            )

        _firebase_ready = True

        logger.info(
            "Firebase Admin SDK initialized successfully",
        )

        return True

    except Exception as exc:
        logger.exception(
            "Firebase initialization failed: %s",
            exc,
        )

        _firebase_ready = False
        return False


# =========================================================
# INITIALIZE ON IMPORT
# =========================================================
_init_firebase()

# =========================================================
# INTERNAL MESSAGE BUILDERS
# =========================================================
def _sanitize_data(
    data: Optional[dict[str, Any]],
) -> dict[str, str]:
    """
    Firebase requires all custom payload values to be strings.
    """
    if not data:
        return {}

    return {
        str(key): str(value)
        for key, value in data.items()
        if value is not None
    }


def _android_config(
    channel_id: str = "blood_requests_channel",
) -> messaging.AndroidConfig:
    return messaging.AndroidConfig(
        priority="high",
        ttl=60 * 60 * 1000,
        notification=messaging.AndroidNotification(
            sound="default",
            channel_id=channel_id,
            click_action="FLUTTER_NOTIFICATION_CLICK",
        ),
    )


def _apns_config() -> messaging.APNSConfig:
    return messaging.APNSConfig(
        payload=messaging.APNSPayload(
            aps=messaging.Aps(
                sound="default",
                badge=1,
                content_available=True,
            ),
        ),
    )


def _build_message(
    *,
    target: str,
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
    topic: bool = False,
) -> messaging.Message:
    payload = {
        "notification": messaging.Notification(
            title=title,
            body=body,
        ),
        "data": _sanitize_data(data),
        "android": _android_config(),
        "apns": _apns_config(),
    }

    if topic:
        return messaging.Message(
            topic=target,
            **payload,
        )

    return messaging.Message(
        token=target,
        **payload,
    )


# =========================================================
# PUBLIC FCM SENDERS
# =========================================================
def send_fcm_to_device(
    *,
    token: str,
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    """
    Send push notification to a single device token.
    """

    if not token.strip():
        logger.warning("FCM token missing")
        return None

    if not _firebase_ready and not _init_firebase():
        logger.error("Firebase not initialized")
        return None

    try:
        message = _build_message(
            target=token,
            title=title,
            body=body,
            data=data,
            topic=False,
        )

        message_id = messaging.send(message)

        logger.info(
            "FCM notification sent to device: %s",
            token[:12],
        )

        return message_id

    except messaging.UnregisteredError:
        logger.warning(
            "Invalid/unregistered FCM token: %s",
            token[:12],
        )

        # =================================================
        # OPTIONAL:
        # Remove token from DB here
        # =================================================
        return "UNREGISTERED"

    except FirebaseError as exc:
        logger.error(
            "Firebase messaging error: %s",
            exc,
        )
        return None

    except Exception as exc:
        logger.exception(
            "Unexpected FCM error: %s",
            exc,
        )
        return None


def send_fcm_to_topic(
    *,
    topic: str,
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    """
    Send push notification to a Firebase topic.
    """

    if not topic.strip():
        logger.warning("FCM topic missing")
        return None

    if not _firebase_ready and not _init_firebase():
        logger.error("Firebase not initialized")
        return None

    try:
        message = _build_message(
            target=topic,
            title=title,
            body=body,
            data=data,
            topic=True,
        )

        message_id = messaging.send(message)

        logger.info(
            "FCM topic notification sent: %s",
            topic,
        )

        return message_id

    except FirebaseError as exc:
        logger.error(
            "Topic messaging failed: %s",
            exc,
        )
        return None

    except Exception as exc:
        logger.exception(
            "Unexpected topic FCM error: %s",
            exc,
        )
        return None


# =========================================================
# LEGACY COMPATIBILITY WRAPPER
# =========================================================
def send_fcm_to_donor(
    target: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> Optional[str]:
    """
    Backward-compatible wrapper.

    Existing modules can continue using:
    send_fcm_to_donor(...)
    """

    if target == "donation":
        return send_fcm_to_topic(
            topic="donation",
            title=title,
            body=body,
            data=data,
        )

    return send_fcm_to_device(
        token=target,
        title=title,
        body=body,
        data=data,
    )