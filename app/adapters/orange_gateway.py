# app/adapters/orange_gateway.py
from app.domain.gateways import IPaymentGateway

class OrangeGateway(IPaymentGateway):
    def __init__(self, client_id: str, client_secret: str):
        ...
    async def charge(self, phone: str, amount: int) -> str:
        ...
