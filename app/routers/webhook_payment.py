import hmac
import hashlib
import logging
import os
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.services.payment_confirmation import confirm_payment

logger = logging.getLogger("bloodonal")

# =====================================================
# ROUTER
# =====================================================
router = APIRouter(
    prefix="/webhooks",
    tags=["payment-webhooks"],
    redirect_slashes=False
)

# =====================================================
# SECURITY CONFIG
# =====================================================
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

if not WEBHOOK_SECRET:
    logger.critical(
        "🚨 SECURITY ALERT: WEBHOOK_SECRET is not set! Webhook security is compromised."
    )


def verify_signature(payload: bytes, signature: str) -> bool:
    if not WEBHOOK_SECRET:
        return False

    try:
        expected = hmac.new(
            WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, signature)
    except Exception:
        logger.exception("Error verifying webhook signature")
        return False


# =====================================================
# WEBHOOK ENDPOINT
# =====================================================
@router.post("/payment")
async def payment_webhook(
    request: Request,

    # ✅ FIXED: replaced deprecated "example=" with "examples="
    payload_in: Dict[str, Any] = Body(
        ...,
        examples={
            "default": {
                "summary": "Sample payment webhook payload",
                "value": {
                    "transaction_id": "TXN-998877",
                    "status": "success",
                    "amount": 500,
                    "payer_phone": "237670000000",
                    "reference": "REF-ABC-123"
                }
            }
        }
    ),

    db: AsyncSession = Depends(get_db),
    x_signature: Optional[str] = Header(None, alias="x-signature"),
):
    """
    2026 Standardized Webhook Handler.
    Validates provider callback and confirms payment.
    """

    # 1. Verify signature
    raw_body = await request.body()

    if not x_signature or not verify_signature(raw_body, x_signature):
        logger.warning(
            "Webhook rejected: Unauthorized request from %s",
            request.client.host if request.client else "unknown"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )

    # 2. Extract fields
    tx_id = payload_in.get("transaction_id")
    status_value = payload_in.get("status")
    payer_phone = payload_in.get("payer_phone")
    amount = payload_in.get("amount")
    reference = payload_in.get("reference")

    if not tx_id or not status_value:
        raise HTTPException(status_code=400, detail="Missing required transaction fields")

    # 3. Handle success flow
    if status_value.lower() in ["success", "successful", "completed"]:
        try:
            confirmed = await confirm_payment(
                db=db,
                transaction_id=tx_id,
                payer_phone=payer_phone,
                amount=amount,
                reference=reference
            )

            if confirmed:
                logger.info("✅ Payment confirmed via webhook: %s", reference)
            else:
                logger.info("ℹ️ Already processed or missing payment: %s", tx_id)

        except Exception as exc:
            logger.exception("Webhook processing failed tx=%s", tx_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal processing error"
            ) from exc

    else:
        logger.info("Ignored webhook status '%s' for tx=%s", status_value, tx_id)

    # 4. Always acknowledge provider
    return {"success": True, "transaction_id": tx_id}