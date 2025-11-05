from pydantic import BaseModel

class PaymentRequest(BaseModel):
    user_id: str
    amount: int
    resource_id: str | None = None  # renamed for general use

class PaymentResponse(BaseModel):
    success: bool
    transaction_id: str

class FreeUsageResponse(BaseModel):
    remaining: int
