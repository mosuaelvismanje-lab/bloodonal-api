#app/gatateways/mtn_momo_adapter
import uuid
import asyncio
import logging
import httpx
from typing import Optional, Dict, Any
from app.domain.gateways import IPaymentGateway, GatewayPaymentResponse

logger = logging.getLogger(__name__)


class MockAdapter(IPaymentGateway):
    """
    Manual Transaction Adapter for Cameroon Mobile Money.
    Generates a USSD code for the Android app to dial directly.
    """

    def __init__(self):
        self._tx_store: set[str] = set()
        self.ADMIN_MTN_BUSINESS = "670556320"
        self.ADMIN_ORANGE_BUSINESS = "690000000"

    async def charge(
            self,
            phone: str,
            amount: int,
            description: Optional[str] = None
    ) -> GatewayPaymentResponse:
        await asyncio.sleep(0.5)

        tx_ref = f"MAN-{uuid.uuid4().hex[:6].upper()}"
        self._tx_store.add(tx_ref)

        is_orange = phone.startswith(("69", "655", "656", "657", "658", "659"))

        if is_orange:
            provider = "ORANGE MONEY"
            ussd_code = f"#150*1*1*{self.ADMIN_ORANGE_BUSINESS}*{amount}#"
        else:
            provider = "MTN MOMO"
            ussd_code = f"*126*9*{self.ADMIN_MTN_BUSINESS}*{amount}#"

        print(f"\n💰 NEW {provider} TRANSACTION: Dial {ussd_code} (Ref: {tx_ref}) 💰\n")

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
    Official API Adapter for MTN MoMo Cameroon.
    """
    BASE_URL = "https://proxy.momoapi.mtn.com/collection"

    def __init__(self, api_key: str, subscription_key: str, momo_account: str):
        self.api_key = api_key
        self.subscription_key = subscription_key
        self.momo_account = momo_account

    async def charge(
            self,
            phone: str,
            amount: int,
            description: Optional[str] = None
    ) -> GatewayPaymentResponse:
        reference = str(uuid.uuid4())
        payload = {
            "amount": str(amount),
            "currency": "XAF",
            "externalId": reference,
            "payer": {"partyIdType": "MSISDN", "partyId": phone},
            "payerMessage": description or "Service Payment",
            "payeeNote": "Thank you",
        }

        headers = {
            "X-Reference-Id": reference,
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "X-Target-Environment": "mtncameroon",
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
                logger.error(f"MTN API Error: {resp.text}")
                return GatewayPaymentResponse(reference=reference, status="FAILED")

            return GatewayPaymentResponse(
                reference=reference,
                status="PENDING",
                ussd_string=None,
                provider_raw_response=resp.json() if resp.text else {}
            )
        except httpx.RequestError as exc:
            logger.error(f"Network error reaching MTN: {exc}")
            return GatewayPaymentResponse(reference=reference, status="FAILED")

    async def verify_transaction(self, reference: str) -> str:
        """
        Polls the MTN API for the status of a specific Request to Pay.
        """
        headers = {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "X-Target-Environment": "mtncameroon",
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
                return data.get("status", "PENDING").upper()  # SUCCESS, FAILED, or PENDING
            return "PENDING"
        except Exception:
            return "PENDING"