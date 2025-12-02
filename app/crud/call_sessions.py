# app/crud/call_sessions.py
import uuid
import secrets
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.call_session import CallSession, CallMode, CallStatus


async def create_call_session(
    db: AsyncSession,
    caller_id: str,
    recipient_ids: Optional[List[str]],
    callee_type: Optional[str],
    call_mode: CallMode,
    metadata: Optional[dict] = None,
    jitsi_room_prefix: str = "bloodonal"
) -> CallSession:
    session_uuid = uuid.uuid4().hex
    room_name = f"{jitsi_room_prefix}-{session_uuid}"
    token = secrets.token_urlsafe(32)  # placeholder token if you need one

    cs = CallSession(
        session_id=session_uuid,
        room_name=room_name,
        caller_id=caller_id,
        callee_ids=recipient_ids or ([] if recipient_ids is not None else None),
        callee_type=callee_type,
        call_mode=call_mode,
        token=token,
        status=CallStatus.ACTIVE
    )

    db.add(cs)
    await db.commit()
    await db.refresh(cs)
    return cs


async def end_call_session(
    db: AsyncSession,
    session_id: str,
    ended_by: Optional[str] = None,
    reason: Optional[str] = None
) -> Optional[CallSession]:
    q = await db.execute(select(CallSession).where(CallSession.session_id == session_id))
    cs = q.scalars().first()
    if not cs:
        return None
    cs.status = CallSession.status.type.enum_class.ENDED if hasattr(CallSession, "status") else "ended"
    from datetime import datetime
    cs.ended_at = datetime.utcnow()
    await db.commit()
    await db.refresh(cs)
    return cs
