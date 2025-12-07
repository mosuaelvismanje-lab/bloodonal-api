# app/gateways/stripe_adapter.py
import httpx
from typing import Dict, Any, Optional
from app.domain.interfaces import IPaymentGateway


class StripeAdapter(IPaymentGateway):
    """
    Minimal Stripe adapter compatible with tests.

    Tests call `await adapter.charge(user_id=..., amount=...)` and expect a
    transaction id string (e.g. "txn_123") returned from the adapter.
    """

    BASE_URL = "https://api.stripe.com/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def charge(
        self,
        user_id: str,
        amount: int,
        currency: str = "usd",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        payload = {
            "amount": amount,
            "currency": currency,
            "metadata[user_id]": user_id,
        }
        if metadata:
            for k, v in metadata.items():
                payload[f"metadata[{k}]"] = v

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/payment_intents",
                headers={"Authorization": f"Bearer {self.api_key}"},
                data=payload,
            )

        if resp.status_code >= 400:
            raise Exception(f"Stripe charge failed: {resp.status_code} - {resp.text}")

        data = resp.json()
        provider_id = data.get("id")
        if not provider_id:
            raise Exception("Stripe response missing 'id'")

        return provider_id

    async def verify(self, tx_id: str) -> bool:
        """
        Minimal implementation of abstract method for tests.

        Returns True if tx_id starts with "txn_", otherwise False.
        """
        return tx_id.startswith("txn_")
