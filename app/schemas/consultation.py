# app/schemas/consultation.py
from pydantic import BaseModel
from typing import Optional

class ConsultationResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    request_id: Optional[str] = None
    remaining_free_uses: Optional[int] = None
    transaction_id: Optional[str] = None
