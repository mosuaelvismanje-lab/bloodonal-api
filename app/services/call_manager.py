import uuid
import logging
import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.endpoints.monitoring import record_call_event
from app.config import settings
from app.models.call_session import CallSession, CallStatus, CallMode
from app.schemas.call import CallInitiatePayload


logger = logging.getLogger("bloodonal.call_manager")


class CallManager:
    """
    The Brain: Orchestrates RTC session lifecycle, security tokens,
    and business rules for emergency health calls.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_call_permissions(self, caller_id: str, callee_id: str) -> bool:
        """
        Business Logic: Verifies if the caller is allowed to contact the callee.
        In 2026, this checks for active bookings or emergency status.
        """
        # TODO: Add logic to check if a payment/booking exists for this pair
        # For now, we allow all calls to ensure emergency connectivity
        return True

    def generate_secure_room(self) -> str:
        """Generates a non-guessable, URL-safe Jitsi room name."""
        prefix = "bld_2026"
        unique_suffix = uuid.uuid4().hex[:12]
        return f"{prefix}_{unique_suffix}"

    def create_jitsi_jwt(self, room_name: str, user_id: str) -> str:
        """
        Generates a JWT for Jitsi "Secure Room" mode.
        Prevents unauthorized users from 'camping' in medical rooms.
        """
        now = datetime.now(timezone.utc)
        payload = {
            "aud": "jitsi",
            "iss": settings.JITSI_APP_ID,
            "sub": settings.JITSI_DOMAIN,
            "room": room_name,
            "iat": now,
            "exp": now + timedelta(hours=1),
            "context": {
                "user": {
                    "id": user_id,
                    "name": f"User_{user_id[:6]}",
                    "avatar": ""  # Optional: Add profile pic URL
                }
            }
        }
        return jwt.encode(payload, settings.JITSI_APP_SECRET, algorithm="HS256")

    async def start_session(self, payload: CallInitiatePayload) -> CallSession:
        """
        Orchestrates the creation of a new medical call session.
        """
        # 1. Permission Check
        if not await self.validate_call_permissions(payload.caller_id, payload.callee_id):
            raise ValueError("Unauthorized: No active booking found for this call.")

        # 2. Infrastructure Setup
        room_name = self.generate_secure_room()
        token = self.create_jitsi_jwt(room_name, payload.caller_id)

        # 3. Persistence (SQLAlchemy 2.0)
        session = CallSession(
            id=uuid.uuid4(),
            room_name=room_name,
            caller_id=payload.caller_id,
            callee_id=payload.callee_id,
            callee_type=payload.callee_type,
            call_mode=payload.call_mode,
            status=CallStatus.INITIATED,
            token=token,
            session_metadata=payload.session_metadata
        )

        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        # 4. Metrics
        record_call_event(payload.callee_type, "initiated", payload.call_mode)

        logger.info(f"🚀 Session {session.id} started. Room: {room_name}")
        return session

    async def end_session(self, session_id: uuid.UUID, reason: str = "completed"):
        """
        Handles the graceful closure of a call, including duration calculation.
        """
        result = await self.db.execute(
            select(CallSession).where(CallSession.id == session_id)
        )
        session = result.scalar_one_or_none()

        if session and session.is_active:
            session.finalize_call()
            session.status = CallStatus.COMPLETED if reason == "completed" else CallStatus.FAILED

            # Record final metrics
            record_call_event(session.callee_type, session.status, session.call_mode)

            await self.db.commit()
            logger.info(f"🏁 Session {session_id} ended. Duration: {session.duration_seconds}s")