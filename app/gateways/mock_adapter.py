import asyncio
import logging
import httpx
from typing import Optional, Dict, Any

from app.domain.gateways import IPaymentGateway, GatewayPaymentResponse
from app.config import settings
from app.services.payment_service import generate_reference

logger = logging.getLogger("app.gateways")


# ======================================================
# 1. MANUAL / MOCK ADAPTER (Cameroon USSD)
# ======================================================

class MockAdapter(IPaymentGateway):
    """
    Manual Transaction Adapter.
    Generates USSD codes for manual Orange/MTN merchant payments.
    """

    def __init__(self):
        self._tx_store: Dict[str, str] = {}

    async def charge(
        self,
        phone: str,
        amount: int,
        description: Optional[str] = None,
        merchant_number: Optional[str] = None
    ) -> GatewayPaymentResponse:

        await asyncio.sleep(0.05)  # faster tests

        tx_ref = generate_reference()
        self._tx_store[tx_ref] = "PENDING"

        # Detect provider
        is_orange = phone.startswith(("69", "655", "656", "657", "658", "659"))

        merchant = merchant_number or (
            settings.ADMIN_ORANGE_NUMBER if is_orange else settings.ADMIN_MTN_NUMBER
        )

        if is_orange:
            ussd_code = f"#150*1*1*{merchant}*{amount}#"
            provider = "ORANGE"
        else:
            ussd_code = f"*126*9*{merchant}*{amount}#"
            provider = "MTN"

        logger.info(f"Manual {provider} USSD Generated: {ussd_code} for {phone}")

        return GatewayPaymentResponse(
            reference=tx_ref,
            status="PENDING",
            ussd_string=ussd_code,
            provider_raw_response={
                "method": "manual_ussd",
                "merchant": merchant,
                "provider": provider,
                "flow": "manual"
            }
        )

    async def verify_transaction(self, reference: str) -> str:
        return self._tx_store.get(reference, "FAILED")


# ======================================================
# 2. PRODUCTION MTN MOMO ADAPTER
# ======================================================

class MTNMomoPaymentGateway(IPaymentGateway):
    """
    Production Adapter for MTN MoMo Collection API.
    """

    def __init__(self, api_key: str, subscription_key: str):
        self.api_key = api_key
        self.subscription_key = subscription_key
        self.base_url = getattr(
            settings,
            "MTN_MOMO_BASE_URL",
            "https://proxy.momoapi.mtn.com/collection"
        )

        # ✅ FIX: define timeout safely
        self.timeout = getattr(settings, "GATEWAY_TIMEOUT", 15.0)

    async def charge(
        self,
        phone: str,
        amount: int,
        description: Optional[str] = None,
        merchant_number: Optional[str] = None
    ) -> GatewayPaymentResponse:

        tx_ref = generate_reference()

        payload = {
            "amount": str(amount),
            "currency": "XAF",
            "externalId": tx_ref,
            "payer": {"partyIdType": "MSISDN", "partyId": phone},
            "payerMessage": description or "Service Payment",
            "payeeNote": "Payment for modular service access",
        }

        headers = {
            "X-Reference-Id": tx_ref,
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "X-Target-Environment": settings.MTN_MOMO_ENVIRONMENT,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            # ✅ FIX: use context manager (important for tests + cleanup)
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/v1_0/requesttopay",
                    headers=headers,
                    json=payload,
                )

            # ✅ FIX: correct status mapping
            if resp.status_code in (200, 202):
                return GatewayPaymentResponse(
                    reference=tx_ref,
                    status="PENDING",   # REQUIRED for your test
                    ussd_string=None,
                    provider_raw_response=resp.json() if resp.text else {}
                )

            logger.error(f"MTN Collection Error: {resp.status_code} | {resp.text}")
            return GatewayPaymentResponse(
                reference=tx_ref,
                status="FAILED",
                provider_raw_response={"error": resp.text}
            )

        except httpx.RequestError as exc:
            logger.error(f"MTN Connectivity Failure: {exc}")
            return GatewayPaymentResponse(
                reference=tx_ref,
                status="FAILED",
                provider_raw_response={"error": str(exc)}
            )

        except Exception as exc:
            # ✅ EXTRA SAFETY (this was causing silent test failures before)
            logger.exception(f"Unexpected MTN error: {exc}")
            return GatewayPaymentResponse(
                reference=tx_ref,
                status="FAILED",
                provider_raw_response={"error": str(exc)}
            )

    async def verify_transaction(self, reference: str) -> str:

        headers = {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "X-Target-Environment": settings.MTN_MOMO_ENVIRONMENT,
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.base_url}/v1_0/requesttopay/{reference}",
                    headers=headers
                )

            if resp.status_code == 200:
                data = resp.json()
                raw_status = data.get("status", "PENDING").upper()

                if raw_status == "SUCCESSFUL":
                    return "SUCCESS"
                elif raw_status in ("FAILED", "REJECTED"):
                    return "FAILED"
                else:
                    return "PENDING"

            return "PENDING"

        except Exception as e:
            logger.warning(f"Verification poll failed for {reference}: {e}")
            return "PENDING"