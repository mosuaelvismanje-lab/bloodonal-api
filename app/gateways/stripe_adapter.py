import uuid
import httpx
import logging
from typing import Dict, Any, Optional
from app.domain.gateways import IPaymentGateway, GatewayPaymentResponse

logger = logging.getLogger(__name__)


class StripeAdapter(IPaymentGateway):
    """
    Stripe adapter synchronized with the domain IPaymentGateway interface.
    Handles global credit/debit card processing while maintaining
    the same interface as local Mobile Money providers.
    """

    BASE_URL = "https://api.stripe.com/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def charge(
            self,
            phone: str,
            amount: int,
            description: Optional[str] = None,
            merchant_number: Optional[str] = None  # ✅ Interface parity
    ) -> GatewayPaymentResponse:
        """
        Initiates a Stripe PaymentIntent.
        Args:
            phone: Customer phone number (stored in metadata).
            amount: Transaction amount (Stripe expects subunit e.g. 100 for 1.00).
            description: Label for the Stripe dashboard.
            merchant_number: Unused by Stripe, but required by interface.
        """

        # Stripe uses application/x-www-form-urlencoded
        payload = {
            "amount": amount,
            "currency": "xaf",
            "description": description or "Bloodonal Service Fee",
            "metadata[customer_phone]": phone,
        }

        # Storing the merchant_number in metadata if provided for audit parity
        if merchant_number:
            payload["metadata[merchant_wallet_ref]"] = merchant_number

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/payment_intents",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data=payload,
                )

            if resp.status_code >= 400:
                logger.error(f"Stripe API Error: {resp.status_code} - {resp.text}")
                return GatewayPaymentResponse(
                    reference=f"stripe-err-{uuid.uuid4().hex[:6]}",
                    status="FAILED",
                    provider_raw_response=resp.json() if resp.text else {}
                )

            data = resp.json()
            provider_id = data.get("id")

            # Map Stripe statuses to Domain statuses
            # Stripe states: requires_payment_method, requires_confirmation,
            # requires_action, processing, requires_capture, canceled, succeeded
            stripe_status = data.get("status")
            final_status = "PENDING"

            if stripe_status == "succeeded":
                final_status = "SUCCESS"
            elif stripe_status in ["canceled"]:
                final_status = "FAILED"
            # 'requires_action' usually means 3D Secure is pending

            return GatewayPaymentResponse(
                reference=provider_id,
                status=final_status,
                ussd_string=None,  # Not applicable for Stripe
                provider_raw_response=data
            )

        except Exception as e:
            logger.error(f"Stripe network failure: {str(e)}")
            return GatewayPaymentResponse(
                reference="connection-error",
                status="FAILED"
            )

    async def verify_transaction(self, reference: str) -> str:
        """
        Polls the current status of a Stripe PaymentIntent.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/payment_intents/{reference}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )

            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status")
                if status == "succeeded":
                    return "SUCCESS"
                if status in ["requires_payment_method", "canceled"]:
                    return "FAILED"

            return "PENDING"
        except Exception as e:
            logger.error(f"Failed to verify Stripe reference {reference}: {e}")
            return "PENDING"