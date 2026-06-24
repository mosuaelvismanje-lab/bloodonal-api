from __future__ import annotations

from datetime import datetime
from typing import Optional, TypedDict


class DonorDTO(TypedDict):
    city: str
    blood_group: str
    is_available: bool
    successful_responses: int
    rejection_count: int
    avg_response_minutes: float
    fraud_risk_score: int
    last_active: Optional[datetime]


class RequestDTO(TypedDict):
    city: str
    blood_group: str
    is_urgent: bool
    active_donors: int
    required_donors: int
    hospital_priority_level: int