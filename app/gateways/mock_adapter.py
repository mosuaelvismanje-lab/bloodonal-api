import uuid
import logging
from typing import Optional
from app.domain.interfaces import IPaymentGateway

logger = logging.getLogger(__name__)


class MockAdapter(IPaymentGateway):
    """
    Fake gateway for development and unit tests.

    Updated to match the production interface:
    charge(phone, amount, description)
    """

    async def charge(
            self,
            phone: str,
            amount: float,
            description: str,
    ) -> str:
        """
        Simulates a mobile money charge.

        Logic for Testing:
        - If phone is '000000000', simulate a Payment Failure (Insufficient Funds).
        - Otherwise, return a deterministic mock transaction ID.
        """
        logger.info(f"[MOCK PAYMENT] Charging {amount} XAF to {phone} for '{description}'")

        # Logic to test error handling in your UseCase
        if phone == "000000000":
            raise ValueError("Insufficient funds in mock wallet.")

        # Create a mock id: 'mock-<phone>-<random_hex>'
        tx_id = f"mock-{phone}-{uuid.uuid4().hex[:8]}"

        return tx_id

    async def verify(self, provider_tx_id: str) -> str:
        """
        Simulates verification of a transaction.
        Returns 'success' if it's a mock ID, otherwise 'failed'.
        """
        if provider_tx_id.startswith("mock-"):
            return "success"
        return "failed"
