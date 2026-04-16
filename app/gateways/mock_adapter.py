#app/gateways/mock_adapter
import uuid
import asyncio
import logging
import httpx
from typing import Optional, Dict, Any
from app.domain.gateways import IPaymentGateway, GatewayPaymentResponse
from app.config import settings  # ✅ Integrated Centralized Settings

logger = logging.getLogger(__name__)


class MockAdapter(IPaymentGateway):
    """
    Manual Transaction Adapter for Cameroon Mobile Money.
    Generates dynamic USSD codes using merchant numbers from .env.
    """

    def __init__(self):
        # In-memory transaction registry for verification simulations
        self._tx_store: set[str] = set()

    async def charge(
            self,
            phone: str,
            amount: int,
            description: Optional[str] = None,
            merchant_number: Optional[str] = None  # ✅ Matches new interface
    ) -> GatewayPaymentResponse:
        """
        Simulates a mobile money charge and generates USSD codes.
        """
        # Simulate network delay
        await asyncio.sleep(0.5)

        tx_ref = f"MAN-{uuid.uuid4().hex[:6].upper()}"
        self._tx_store.add(tx_ref)

        # 1. Detect Provider (Cameroon Prefixes)
        is_orange = phone.startswith(("69", "655", "656", "657", "658", "659"))

        # 2. Lookup Merchant Number (Priority: Passed argument > .env Settings)
        if not merchant_number:
            merchant_number = settings.ADMIN_ORANGE_NUMBER if is_orange else settings.ADMIN_MTN_NUMBER

        # 3. Build USSD String
        if is_orange:
            provider = "ORANGE MONEY"
            ussd_code = f"#150*1*1*{merchant_number}*{amount}#"
        else:
            provider = "MTN MOMO"
            ussd_code = f"*126*9*{merchant_number}*{amount}#"

        # Log for Admin Visibility
        logger.info(f"💰 [MOCK] {provider} USSD: Dial {ussd_code} (Ref: {tx_ref})")

        return GatewayPaymentResponse(
            reference=tx_ref,
            status="PENDING",
            ussd_string=ussd_code,
            provider_raw_response={"provider": provider, "manual": True, "merchant_wallet": merchant_number}
        )

    async def verify_transaction(self, reference: str) -> str:
        """
        Matches IPaymentGateway interface exactly.
        Returns: "SUCCESS", "FAILED", or "PENDING"
        """
        await asyncio.sleep(0.1)
        return "SUCCESS" if reference in self._tx_store else "FAILED"


class MTNMomoPaymentGateway(IPaymentGateway):
    """
    Official API Adapter for MTN MoMo Cameroon (Collection API).
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

        # Standard MTN Request-to-Pay Payload
        payload = {
            "amount": str(amount),
            "currency": "XAF",
            "externalId": tx_ref,
            "payer": {"partyIdType": "MSISDN", "partyId": phone},
            "payerMessage": description or "Service Payment",
            "payeeNote": "Payment received",
        }

        headers = {
            "X-Reference-Id": tx_ref,
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "X-Target-Environment": settings.MTN_MOMO_ENVIRONMENT,  # ✅ Pulls "sandbox" or "mtncameroon"
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/v1_0/requesttopay",
                    headers=headers,
                    json=payload,
                )

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
            logger.error(f"Network error reaching MTN MoMo: {exc}")
            return GatewayPaymentResponse(reference=tx_ref, status="FAILED")

    async def verify_transaction(self, reference: str) -> str:
        """Required by interface to poll for final status."""
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
                data = resp.json()
                return data.get("status", "PENDING").upper()  # e.g., SUCCESSFUL, FAILED
            return "PENDING"
        except Exception:
            return "PENDING"