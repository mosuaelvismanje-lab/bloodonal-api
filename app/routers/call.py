from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

# Ensure the import matches your updated schema filename (calls.py)
from app.schemas.call import CallRequestPayload, InitiateCallRequest, EndCallRequest, SessionResponse
from app.crud.call_sessions import create_call_session, end_call_session
from app.models.call_session import CallMode
from app.db.session import get_db

router = APIRouter(prefix="/calls", tags=["calls"])


@router.post("/session", response_model=SessionResponse)
async def create_session(payload: CallRequestPayload, db: AsyncSession = Depends(get_db)):
    # Normalize recipients
    recipient_ids = payload.recipient_ids
    if not recipient_ids and payload.callee_id:
        recipient_ids = [payload.callee_id]

    # Normalize call mode
    call_mode = CallMode(payload.call_mode.lower()) if payload.call_mode else CallMode.VIDEO

    # We use session_metadata to match our updated Model and Schema
    cs = await create_call_session(
        db=db,
        caller_id=payload.caller_id,
        recipient_ids=recipient_ids,
        callee_type=payload.callee_type,
        call_mode=call_mode,
        session_metadata=payload.session_metadata
    )

    # In Pydantic V2, model_validate() automatically converts
    # the SQLAlchemy object into the schema using from_attributes=True
    return SessionResponse.model_validate(cs)


@router.post("/session/voice", response_model=SessionResponse)
async def create_voice_session(request: InitiateCallRequest, db: AsyncSession = Depends(get_db)):
    recipient_ids = request.recipient_ids or []
    call_mode = CallMode.VOICE

    cs = await create_call_session(
        db=db,
        caller_id=request.caller_id,
        recipient_ids=recipient_ids,
        callee_type=request.callee_type,
        call_mode=call_mode,
        session_metadata=request.session_metadata
    )
    return SessionResponse.model_validate(cs)


@router.post("/session/video", response_model=SessionResponse)
async def create_video_session(request: InitiateCallRequest, db: AsyncSession = Depends(get_db)):
    recipient_ids = request.recipient_ids or []
    call_mode = CallMode.VIDEO

    cs = await create_call_session(
        db=db,
        caller_id=request.caller_id,
        recipient_ids=recipient_ids,
        callee_type=request.callee_type,
        call_mode=call_mode,
        session_metadata=request.session_metadata
    )
    return SessionResponse.model_validate(cs)


@router.post("/session/end", status_code=200)
async def end_session(request: EndCallRequest, db: AsyncSession = Depends(get_db)):
    cs = await end_call_session(
        db,
        request.session_id,
        ended_by=request.ended_by,
        reason=request.reason
    )

    if not cs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    return {"ok": True, "session_id": cs.session_id, "ended_at": cs.ended_at}