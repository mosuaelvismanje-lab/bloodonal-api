# File: app/firebase_client.py
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from app.config import settings

cred_path = settings.GOOGLE_CREDENTIALS_PATH  # <- use correct property

if not cred_path or not cred_path.is_file():
    raise RuntimeError(f"Missing or invalid GOOGLE_APPLICATION_CREDENTIALS: {cred_path!r}")

if not firebase_admin._apps:
    cred = credentials.Certificate(str(cred_path))
    firebase_admin.initialize_app(cred)

db = firestore.client()

def send_fcm_to_donor(
    fcm_token: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> str | None:
    message = messaging.Message(
        token=fcm_token,
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
    )
    try:
        return messaging.send(message)
    except Exception as e:
        print(f"Failed to send FCM to {fcm_token}: {e}")
        return None
