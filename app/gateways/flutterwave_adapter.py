import httpx
import logging
from typing import Optional
from app.domain.interfaces import IPaymentGateway

logger = logging.getLogger(__name__)


class FlutterwavePaymentGateway(IPaymentGateway):
    BASE_URL = "https://api.flutterwave.com/v3"

    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    async def charge(
            self,
            phone: str,
            amount: int,
            description: str
    ) -> str:
        """
        Initiates a Mobile Money collection (pull) via Flutterwave.
        """
        # Flutterwave mobile money payload for Cameroon/Africa regions
        payload = {
            "amount": amount,
            "currency": "XAF",
            "phone_number": phone,
            "network": self._detect_network(phone),  # Helper to pick MTN/ORANGE
            "email": "payments@yourapp.com",  # Required by FLW
            "tx_ref": f"ref-{phone}-{description[:10]}",
            "fullname": "App User",
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
                raise RuntimeError("Payment provider is currently unreachable.")

        if resp.status_code not in (200, 201):
            logger.error(f"Flutterwave error: {resp.text}")
            # Raise ValueError so the UseCase returns HTTP 402
            raise ValueError(f"Payment failed: {resp.json().get('message', 'Unknown error')}")

        data = resp.json()

        # Check if the transaction was successfully initiated
        if data.get("status") == "error":
            raise ValueError(data.get("message", "Transaction rejected"))

        # Return the provider's transaction ID (used for future verification)
        return str(data["data"].get("id") or data["data"].get("flw_ref"))

    async def verify(self, provider_tx_id: str) -> str:
        """
        Verifies the status of a specific transaction.
        """
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/transactions/{provider_tx_id}/verify",
                headers={"Authorization": f"Bearer {self.secret_key}"}
            )

        if resp.status_code != 200:
            return "pending"

        data = resp.json()
        status = data.get("data", {}).get("status", "pending")

        # Normalize status for the domain layer
        if status == "successful":
            return "success"
        elif status == "failed":
            return "failed"
        return "pending"

    def _detect_network(self, phone: str) -> str:
        """Simple helper to detect MTN vs Orange based on prefix."""
        # Standard Cameroon prefixes
        if phone.startswith(("67", "68", "650", "651", "652", "653", "654")):
            return "MTN"
        return "ORANGE"
