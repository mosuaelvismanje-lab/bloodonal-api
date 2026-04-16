import uuid
import httpx
import logging
from typing import Optional, Dict, Any
from app.domain.gateways import IPaymentGateway, GatewayPaymentResponse

logger = logging.getLogger(__name__)


class FlutterwavePaymentGateway(IPaymentGateway):
    """
    Flutterwave adapter for Cameroon Mobile Money (XAF).
    Aligned with GatewayPaymentResponse and IPaymentGateway interface.
    """
    BASE_URL = "https://api.flutterwave.com/v3"

    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    async def charge(
            self,
            phone: str,
            amount: int,
            description: Optional[str] = None
    ) -> GatewayPaymentResponse:
        """
        Initiates a Mobile Money collection (pull) via Flutterwave.
        """
        internal_ref = f"flw-{uuid.uuid4().hex[:8]}"

        # Francophone Mobile Money requires specific payload fields
        payload = {
            "amount": amount,
            "currency": "XAF",
            "phone_number": phone,
            "network": self._detect_network(phone),
            "email": "payments@yourapp.com",
            "tx_ref": internal_ref,
            "fullname": "App User",
            "country": "CM",  # Mandatory for Cameroon
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{self.BASE_URL}/charges?type=mobile_money_franco",
                    headers={"Authorization": f"Bearer {self.secret_key}"},
                    json=payload,
                    timeout=30.0
                )
            except httpx.RequestError as exc:
                logger.error(f"Network error calling Flutterwave: {exc}")
                return GatewayPaymentResponse(reference=internal_ref, status="FAILED")

        if resp.status_code not in (200, 201):
            logger.error(f"Flutterwave error: {resp.text}")
            return GatewayPaymentResponse(reference=internal_ref, status="FAILED")

        # Parse JSON correctly from httpx response
        data = resp.json()

        if data.get("status") == "error":
            logger.warning(f"Flutterwave rejected charge: {data.get('message')}")
            return GatewayPaymentResponse(reference=internal_ref, status="FAILED")

        # FLW returns the transaction ID in data['data']['id']
        flw_id = str(data.get("data", {}).get("id") or internal_ref)

        return GatewayPaymentResponse(
            reference=flw_id,
            status="PENDING",
            ussd_string=None,  # Flutterwave typically uses Push/STK prompts
            provider_raw_response=data
        )

    async def verify_transaction(self, reference: str) -> str:
        """
        Checks the final status of a transaction using the FLW ID.
        """
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"{self.BASE_URL}/transactions/{reference}/verify",
                    headers={"Authorization": f"Bearer {self.secret_key}"},
                    timeout=10.0
                )
            except Exception as e:
                logger.error(f"Verification fetch failed: {e}")
                return "PENDING"

        if resp.status_code != 200:
            return "PENDING"

        data = resp.json()
        status = data.get("data", {}).get("status", "").lower()

        # Map Flutterwave status to domain status
        if status == "successful":
            return "SUCCESS"
        elif status == "failed":
            return "FAILED"
        return "PENDING"

    def _detect_network(self, phone: str) -> str:
        """Standard Cameroon prefixes for network detection."""
        if phone.startswith(("23767", "23768", "237650", "237651", "237652", "237653", "237654", "67", "68")):
            return "MTN"
        return "ORANGE"
