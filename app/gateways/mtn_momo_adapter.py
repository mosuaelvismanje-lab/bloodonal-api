import httpx
from typing import Dict, Any
from app.domain.interfaces import IPaymentGateway


class MTNMomoPaymentGateway(IPaymentGateway):
    BASE_URL = "https://proxy.momoapi.mtn.com/collection"

    def __init__(self, api_key: str, subscription_key: str, momo_account: str):
        self.api_key = api_key
        self.subscription_key = subscription_key
        self.momo_account = momo_account

    async def charge(self, amount: int, currency: str, reference: str, metadata: Dict[str, Any]):
        """
        Charge using MTN MoMo API.
        """
        payload = {
            "amount": str(amount),
            "currency": currency,
            "externalId": reference,
            "payer": {
                "partyIdType": "MSISDN",
                "partyId": metadata.get("phone"),
            },
            "payerMessage": "Service Payment",
            "payeeNote": "Thank you",
        }

        headers = {
            "X-Reference-Id": reference,
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "X-Target-Environment": "mtncameroon",
            "Authorization": f"Bearer {self.api_key}",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/v1_0/requesttopay",
                headers=headers,
                json=payload,
            )

        if resp.status_code not in (200, 202):
            raise Exception(f"MTN MoMo charge failed: {resp.text}")

        return {
            "status": "pending",
            "provider_ref": reference,
            "raw": resp.json() if resp.content else {},
        }
