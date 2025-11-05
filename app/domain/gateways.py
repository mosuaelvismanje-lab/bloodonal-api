# app/domain/gateways.py
from abc import ABC, abstractmethod

class IPaymentGateway(ABC):
    @abstractmethod
    async def charge(self, phone: str, amount: int) -> str:
        """Charge mobile money; return transaction_id or raise on failure."""
