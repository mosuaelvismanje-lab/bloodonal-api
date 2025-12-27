from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime


class CallRequestPayload(BaseModel):
    # Use model_config instead of class Config
    model_config = ConfigDict(populate_by_name=True)

    caller_id: str = Field(..., alias="caller_id")
    callee_id: Optional[str] = Field(None, alias="callee_id")
    recipient_ids: Optional[List[str]] = Field(None, alias="recipient_ids")
    callee_type: Optional[str] = Field(None, alias="callee_type")
    call_mode: Optional[str] = Field("video", alias="call_mode")

    # Renamed to match your SQLAlchemy model fix
    session_metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata")


class InitiateCallRequest(BaseModel):
    caller_id: str
    recipient_ids: Optional[List[str]] = None
    callee_type: Optional[str] = None
    call_mode: Optional[str] = "video"
    session_metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata")


class EndCallRequest(BaseModel):
    session_id: str
    reason: Optional[str] = None
    ended_by: Optional[str] = None


class SessionResponse(BaseModel):
    # orm_mode is now from_attributes
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    room_name: str
    token: Optional[str] = None
    call_mode: Optional[str] = None
    status: Optional[str] = None
    started_at: Optional[datetime] = None
