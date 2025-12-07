# app/gateways/mock_adapter.py
import uuid
from typing import Dict, Any, Optional
from app.domain.interfaces import IPaymentGateway


class MockAdapter(IPaymentGateway):
    """
    Fake gateway for development and unit tests.

    The tests expect `await adapter.charge(user_id=..., amount=...)` and a
    returned string transaction id that begins with "mock-<user_id>-".
    """

    async def charge(
        self,
        user_id: str,
        amount: int,
        currency: str = "usd",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        # Create a deterministic-ish mock id so tests can assert prefix
        tx_id = f"mock-{user_id}-{uuid.uuid4().hex}"
        return tx_id

    async def verify(self, tx_id: str) -> bool:
        """
        Minimal implementation of abstract method.

        Returns True if tx_id starts with "mock-", otherwise False.
        """
        return tx_id.startswith("mock-")
