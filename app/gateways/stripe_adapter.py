import httpx
from app.domain.interfaces import IPaymentGateway
from typing import Dict, Any


class StripePaymentGateway(IPaymentGateway):
    BASE_URL = "https://api.stripe.com/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def charge(self, amount: int, currency: str, reference: str, metadata: Dict[str, Any]):
        """
        Charge via Stripe API.
        """
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/payment_intents",
                headers={"Authorization": f"Bearer {self.api_key}"},
                data={
                    "amount": amount,
                    "currency": currency,
                    "metadata[reference]": reference,
                }
            )

        if resp.status_code != 200:
            raise Exception(f"Stripe charge failed: {resp.text}")

        data = resp.json()
        return {
            "status": "success",
            "provider_ref": data.get("id"),
            "raw": data,
        }
