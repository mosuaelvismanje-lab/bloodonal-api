#app/gateways/stripe_adapter
import uuid
import httpx
import logging
from typing import Dict, Any, Optional
from app.domain.gateways import IPaymentGateway, GatewayPaymentResponse

logger = logging.getLogger(__name__)


class StripeAdapter(IPaymentGateway):
    """
    Stripe adapter synchronized with the domain IPaymentGateway interface.
    Returns GatewayPaymentResponse for consistency across the app.
    """

    BASE_URL = "https://api.stripe.com/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def charge(
            self,
            phone: str,
            amount: int,
            description: Optional[str] = None,
            merchant_number: Optional[str] = None  # ✅ Added to satisfy interface signature
    ) -> GatewayPaymentResponse:
        """
        Initiates a Stripe PaymentIntent.
        Note: Stripe amounts are usually in subunits (cents).
        For XAF, verify if your account supports zero-decimal currency.
        """

        # Stripe expects application/x-www-form-urlencoded
        payload = {
            "amount": amount,
            "currency": "xaf",
            "description": description or "Consultation Fee",
            "metadata[phone]": phone,
        }

        # Optional: Store merchant_number in metadata for audit trails
        if merchant_number:
            payload["metadata[merchant_wallet]"] = merchant_number

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/payment_intents",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data=payload,
                )

            if resp.status_code >= 400:
                logger.error(f"Stripe API Error: {resp.text}")
                return GatewayPaymentResponse(
                    reference=f"stripe-err-{uuid.uuid4().hex[:6]}",
                    status="FAILED",
                    provider_raw_response=resp.json() if resp.text else {}
                )

            data = resp.json()
            provider_id = data.get("id")

            # Standardize the status (Stripe 'succeeded' -> Domain 'SUCCESS')
            stripe_status = data.get("status")
            final_status = "PENDING"

            if stripe_status == "succeeded":
                final_status = "SUCCESS"
            elif stripe_status in ["requires_payment_method", "requires_action"]:
                final_status = "PENDING"  # Often waiting for 3D Secure
            elif stripe_status in ["canceled"]:
                final_status = "FAILED"

            return GatewayPaymentResponse(
                reference=provider_id,
                status=final_status,
                ussd_string=None,  # Not used for Stripe
                provider_raw_response=data
            )

        except Exception as e:
            logger.error(f"Stripe connection failure: {str(e)}")
            return GatewayPaymentResponse(
                reference="connection-error",
                status="FAILED"
            )

    async def verify_transaction(self, reference: str) -> str:
        """
        ✅ Matches the IPaymentGateway interface signature.
        Checks the current status of a Stripe PaymentIntent.
        """
        try:
            async with httpx.AsyncClient() as client:
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
            logger.error(f"Error verifying Stripe transaction {reference}: {e}")
            return "PENDING"