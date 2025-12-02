# app/api/routers/calls.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app.schemas.calls import CallRequestPayload, InitiateCallRequest, EndCallRequest, SessionResponse
from app.crud.call_sessions import create_call_session, end_call_session
from app.models.call_session import CallMode
from app.db.session import get_db  # your project's DB dependency

router = APIRouter(prefix="/calls", tags=["calls"])


@router.post("/session", response_model=SessionResponse)
async def create_session(payload: CallRequestPayload, db: AsyncSession = Depends(get_db)):
    # normalize recipients
    recipient_ids = payload.recipient_ids
    if not recipient_ids and payload.callee_id:
        recipient_ids = [payload.callee_id]

    # normalize call mode
    call_mode = CallMode(payload.call_mode.lower()) if payload.call_mode else CallMode.VIDEO

    cs = await create_call_session(
        db=db,
        caller_id=payload.caller_id,
        recipient_ids=recipient_ids,
        callee_type=payload.callee_type,
        call_mode=call_mode,
        metadata=payload.metadata
    )

    return SessionResponse(
        session_id=cs.session_id,
        room_name=cs.room_name,
        token=cs.token,
        call_mode=cs.call_mode.value,
        status=cs.status.value if hasattr(cs.status, "value") else str(cs.status),
        started_at=cs.started_at
    )


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
        metadata=request.metadata
    )
    return SessionResponse(
        session_id=cs.session_id,
        room_name=cs.room_name,
        token=cs.token,
        call_mode=cs.call_mode.value,
        status=cs.status.value,
        started_at=cs.started_at
    )


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
        metadata=request.metadata
    )
    return SessionResponse(
        session_id=cs.session_id,
        room_name=cs.room_name,
        token=cs.token,
        call_mode=cs.call_mode.value,
        status=cs.status.value,
        started_at=cs.started_at
    )


@router.post("/session/end", status_code=200)
async def end_session(request: EndCallRequest, db: AsyncSession = Depends(get_db)):
    cs = await end_call_session(db, request.session_id, ended_by=request.ended_by, reason=request.reason)
    if not cs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return {"ok": True, "session_id": cs.session_id, "ended_at": cs.ended_at}
