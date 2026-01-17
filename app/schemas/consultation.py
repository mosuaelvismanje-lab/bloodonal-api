from pydantic import BaseModel, ConfigDict # ✅ Added ConfigDict
from typing import Optional

class ConsultationResponse(BaseModel):
    """
    Standardized response for consultation requests.
    Includes quota tracking for free usage.
    """
    # ✅ Added for Pydantic V2 consistency and ORM support
    model_config = ConfigDict(from_attributes=True)

    success: bool
    message: Optional[str] = None
    request_id: Optional[str] = None
    remaining_free_uses: Optional[int] = None
    transaction_id: Optional[str] = None
