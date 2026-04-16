from __future__ import annotations

import os
import json
import logging
import tempfile
import atexit
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

import firebase_admin
from firebase_admin import credentials, messaging
from firebase_admin.exceptions import FirebaseError

# Force load the .env file at the very start
load_dotenv()

logger = logging.getLogger("uvicorn.error")

# Runtime state
_firebase_ready = False
_tmp_cred_file: Optional[str] = None

def _cleanup_tmp_file():
    """Removes the temporary JSON credential file on application shutdown."""
    global _tmp_cred_file
    if _tmp_cred_file and os.path.exists(_tmp_cred_file):
        try:
            os.remove(_tmp_cred_file)
            logger.info("🧹 Cleaned up temporary Firebase credentials file.")
        except Exception as e:
            logger.error("❌ Failed to delete temp Firebase file: %s", e)

# Register the cleanup handler
atexit.register(_cleanup_tmp_file)

def _load_credential_path() -> Optional[Path]:
    """
    Priority:
    1. FIREBASE_CREDENTIALS_PATH
    2. GOOGLE_APPLICATION_CREDENTIALS
    3. FIREBASE_CREDENTIALS_JSON (Raw string from Env)
    """
    path_str = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if path_str and Path(path_str).is_file():
        return Path(path_str)

    path_str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if path_str and Path(path_str).is_file():
        return Path(path_str)

    json_env = os.getenv("FIREBASE_CREDENTIALS_JSON")
    if json_env:
        try:
            cred_obj = json.loads(json_env)
            # Fix newline issues common in private keys stored in env variables
            if "private_key" in cred_obj and isinstance(cred_obj["private_key"], str):
                cred_obj["private_key"] = cred_obj["private_key"].replace("\\n", "\n")

            tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json", encoding="utf-8")
            json.dump(cred_obj, tmp, ensure_ascii=False)
            tmp.flush()
            tmp.close()
            global _tmp_cred_file
            _tmp_cred_file = tmp.name
            return Path(tmp.name)
        except Exception:
            logger.exception("FIREBASE_CREDENTIALS_JSON is invalid.")
            return None

    return None

def _init_firebase() -> bool:
    """Initialize firebase admin SDK with singleton check."""
    global _firebase_ready
    if _firebase_ready:
        return True

    cred_path = _load_credential_path()
    if not cred_path:
        logger.warning("⚠️ Firebase credentials not found. FCM operations will fail.")
        return False

    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(str(cred_path))
            firebase_admin.initialize_app(cred)

        _firebase_ready = True
        logger.info("🚀 Firebase Admin SDK initialized from %s", cred_path)
        return True
    except Exception as exc:
        logger.exception("🔥 Failed to initialize Firebase: %s", exc)
        return False

# Initialize on module load
_init_firebase()

def send_fcm_to_donor(
        target: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
) -> Optional[str]:
    """
    Synchronous FCM wrapper for BackgroundTasks.
    Handles both specific device tokens and the 'donation' topic.
    """
    if not _firebase_ready and not _init_firebase():
        return None

    # Standardize data to strings for FCM
    sanitized_data = {k: str(v) for k, v in (data or {}).items()}

    # Android: High priority ensures delivery in Doze/Battery saving mode
    android_config = messaging.AndroidConfig(
        priority='high',
        notification=messaging.AndroidNotification(
            click_action='FLUTTER_NOTIFICATION_CLICK',
            channel_id='blood_requests_channel', # Must match mobile app channel ID
            sound='default'
        )
    )

    # iOS: Content-available=True allows background processing
    apns_config = messaging.APNSConfig(
        payload=messaging.APNSPayload(
            aps=messaging.Aps(sound='default', badge=1, content_available=True)
        )
    )

    # Construct Message
    message_params = {
        "notification": messaging.Notification(title=title, body=body),
        "data": sanitized_data,
        "android": android_config,
        "apns": apns_config
    }

    if target == "donation":
        message = messaging.Message(topic="donation", **message_params)
    else:
        message = messaging.Message(token=target, **message_params)

    try:
        msg_id = messaging.send(message)
        logger.info("📨 FCM Sent [%s] -> %s", msg_id, target[:10])
        return msg_id
    except messaging.UnregisteredError:
        # ✅ Production Hook: Token is invalid (User uninstalled app)
        # In a full service, we would call a CRUD function here to delete this token.
        logger.warning("⚠️ Token '%s...' is invalid. Should be purged from DB.", target[:10])
        return "DELETED"
    except Exception as e:
        logger.error("❌ FCM Error for target %s: %s", target[:10], e)
        return None