import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Project Dependencies
from app.api.dependencies import get_db, get_current_user
from app.schemas.call import (
    CallInitiatePayload,    # Matches your updated schema
    CallStatusUpdate,       # Maps to end_session/status logic
    CallSessionResponse     # Matches your updated schema
)
from app.crud.call_sessions import create_call_session, end_call_session
from app.models.call_session import CallMode

logger = logging.getLogger(__name__)

# ✅ Versioning: Prefix set to /v1 to match production API layout
router = APIRouter(prefix="/calls", tags=["calls"])

# -------------------------------------------------
# INTERNAL FACTORY: Consolidate Session Creation
# -------------------------------------------------
async def _handle_session_creation(
    db: AsyncSession,
    user_uid: str,
    payload: CallInitiatePayload,
    mode: CallMode
) -> CallSessionResponse:
    """Helper to maintain DRY principle across call modes."""
    try:
        # Note: Ensure create_call_session handles the new schema structure
        cs = await create_call_session(
            db=db,
            caller_id=user_uid,
            callee_id=payload.callee_id,
            callee_type=payload.callee_type,
            call_mode=mode,
            session_metadata=payload.session_metadata
        )
        await db.commit()
        return CallSessionResponse.model_validate(cs)
    except Exception as e:
        await db.rollback()
        logger.error(f"Session creation failed: {e}")
        raise HTTPException(status_code=500, detail="Could not initiate session")

# -------------------------------------------------
# ENDPOINTS
# -------------------------------------------------

@router.post("/session", response_model=CallSessionResponse)
async def create_session(
        payload: CallInitiatePayload,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Creates a generic session, defaulting to the mode provided in payload."""
    mode = CallMode(payload.call_mode.lower())
    return await _handle_session_creation(db, current_user.uid, payload, mode)

@router.post("/session/voice", response_model=CallSessionResponse)
async def create_voice_session(
        payload: CallInitiatePayload,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    return await _handle_session_creation(db, current_user.uid, payload, CallMode.VOICE)

@router.post("/session/video", response_model=CallSessionResponse)
async def create_video_session(
        payload: CallInitiatePayload,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    return await _handle_session_creation(db, current_user.uid, payload, CallMode.VIDEO)

@router.post("/session/end", status_code=status.HTTP_200_OK)
async def end_session(
        request: CallStatusUpdate,
        session_id: str,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Terminates an active session."""
    cs = await end_call_session(
        db,
        session_id,
        ended_by=current_user.uid,
        reason=request.status # Using status field as reason for closure
    )
    if not cs:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.commit()
    return {"ok": True, "session_id": cs.session_id, "ended_at": cs.ended_at}