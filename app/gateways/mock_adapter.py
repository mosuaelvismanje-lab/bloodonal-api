import uuid
import asyncio
import logging
from typing import Optional
from app.domain.interfaces import IPaymentGateway

logger = logging.getLogger(__name__)


class MockAdapter(IPaymentGateway):
    """
    Fake payment gateway for development and unit tests.

    Supports:
    - Unit tests → charge(user_id, amount)
    - App logic → charge(phone, amount, description)

    Keeps an in-memory transaction registry so verify() behaves correctly.
    """

    def __init__(self):
        # In-memory transaction registry (safe for tests)
        self._tx_store: set[str] = set()

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
        - If user_id is provided → test mode
        - If phone == "000000000" → simulate failure
        """

        # simulate async network delay
        await asyncio.sleep(0)

        # ✅ Test mode (pytest, services)
        if user_id:
            tx = f"mock-{user_id}-{uuid.uuid4().hex[:12]}"
            self._tx_store.add(tx)
            logger.debug("[MOCK][TEST] charge -> %s", tx)
            return tx

        # ✅ Production / app mode
        if not phone:
            raise ValueError("phone is required when user_id is not provided")

        if phone == "000000000":
            raise ValueError("Insufficient funds in mock wallet.")

        tx = f"mock-{phone}-{uuid.uuid4().hex[:12]}"
        self._tx_store.add(tx)

        logger.debug(
            "[MOCK] Charging %s XAF to %s (%s) -> %s",
            amount,
            phone,
            description,
            tx,
        )

        return tx

    async def verify(self, provider_tx_id: str) -> bool:
        """
        Verifies a previously generated transaction.

        Returns:
        - True → transaction exists
        - False → unknown transaction
        """

        await asyncio.sleep(0)
        result = provider_tx_id in self._tx_store
        logger.debug("[MOCK] verify %s -> %s", provider_tx_id, result)
        return bool(result)

