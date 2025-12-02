import uuid
from typing import Dict, Any
from app.domain.interfaces import IPaymentGateway


class MockPaymentGateway(IPaymentGateway):
    """
    Fake gateway for development and unit tests.
    """

    async def charge(self, amount: int, currency: str, reference: str, metadata: Dict[str, Any]):
        fake_id = str(uuid.uuid4())
        return {
            "status": "success",
            "provider_ref": fake_id,
            "raw": {
                "message": "Mock charge completed",
                "amount": amount,
                "currency": currency,
                "reference": reference
            }
        }
