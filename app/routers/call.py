import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

# ✅ Production Standard: Use unified dependencies and security
from app.api.dependencies import get_db_session, get_current_user
from app.schemas.call import (
    CallRequestPayload,
    InitiateCallRequest,
    EndCallRequest,
    SessionResponse
)
from app.crud.call_sessions import create_call_session, end_call_session
from app.models.call_session import CallMode

logger = logging.getLogger(__name__)

# ✅ Versioning: Prefix set to /v1 to match production API layout
router = APIRouter(prefix="/v1/calls", tags=["calls"])


# -------------------------------------------------
# CREATE GENERIC SESSION
# -------------------------------------------------
@router.post("/session", response_model=SessionResponse)
async def create_session(
        payload: CallRequestPayload,
        db: AsyncSession = Depends(get_db_session),
        current_user=Depends(get_current_user)  # ✅ Secure: Token required
):
    """
    Creates a new communication session.
    Identity is strictly enforced via the authenticated token.
    """
    # Normalize recipients
    recipient_ids = payload.recipient_ids
    if not recipient_ids and payload.callee_id:
        recipient_ids = [payload.callee_id]

    # Normalize call mode
    call_mode = CallMode(payload.call_mode.lower()) if payload.call_mode else CallMode.VIDEO

    try:
        cs = await create_call_session(
            db=db,
            caller_id=current_user.uid,  # ✅ Security: Override payload with verified UID
            recipient_ids=recipient_ids,
            callee_type=payload.callee_type,
            call_mode=call_mode,
            session_metadata=payload.session_metadata
        )
        await db.commit()
        return SessionResponse.model_validate(cs)
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create call session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not initiate call session"
        )


# -------------------------------------------------
# CREATE VOICE SESSION
# -------------------------------------------------
@router.post("/session/voice", response_model=SessionResponse)
async def create_voice_session(
        request: InitiateCallRequest,
        db: AsyncSession = Depends(get_db_session),
        current_user=Depends(get_current_user)
):
    recipient_ids = request.recipient_ids or []

    try:
        cs = await create_call_session(
            db=db,
            caller_id=current_user.uid,  # ✅ Use verified ID
            recipient_ids=recipient_ids,
            callee_type=request.callee_type,
            call_mode=CallMode.VOICE,
            session_metadata=request.session_metadata
        )
        await db.commit()
        return SessionResponse.model_validate(cs)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------------------------
# CREATE VIDEO SESSION
# -------------------------------------------------
@router.post("/session/video", response_model=SessionResponse)
async def create_video_session(
        request: InitiateCallRequest,
        db: AsyncSession = Depends(get_db_session),
        current_user=Depends(get_current_user)
):
    recipient_ids = request.recipient_ids or []

    try:
        cs = await create_call_session(
            db=db,
            caller_id=current_user.uid,
            recipient_ids=recipient_ids,
            callee_type=request.callee_type,
            call_mode=CallMode.VIDEO,
            session_metadata=request.session_metadata
        )
        await db.commit()
        return SessionResponse.model_validate(cs)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------------------------
# END SESSION
# -------------------------------------------------
@router.post("/session/end", status_code=status.HTTP_200_OK)
async def end_session(
        request: EndCallRequest,
        db: AsyncSession = Depends(get_db_session),
        current_user=Depends(get_current_user)
):
    """
    Terminates an active session. Authenticates the person ending the call.
    """
    cs = await end_call_session(
        db,
        request.session_id,
        ended_by=current_user.uid,  # ✅ Track who actually hung up
        reason=request.reason
    )

    if not cs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    await db.commit()
    return {"ok": True, "session_id": cs.session_id, "ended_at": cs.ended_at}