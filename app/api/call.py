# app/api/calls.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from uuid import uuid4
from typing import Optional
from datetime import datetime, timedelta
import os
import jwt

router = APIRouter(prefix="/calls", tags=["calls"])

# -----------------------------
# Models
# -----------------------------
class CallRequestPayload(BaseModel):
    caller_id: str
    callee_id: str
    call_mode: str  # "voice" or "video"

class SessionResponse(BaseModel):
    session_id: str
    room_name: str
    call_mode: str
    token: Optional[str] = None  # optional JWT for secure Jitsi

# -----------------------------
# Config (replace with env vars)
# -----------------------------
USE_SECURE_JITSI = os.getenv("USE_SECURE_JITSI", "false").lower() == "true"
JITSI_APP_ID = os.getenv("JITSI_APP_ID", "my_app_id")
JITSI_APP_SECRET = os.getenv("JITSI_APP_SECRET", "my_secret")
JITSI_DOMAIN = os.getenv("JITSI_DOMAIN", "meet.yourdomain.com")

# -----------------------------
# Helper: generate JWT for Jitsi
# -----------------------------
def generate_jitsi_token(room_name: str, user_id: str) -> str:
    payload = {
        "aud": "jitsi",
        "iss": JITSI_APP_ID,
        "sub": JITSI_DOMAIN,
        "room": room_name,
        "exp": datetime.utcnow() + timedelta(minutes=60),
        "context": {
            "user": {
                "id": user_id,
                "name": user_id
            }
        }
    }
    token = jwt.encode(payload, JITSI_APP_SECRET, algorithm="HS256")
    return token

# -----------------------------
# Endpoint
# -----------------------------
@router.post("/session", response_model=SessionResponse)
def create_call_session(payload: CallRequestPayload):
    if payload.call_mode not in ["voice", "video"]:
        raise HTTPException(status_code=400, detail="Invalid call_mode, must be 'voice' or 'video'")

    # generate unique session id and room name
    session_id = str(uuid4())
    room_name = f"bloodonal-{session_id}"

    token = None
    if USE_SECURE_JITSI:
        token = generate_jitsi_token(room_name, payload.caller_id)

    return SessionResponse(
        session_id=session_id,
        room_name=room_name,
        call_mode=payload.call_mode,
        token=token
    )
