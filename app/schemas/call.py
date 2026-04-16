from __future__ import annotations
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID


# ---------------------------------------------------------
# 1. INITIATION SCHEMAS (Kotlin -> FastAPI)
# ---------------------------------------------------------

class CallInitiatePayload(BaseModel):
    """
    Matches Kotlin: data class CallInitiateRequest(...)
    Sent by the Android app to start a new Jitsi session.
    """
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    caller_id: str = Field(..., description="UID of the person starting the call")
    callee_id: str = Field(..., description="UID of the provider/recipient")
    callee_type: str = Field("doctor", description="doctor | nurse | donor | taxi")
    call_mode: str = Field("video", description="voice | video")

    # Allows Android to pass extra data like 'specialty' or 'emergency_level'
    session_metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata")


class CallStatusUpdate(BaseModel):
    """
    Used for PATCH /calls/{session_id}/status
    Updates the state of the call (ongoing, completed, rejected).
    """
    model_config = ConfigDict(use_enum_values=True)

    status: str = Field(..., description="ongoing | completed | missed | rejected")
    session_metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata")


# ---------------------------------------------------------
# 2. RESPONSE SCHEMAS (FastAPI -> Kotlin)
# ---------------------------------------------------------

class CallSessionResponse(BaseModel):
    """
    Matches Kotlin: data class CallSessionResponse(...)
    The full object returned after initiation or status updates.
    """
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    # Note: UUID is automatically serialized to string for Kotlin
    session_id: UUID = Field(..., alias="id")
    room_name: str
    token: Optional[str] = None  # Jitsi JWT Token

    caller_id: str
    callee_id: str
    status: str
    call_mode: str

    # Timing info for the Android UI
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: int = 0


# ---------------------------------------------------------
# 3. ADMIN & MONITORING SCHEMAS
# ---------------------------------------------------------

class ActiveCallReport(BaseModel):
    """
    Used by the Admin Dashboard to show live calls.
    """
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    caller_id: str
    callee_id: str
    service_type: str
    duration_current: int = Field(..., description="Active duration in seconds")