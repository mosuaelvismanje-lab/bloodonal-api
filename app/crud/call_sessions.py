import uuid
import secrets
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

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
    """
    Creates a new CallSession using AsyncSession.
    """
    session_uuid = uuid.uuid4().hex
    room_name = f"{jitsi_room_prefix}-{session_uuid}"
    token = secrets.token_urlsafe(32)

    cs = CallSession(
        session_id=session_uuid,
        room_name=room_name,
        caller_id=caller_id,
        # Ensure it's a list for JSON compatibility in PostgreSQL
        callee_ids=recipient_ids if recipient_ids is not None else [],
        callee_type=callee_type,
        call_mode=call_mode,
        token=token,
        status=CallStatus.ACTIVE  # ✅ Direct Enum usage
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
    """
    Finds and marks a call session as ended.
    """
    # 1. Fetch the session using the async select pattern
    result = await db.execute(
        select(CallSession).where(CallSession.session_id == session_id)
    )
    cs = result.scalars().first()

    if not cs:
        return None

    # 2. Update Status and Timestamp
    # ✅ Using the Enum class directly is safer than complex introspection
    cs.status = CallStatus.ENDED

    # ✅ datetime.utcnow() is deprecated; use timezone-aware now()
    cs.ended_at = datetime.now(timezone.utc)

    # 3. Commit and Refresh
    await db.commit()
    await db.refresh(cs)
    return cs
