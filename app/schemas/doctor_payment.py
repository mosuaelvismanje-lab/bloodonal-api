from pydantic import BaseModel

class DoctorPaymentRequest(BaseModel):
    user_id: str
    amount: int
    consult_id: str | None = None

class DoctorPaymentResponse(BaseModel):
    success: bool
    transaction_id: str
