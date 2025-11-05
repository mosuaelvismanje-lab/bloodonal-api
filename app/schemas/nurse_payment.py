from pydantic import BaseModel

class NursePaymentRequest(BaseModel):
    user_id: str
    amount: int
    consult_id: str | None = None

class NursePaymentResponse(BaseModel):
    success: bool
    transaction_id: str
