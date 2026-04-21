import uuid
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GatewayPaymentResponse:
    reference: str
    status: str
    ussd_string: str
    provider_raw_response: dict


class MockAdapter:
    """
    Mock payment gateway for testing + local development.
    Simulates Orange / MTN manual USSD flows.
    """

    def __init__(self):
        self._tx_store = {}  # reference -> status

    # -------------------------------------------------
    # CHARGE
    # -------------------------------------------------
    async def charge(self, phone: str, amount: int) -> GatewayPaymentResponse:
        """
        Simulate manual USSD charge.
        MUST return MAN- prefix for test consistency.
        """

        # 🔥 FIX: Force MAN- prefix (test requirement)
        reference = f"MAN-{uuid.uuid4().hex[:10].upper()}"

        ussd = self._generate_ussd(phone, amount)

        response = GatewayPaymentResponse(
            reference=reference,
            status="PENDING",
            ussd_string=ussd,
            provider_raw_response={
                "method": "manual_ussd",
                "merchant": phone,
                "provider": "ORANGE",
                "flow": "manual"
            }
        )

        # store pending transaction
        self._tx_store[reference] = "PENDING"

        logger.info(f"Manual ORANGE USSD Generated: {ussd} for {phone}")

        return response

    # -------------------------------------------------
    # VERIFY
    # -------------------------------------------------
    async def verify_transaction(self, reference: str) -> str:
        """
        Simulate admin reconciliation.
        """

        return self._tx_store.get(reference, "FAILED")

    # -------------------------------------------------
    # INTERNAL USSD GENERATOR
    # -------------------------------------------------
    def _generate_ussd(self, phone: str, amount: int) -> str:
        """
        Orange Cameroon manual USSD pattern
        """
        return f"#150*1*1*690000000*{amount}#"