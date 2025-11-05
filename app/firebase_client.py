# File: app/services/firebase_app.py
import os
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from firebase_admin.exceptions import FirebaseError
from app.config import settings

cred_path = settings.GOOGLE_APPLICATION_CREDENTIALS
if not cred_path or not os.path.isfile(cred_path):
    raise RuntimeError(f"Missing or invalid GOOGLE_APPLICATION_CREDENTIALS: {cred_path!r}")

if not firebase_admin._apps:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()  # for Firestore if you ever need it

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
    except FirebaseError as e:
        # Replace with real logging
        print(f"Failed to send FCM to {fcm_token!r}: {e}")
        return None
