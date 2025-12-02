# app/schemas/calls.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class CallRequestPayload(BaseModel):
    caller_id: str = Field(..., alias="caller_id")
    callee_id: Optional[str] = Field(None, alias="callee_id")   # single-recipient legacy
    recipient_ids: Optional[List[str]] = Field(None, alias="recipient_ids")  # multi-recipient
    callee_type: Optional[str] = Field(None, alias="callee_type")
    call_mode: Optional[str] = Field("video", alias="call_mode")  # "voice" or "video"
    metadata: Optional[dict] = None

    class Config:
        allow_population_by_field_name = True


class InitiateCallRequest(BaseModel):
    caller_id: str
    recipient_ids: Optional[List[str]] = None
    callee_type: Optional[str] = None
    call_mode: Optional[str] = "video"
    metadata: Optional[dict] = None


class EndCallRequest(BaseModel):
    session_id: str
    reason: Optional[str] = None
    ended_by: Optional[str] = None


class SessionResponse(BaseModel):
    session_id: str
    room_name: str
    token: Optional[str] = None
    call_mode: Optional[str] = None
    status: Optional[str] = None
    started_at: Optional[datetime] = None

    class Config:
        orm_mode = True
