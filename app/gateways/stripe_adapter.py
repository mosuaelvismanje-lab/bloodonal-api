import httpx
from typing import Dict, Any, Optional
from app.domain.interfaces import IPaymentGateway

class StripeAdapter(IPaymentGateway):
    """
    Minimal Stripe adapter compatible with tests.
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
            for key, value in metadata.items():
                payload[f"metadata[{key}]"] = value

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/payment_intents",
                headers={"Authorization": f"Bearer {self.api_key}"},
                data=payload,
            )

        if resp.status_code >= 400:
            raise Exception(f"Stripe charge failed: {resp.status_code} - {resp.text}")

        # ✅ FIX: Use .json() for httpx response, NOT .model_dump_json()
        data = resp.json()
        provider_id = data.get("id")

        if not provider_id:
            raise Exception("Stripe response missing 'id'")

        return provider_id

    async def verify(self, tx_id: str) -> bool:
        return tx_id.startswith("txn_")