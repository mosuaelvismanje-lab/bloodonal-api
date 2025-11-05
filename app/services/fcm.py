# app/services/fcm.py

import firebase_admin
from firebase_admin import messaging

# (Assumes you already initialized firebase_admin in main.py at import time)

def send_push(token: str, title: str, body: str) -> str:
    """
    Send a Firebase push notification to the given FCM registration token.
    Returns the FCM message ID on success.
    """
    msg = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        token=token
    )
    return messaging.send(msg)
