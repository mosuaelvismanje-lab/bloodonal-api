#app/gateways/mock_adapter
import uuid
import logging
from typing import Optional
from app.domain.interfaces import IPaymentGateway

logger = logging.getLogger(__name__)


class MockAdapter(IPaymentGateway):
    """
    Fake payment gateway for development and unit tests.

    Supports BOTH:
    - Tests: charge(user_id, amount)
    - Production: charge(phone, amount, description)
    """

    async def charge(
        self,
        *,
        amount: float,
        phone: Optional[str] = None,
        description: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Simulates a mobile money charge.

        Rules:
        - If phone == "000000000", simulate failure
        - If user_id is provided (tests), generate tx using user_id
        """

        # ✅ Test mode (used by pytest)
        if user_id:
            logger.info(f"[MOCK PAYMENT][TEST] Charging {amount} XAF for user {user_id}")
            return f"mock-{user_id}-{uuid.uuid4().hex[:8]}"

        # ✅ Production mode
        if not phone:
            raise ValueError("phone is required when user_id is not provided")

        logger.info(
            f"[MOCK PAYMENT] Charging {amount} XAF to {phone} for '{description}'"
        )

        if phone == "000000000":
            raise ValueError("Insufficient funds in mock wallet.")

        return f"mock-{phone}-{uuid.uuid4().hex[:8]}"

    async def verify(self, provider_tx_id: str) -> str:
        """
        Simulates verification of a transaction.
        """
        return "success" if provider_tx_id.startswith("mock-") else "failed"
