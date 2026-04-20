import hmac
import hashlib
import logging
import os
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status, Body
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Aligned: Use the project-wide standardized session dependency
from app.api.dependencies import get_current_user, get_db
# ✅ Logic for wallet credit and usage unlocking
from app.services.payment_confirmation import confirm_payment

logger = logging.getLogger("bloodonal")

# --- FIX: Prefix standardized to /webhooks ---
# This will resolve to /v1/webhooks via the main.py v1 router loop
router = APIRouter(
    prefix="/webhooks",
    tags=["payment-webhooks"],
    redirect_slashes=False
)

# ✅ SECURITY: Strict Environment Loading
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

if not WEBHOOK_SECRET:
    logger.critical("🚨 SECURITY ALERT: WEBHOOK_SECRET is not set! Webhook security is compromised.")


def verify_signature(payload: bytes, signature: str) -> bool:
    """
    Verify HMAC-SHA256 webhook signature to ensure the request is from the provider.
    """
    if not WEBHOOK_SECRET:
        return False

    try:
        expected = hmac.new(
            WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        # compare_digest prevents timing attacks
        return hmac.compare_digest(expected, signature)
    except Exception:
        logger.exception("Error verifying webhook signature")
        return False


@router.post("/payment")
async def payment_webhook(
        request: Request,
        payload_in: Dict[str, Any] = Body(..., example={
            "transaction_id": "TXN-998877",
            "status": "success",
            "amount": 500,
            "payer_phone": "237670000000",
            "reference": "REF-ABC-123"
        }),
        db: AsyncSession = Depends(get_db),
        x_signature: Optional[str] = Header(None, alias="x-signature"),
):
    """
    2026 Standardized Webhook Handler.
    Validates incoming provider signals, updates Payment records, and unlocks service usage.
    """

    # 1. Signature Verification (The "Guardian" Step)
    raw_body = await request.body()
    if not x_signature or not verify_signature(raw_body, x_signature):
        logger.warning("Webhook rejected: Unauthorized or Invalid signature from IP: %s", request.client.host)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )

    # 2. Extract Data
    tx_id = payload_in.get("transaction_id")
    status_value = payload_in.get("status")
    payer_phone = payload_in.get("payer_phone")
    amount = payload_in.get("amount")
    reference = payload_in.get("reference")

    if not tx_id or not status_value:
        raise HTTPException(status_code=400, detail="Missing required transaction fields")

    # 3. Success Flow Processing
    # Standardizing across multiple 2026 provider formats
    if status_value.lower() in ["success", "successful", "completed"]:
        try:
            # ✅ confirm_payment handles the following atomicity:
            # - Updates Payment status to SUCCESS
            # - Increments UsageCounter via Repository
            # - Records the Transaction ID
            confirmed = await confirm_payment(
                db=db,
                transaction_id=tx_id,
                payer_phone=payer_phone,
                amount=amount,
                reference=reference
            )

            if not confirmed:
                logger.info("Webhook: Transaction %s was already processed or reference not found.", tx_id)
            else:
                logger.info("✅ Service unlocked via webhook for Reference: %s", reference)

        except Exception as exc:
            logger.exception("Automatic confirmation failed for tx=%s", tx_id)
            # 500 signals the provider to retry later
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal processing error"
            ) from exc
    else:
        logger.info("Webhook: Ignoring non-success status '%s' for %s.", status_value, tx_id)

    # 4. Acknowledge Provider
    return {"success": True, "transaction_id": tx_id}