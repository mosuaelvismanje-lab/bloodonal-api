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
    Generates dynamic USSD codes for Orange and MTN based on prefix detection.
    """

    def __init__(self):
        # In-memory store to simulate transaction persistence for unit tests
        self._tx_store: Dict[str, str] = {}

    async def charge(
            self,
            phone: str,
            amount: int,
            description: Optional[str] = None,
            merchant_number: Optional[str] = None
    ) -> GatewayPaymentResponse:
        """
        Detects the provider and generates the appropriate USSD string for
        manual merchant payments in Cameroon.
        """
        await asyncio.sleep(0.3)  # Simulate network latency

        tx_ref = f"MAN-{uuid.uuid4().hex[:8].upper()}"
        self._tx_store[tx_ref] = "SUCCESS"

        # 1. Provider Detection (Cameroon Prefixes)
        # Orange: 69x, 655, 656, 657, 658, 659
        is_orange = phone.startswith(("69", "655", "656", "657", "658", "659"))

        # 2. Select Merchant Wallet (Arg Priority > Settings)
        if not merchant_number:
            merchant_number = (
                settings.ADMIN_ORANGE_NUMBER if is_orange
                else settings.ADMIN_MTN_NUMBER
            )

        # 3. Generate USSD String
        if is_orange:
            provider = "ORANGE"
            ussd_code = f"#150*1*1*{merchant_number}*{amount}#"
        else:
            provider = "MTN"
            ussd_code = f"*126*9*{merchant_number}*{amount}#"

        logger.info(f"PROMPT: {provider} Payment initiated for {phone}. USSD: {ussd_code}")

        return GatewayPaymentResponse(
            reference=tx_ref,
            status="PENDING",
            ussd_string=ussd_code,
            provider_raw_response={
                "provider": provider,
                "merchant": merchant_number,
                "method": "manual_ussd"
            }
        )

    async def verify_transaction(self, reference: str) -> str:
        """Simulates immediate success for manual test paths."""
        return self._tx_store.get(reference, "FAILED")


class MTNMomoPaymentGateway(IPaymentGateway):
    """
    Production Adapter for MTN MoMo Cameroon Collection API.
    """
    BASE_URL = "https://proxy.momoapi.mtn.com/collection"

    def __init__(self, api_key: str, subscription_key: str):
        self.api_key = api_key
        self.subscription_key = subscription_key

    async def charge(
            self,
            phone: str,
            amount: int,
            description: Optional[str] = None,
            merchant_number: Optional[str] = None
    ) -> GatewayPaymentResponse:
        tx_ref = str(uuid.uuid4())

        payload = {
            "amount": str(amount),
            "currency": "XAF",
            "externalId": tx_ref,
            "payer": {"partyIdType": "MSISDN", "partyId": phone},
            "payerMessage": description or "Service Payment",
            "payeeNote": "Bloodonal Service Payment",
        }

        headers = {
            "X-Reference-Id": tx_ref,
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "X-Target-Environment": settings.MTN_MOMO_ENVIRONMENT,
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/v1_0/requesttopay",
                    headers=headers,
                    json=payload,
                )

            # 202 Accepted is the standard response for MTN Collection
            if resp.status_code not in (200, 202):
                logger.error(f"MTN API Error: {resp.status_code} - {resp.text}")
                return GatewayPaymentResponse(reference=tx_ref, status="FAILED")

            return GatewayPaymentResponse(
                reference=tx_ref,
                status="PENDING",
                ussd_string=None,
                provider_raw_response=resp.json() if resp.text else {}
            )
        except Exception as exc:
            logger.error(f"MTN Connection Failure: {exc}")
            return GatewayPaymentResponse(reference=tx_ref, status="FAILED")

    async def verify_transaction(self, reference: str) -> str:
        """Polls the MTN API for the final status of a request."""
        headers = {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "X-Target-Environment": settings.MTN_MOMO_ENVIRONMENT,
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/v1_0/requesttopay/{reference}",
                    headers=headers
                )

            if resp.status_code == 200:
                status = resp.json().get("status", "PENDING")
                return "SUCCESS" if status == "SUCCESSFUL" else status.upper()

            return "PENDING"
        except Exception:
            return "PENDING"