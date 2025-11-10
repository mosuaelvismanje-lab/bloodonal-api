# app/firebase_client.py
import os
import json
import logging
import tempfile
from pathlib import Path
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore, messaging
from firebase_admin.exceptions import FirebaseError

logger = logging.getLogger("uvicorn.error")

# Runtime state
_firebase_ready = False
_tmp_cred_file: Optional[str] = None  # path to temp file when using FIREBASE_CREDENTIALS_JSON


def _load_credential_path() -> Optional[Path]:
    """
    Try in this order:
      1. FIREBASE_CREDENTIALS_PATH (mounted file path, e.g. /etc/secrets/firebase.json)
      2. GOOGLE_APPLICATION_CREDENTIALS (legacy env)
      3. FIREBASE_CREDENTIALS_JSON (JSON string in env -> write to temp file and return path)
    Returns a Path to an existing JSON file, or None.
    """
    # 1) explicit path (recommended on Render)
    path_str = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if path_str:
        p = Path(path_str)
        if p.is_file():
            logger.debug("Using Firebase credentials file from FIREBASE_CREDENTIALS_PATH=%s", path_str)
            return p
        logger.warning("FIREBASE_CREDENTIALS_PATH set but file missing: %s", path_str)

    # 2) legacy GOOGLE_APPLICATION_CREDENTIALS
    path_str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if path_str:
        p = Path(path_str)
        if p.is_file():
            logger.debug("Using Firebase credentials file from GOOGLE_APPLICATION_CREDENTIALS=%s", path_str)
            return p
        logger.warning("GOOGLE_APPLICATION_CREDENTIALS set but file missing: %s", path_str)

    # 3) JSON string in env (Render secret as env string) - convert to temp file
    json_env = os.getenv("FIREBASE_CREDENTIALS_JSON")
    if json_env:
        try:
            # If the JSON came in with escaped newlines in the private_key (\\n),
            # convert them to real newlines before loading JSON.
            # Also allow it to be already a dict-like string.
            # Some callers may pass a single-line JSON with literal \n sequences.
            # Replace double-escaped newlines with real newlines AFTER parsing, to be safe.
            # First parse the JSON string (it might already use real newlines).
            cred_obj = json.loads(json_env)
            # Fix private_key if it has escaped backslash-n (literal backslash + n)
            if "private_key" in cred_obj and isinstance(cred_obj["private_key"], str):
                cred_obj["private_key"] = cred_obj["private_key"].replace("\\n", "\n")
        except Exception as exc:
            # If json.loads fails (maybe because the env var is not well-formed), try simple replace and retry
            try:
                cleaned = json_env.replace("\\n", "\n")
                cred_obj = json.loads(cleaned)
            except Exception:
                logger.exception("FIREBASE_CREDENTIALS_JSON is present but is not valid JSON.")
                return None

        # Write to a temp file for firebase_admin to consume
        try:
            tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json", encoding="utf-8")
            json.dump(cred_obj, tmp, ensure_ascii=False)
            tmp.flush()
            tmp.close()
            global _tmp_cred_file
            _tmp_cred_file = tmp.name
            logger.debug("Wrote Firebase credentials JSON to temp file %s", tmp.name)
            return Path(tmp.name)
        except Exception:
            logger.exception("Failed to write FIREBASE_CREDENTIALS_JSON to temp file.")
            return None

    # nothing found
    return None


def _init_firebase() -> bool:
    """Initialize firebase admin SDK if credentials available. Return True on success."""
    global _firebase_ready
    if _firebase_ready:
        return True

    cred_path = _load_credential_path()
    if not cred_path:
        logger.info("Firebase credentials not configured. Skipping Firebase initialization.")
        return False

    try:
        cred = credentials.Certificate(str(cred_path))
        firebase_admin.initialize_app(cred)
        # optionally warm Firestore client to catch errors early
        try:
            _ = firestore.client()
        except Exception:
            logger.exception("Firestore client creation failed after Firebase init — continuing.")
        _firebase_ready = True
        logger.info("Firebase Admin SDK initialized from %s", cred_path)
        return True
    except Exception as exc:
        logger.exception("Failed to initialize Firebase Admin SDK from %s: %s", cred_path, exc)
        return False


# Attempt initialization now but do not raise
_init_firebase()


def send_fcm_to_donor(
    fcm_token: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> Optional[str]:
    """
    Send a push notification via FCM. Returns the message ID on success, None on failure/disabled.
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
