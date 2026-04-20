import uuid
import asyncio
import logging
import httpx
from typing import Optional, Dict, Any
from app.domain.gateways import IPaymentGateway, GatewayPaymentResponse
from app.config import settings  # ✅ Use centralized settings

logger = logging.getLogger(__name__)


class MockAdapter(IPaymentGateway):
    """
    Manual Transaction Adapter for Cameroon Mobile Money.
    Used for local testing and manual USSD generation.
    """

    def __init__(self):
        self._tx_store: set[str] = set()

    async def charge(
            self,
            phone: str,
            amount: int,
            description: Optional[str] = None,
            merchant_number: Optional[str] = None  # ✅ Added for interface parity
    ) -> GatewayPaymentResponse:
        await asyncio.sleep(0.3)

        tx_ref = f"MAN-{uuid.uuid4().hex[:6].upper()}"
        self._tx_store.add(tx_ref)

        is_orange = phone.startswith(("69", "655", "656", "657", "658", "659"))

        # Prioritize passed merchant_number, fallback to .env settings
        if not merchant_number:
            merchant_number = (
                settings.ADMIN_ORANGE_NUMBER if is_orange
                else settings.ADMIN_MTN_NUMBER
            )

        if is_orange:
            provider = "ORANGE MONEY"
            ussd_code = f"#150*1*1*{merchant_number}*{amount}#"
        else:
            provider = "MTN MOMO"
            ussd_code = f"*126*9*{merchant_number}*{amount}#"

        logger.info(f"💰 MOCK {provider}: Dial {ussd_code} for {phone}")

        return GatewayPaymentResponse(
            reference=tx_ref,
            status="PENDING",
            ussd_string=ussd_code,
            provider_raw_response={"provider": provider, "manual": True}
        )

    async def verify_transaction(self, reference: str) -> str:
        return "SUCCESS" if reference in self._tx_store else "FAILED"


class MTNMomoPaymentGateway(IPaymentGateway):
    """
    Official API Adapter for MTN MoMo Cameroon (Collection API).
    """
    BASE_URL = "https://proxy.momoapi.mtn.com/collection"

    def __init__(self, api_key: str, subscription_key: str, momo_account: str = None):
        self.api_key = api_key
        self.subscription_key = subscription_key
        self.momo_account = momo_account

    async def charge(
            self,
            phone: str,
            amount: int,
            description: Optional[str] = None,
            merchant_number: Optional[str] = None  # ✅ Added for interface parity
    ) -> GatewayPaymentResponse:
        reference = str(uuid.uuid4())

        payload = {
            "amount": str(amount),
            "currency": "XAF",
            "externalId": reference,
            "payer": {"partyIdType": "MSISDN", "partyId": phone},
            "payerMessage": description or "Bloodonal Service Payment",
            "payeeNote": "Thank you for using Bloodonal",
        }

        headers = {
            "X-Reference-Id": reference,
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            # ✅ Pull environment (sandbox vs mtncameroon) from settings
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

            if resp.status_code not in (200, 202):
                logger.error(f"MTN API Error: {resp.status_code} - {resp.text}")
                return GatewayPaymentResponse(reference=reference, status="FAILED")

            return GatewayPaymentResponse(
                reference=reference,
                status="PENDING",
                ussd_string=None,
                provider_raw_response=resp.json() if resp.text else {}
            )
        except Exception as exc:
            logger.error(f"Network error reaching MTN: {exc}")
            return GatewayPaymentResponse(reference=reference, status="FAILED")

    async def verify_transaction(self, reference: str) -> str:
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
                status = data.get("status", "PENDING").upper()
                return "SUCCESS" if status == "SUCCESSFUL" else status
            return "PENDING"
        except Exception:
            return "PENDING"