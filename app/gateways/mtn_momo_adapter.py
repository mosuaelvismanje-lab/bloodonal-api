import uuid
import asyncio
import logging
import httpx
from typing import Optional, Dict, Any
from app.domain.gateways import IPaymentGateway, GatewayPaymentResponse
from app.config import settings

logger = logging.getLogger(__name__)


class MockAdapter(IPaymentGateway):
    """
    Manual Transaction Adapter for Cameroon Mobile Money.
    Used for local testing and manual USSD generation.
    """

    def __init__(self):
        # Using a dict to store status allows for more realistic test scenarios
        self._tx_store: Dict[str, str] = {}

    async def charge(
            self,
            phone: str,
            amount: int,
            description: Optional[str] = None,
            merchant_number: Optional[str] = None
    ) -> GatewayPaymentResponse:
        """Generates a manual USSD string for Orange/MTN Cameroon."""
        await asyncio.sleep(0.2)  # Simulate network latency

        tx_ref = f"MAN-{uuid.uuid4().hex[:6].upper()}"
        self._tx_store[tx_ref] = "PENDING"

        # Determine provider based on Cameroon phone prefix logic
        is_orange = phone.startswith(("69", "655", "656", "657", "658", "659"))

        # Fallback logic for merchant numbers
        if not merchant_number:
            merchant_number = (
                settings.ADMIN_ORANGE_NUMBER if is_orange
                else settings.ADMIN_MTN_NUMBER
            )

        if is_orange:
            provider = "ORANGE"
            ussd_code = f"#150*1*1*{merchant_number}*{amount}#"
        else:
            provider = "MTN"
            ussd_code = f"*126*9*{merchant_number}*{amount}#"

        logger.info(f"💰 [MOCK] {provider} payment generated: {tx_ref} | Dial: {ussd_code}")

        return GatewayPaymentResponse(
            reference=tx_ref,
            status="PENDING",
            ussd_string=ussd_code,
            provider_raw_response={"provider": provider, "manual": True, "merchant": merchant_number}
        )

    async def verify_transaction(self, reference: str) -> str:
        """Mocks the verification of a manual transaction."""
        return self._tx_store.get(reference, "FAILED")


class MTNMomoPaymentGateway(IPaymentGateway):
    """
    Official API Adapter for MTN MoMo Cameroon (Collection API).
    """
    BASE_URL = "https://proxy.momoapi.mtn.com/collection"

    def __init__(self, api_key: str, subscription_key: str, momo_account: str = None):
        self.api_key = api_key
        self.subscription_key = subscription_key
        self.momo_account = momo_account

    def _get_headers(self, reference: Optional[str] = None) -> Dict[str, str]:
        """Helper to standardize MTN API headers."""
        headers = {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "X-Target-Environment": settings.MTN_MOMO_ENVIRONMENT,
            "Authorization": f"Bearer {self.api_key}",
        }
        if reference:
            headers["X-Reference-Id"] = reference
        return headers

    async def charge(
            self,
            phone: str,
            amount: int,
            description: Optional[str] = None,
            merchant_number: Optional[str] = None
    ) -> GatewayPaymentResponse:
        """Triggers a Push USSD request via MTN Collection API."""
        reference = str(uuid.uuid4())

        payload = {
            "amount": str(amount),
            "currency": "XAF",
            "externalId": reference,
            "payer": {"partyIdType": "MSISDN", "partyId": phone},
            "payerMessage": description or "Bloodonal Payment",
            "payeeNote": "Thank you for your contribution",
        }

        try:
            async with httpx.AsyncClient(timeout=settings.GATEWAY_TIMEOUT) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/v1_0/requesttopay",
                    headers=self._get_headers(reference),
                    json=payload,
                )

            # MTN returns 202 Accepted for successful push triggers
            if resp.status_code == 202:
                return GatewayPaymentResponse(
                    reference=reference,
                    status="PENDING",
                    provider_raw_response={"http_status": 202}
                )

            logger.error(f"❌ MTN Charge Failed [{resp.status_code}]: {resp.text}")
            return GatewayPaymentResponse(reference=reference, status="FAILED")

        except Exception as exc:
            logger.exception(f"🚨 Network exception during MTN charge: {exc}")
            return GatewayPaymentResponse(reference=reference, status="FAILED")

    async def verify_transaction(self, reference: str) -> str:
        """Polls MTN API to check the status of a specific RequestToPay."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/v1_0/requesttopay/{reference}",
                    headers=self._get_headers()
                )

            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status", "PENDING").upper()
                # Normalizing MTN 'SUCCESSFUL' to internal 'SUCCESS'
                return "SUCCESS" if status == "SUCCESSFUL" else status

            return "PENDING"
        except Exception as exc:
            logger.warning(f"⚠️ Could not verify MTN transaction {reference}: {exc}")
            return "PENDING"