import uuid
import logging
from dataclasses import dataclass
from typing import Dict

logger = logging.getLogger(__name__)


# =========================================================
# GATEWAY RESPONSE MODEL
# =========================================================
@dataclass
class GatewayPaymentResponse:
    reference: str
    status: str
    ussd_string: str
    provider_raw_response: dict


# =========================================================
# MOCK PAYMENT GATEWAY ADAPTER
# =========================================================
class MockAdapter:
    """
    Mock payment gateway for testing + local development.

    Simulates:
    - Orange USSD flows
    - MTN manual payment flows
    - Test-safe deterministic references
    """

    def __init__(self):
        # reference -> status
        self._tx_store: Dict[str, str] = {}

    # =====================================================
    # CHARGE (INITIATE PAYMENT)
    # =====================================================
    async def charge(self, phone: str, amount: int) -> GatewayPaymentResponse:
        """
        Simulate USSD charge initiation.
        Always returns MAN- prefix for test consistency.
        """

        reference = f"MAN-{uuid.uuid4().hex[:10].upper()}"
        ussd = self._generate_ussd(phone, amount)

        response = GatewayPaymentResponse(
            reference=reference,
            status="PENDING",
            ussd_string=ussd,
            provider_raw_response={
                "method": "manual_ussd",
                "provider": "ORANGE",
                "flow": "manual",
                "phone": phone,
                "amount": amount
            }
        )

        # store transaction state
        self._tx_store[reference] = "PENDING"

        logger.info(
            "USSD Generated | ref=%s | phone=%s | amount=%s",
            reference, phone, amount
        )

        return response

    # =====================================================
    # VERIFY TRANSACTION
    # =====================================================
    async def verify_transaction(self, reference: str) -> str:
        """
        Simulate provider reconciliation.
        """

        status = self._tx_store.get(reference, "FAILED")

        logger.info(
            "Transaction verification | ref=%s | status=%s",
            reference, status
        )

        return status

    # =====================================================
    # USSD GENERATOR
    # =====================================================
    def _generate_ussd(self, phone: str, amount: int) -> str:
        """
        Orange Cameroon-style USSD simulation.
        """

        return f"#150*1*1*{phone}*{amount}#"