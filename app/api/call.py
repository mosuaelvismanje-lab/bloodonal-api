from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from uuid import uuid4, UUID
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import os
import jwt
import logging

from app.db.session import get_db
from app.models.call_session import CallSession, CallStatus, CallMode
from app.schemas.calls import CallInitiatePayload, CallSessionResponse, CallStatusUpdate

# Logging setup
log = logging.getLogger("bloodonal")

router = APIRouter(prefix="/calls", tags=["calls"])

# -----------------------------
# Configuration (2026 Standards)
# -----------------------------
USE_SECURE_JITSI = os.getenv("USE_SECURE_JITSI", "true").lower() == "true"
JITSI_APP_ID = os.getenv("JITSI_APP_ID", "bloodonal_prod_2026")
JITSI_APP_SECRET = os.getenv("JITSI_APP_SECRET", "change_this_in_production")
JITSI_DOMAIN = os.getenv("JITSI_DOMAIN", "meet.bloodonal.org")


# -----------------------------
# Helpers
# -----------------------------
def generate_jitsi_token(room_name: str, user_id: str) -> str:
    """Generates a JWT token for secure Jitsi Meet authentication."""
    payload = {
        "aud": "jitsi",
        "iss": JITSI_APP_ID,
        "sub": JITSI_DOMAIN,
        "room": room_name,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        "context": {
            "user": {
                "id": user_id,
                "name": f"User_{user_id[:8]}"
            },
            "features": {
                "recording": "true",
                "livestreaming": "false"
            }
        }
    }
    return jwt.encode(payload, JITSI_APP_SECRET, algorithm="HS256")


# -----------------------------
# Endpoints
# -----------------------------

@router.post("/initiate", response_model=CallSessionResponse, status_code=status.HTTP_201_CREATED)
async def initiate_call(
        payload: CallInitiatePayload,
        db: AsyncSession = Depends(get_db)
):
    """
    Step 1: Initiates a call session.
    Creates a database record and returns Jitsi credentials to the Android caller.
    """
    # 1. Generate Session Identity
    session_id = uuid4()
    room_name = f"bloodonal_{uuid4().hex[:12]}"

    # 2. Secure Token Generation
    token = None
    if USE_SECURE_JITSI:
        token = generate_jitsi_token(room_name, payload.caller_id)

    # 3. Persist to Database (SQLAlchemy 2.0)
    new_session = CallSession(
        id=session_id,
        room_name=room_name,
        caller_id=payload.caller_id,
        callee_id=payload.callee_id,
        callee_type=payload.callee_type,
        call_mode=payload.call_mode,
        status=CallStatus.INITIATED,
        token=token
    )

    try:
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)

        # 🚀 2026 TODO: Trigger Firebase Cloud Messaging (FCM) here
        # signaling_service.send_ring_notification(payload.callee_id, session_id)

        log.info(f"📞 Call initiated: {session_id} between {payload.caller_id} and {payload.callee_id}")

        return new_session
    except Exception as e:
        await db.rollback()
        log.error(f"❌ Failed to initiate call: {e}")
        raise HTTPException(status_code=500, detail="Could not create call session.")


@router.patch("/{session_id}/status", response_model=CallSessionResponse)
async def update_call_status(
        session_id: UUID,
        payload: CallStatusUpdate,
        db: AsyncSession = Depends(get_db)
):
    """
    Step 2: Updates the call status (ongoing, completed, rejected).
    Handles duration calculation automatically on completion.
    """
    # 1. Fetch Session
    result = await db.execute(select(CallSession).where(CallSession.id == session_id))
    call_session = result.scalar_one_or_none()

    if not call_session:
        raise HTTPException(status_code=404, detail="Call session not found")

    # 2. Logic: Handle status transitions
    if payload.status == CallStatus.ONGOING and not call_session.started_at:
        call_session.started_at = datetime.now(timezone.utc)

    if payload.status in [CallStatus.COMPLETED, CallStatus.REJECTED, CallStatus.FAILED]:
        call_session.finalize_call()  # Uses the helper logic we wrote in the model

    call_session.status = payload.status

    if payload.session_metadata:
        call_session.session_metadata = payload.session_metadata

    try:
        await db.commit()
        await db.refresh(call_session)
        return call_session
    except Exception as e:
        await db.rollback()
        log.error(f"❌ Status update failed for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Update failed")


@router.get("/{session_id}", response_model=CallSessionResponse)
async def get_call_details(session_id: UUID, db: AsyncSession = Depends(get_db)):
    """Fetches full details of a specific call session for history or billing."""
    result = await db.execute(select(CallSession).where(CallSession.id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session