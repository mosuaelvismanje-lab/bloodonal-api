# app/adapters/mtn_gateway.py
from app.domain.gateways import IPaymentGateway

class MtnGateway(IPaymentGateway):
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def charge(self, phone: str, amount: int) -> str:
        # call MTN API, handle response
        # e.g., HTTPX.post(...)
        # return transaction id
        ...
