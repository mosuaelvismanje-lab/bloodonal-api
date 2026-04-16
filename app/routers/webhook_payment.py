import json
import hmac
import hashlib
import logging
import os
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status, Body
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ FIX 1: Use the project-wide standardized session dependency
from app.api.dependencies import get_db_session
# ✅ Logic for wallet credit and usage unlocking
from app.services.payment_confirmation import confirm_payment

logger = logging.getLogger(__name__)

# ✅ PREFIX: Standardized as /webhooks.
# Main.py will include this as app.include_router(webhook_router)
router = APIRouter(prefix="/webhooks", tags=["payment-webhooks"])

# ✅ SECURITY: Strict Environment Loading
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

if not WEBHOOK_SECRET:
    logger.critical("🚨 SECURITY ALERT: WEBHOOK_SECRET is not set in environment variables!")


def verify_signature(payload: bytes, signature: str) -> bool:
    """
    Verify HMAC-SHA256 webhook signature to ensure request is from the provider.
    """
    if not WEBHOOK_SECRET:
        logger.error("Signature verification failed: WEBHOOK_SECRET is missing.")
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
            "reference": "REF-ABC-123"  # The reference generated in your payment router
        }),
        db: AsyncSession = Depends(get_db_session),
        x_signature: Optional[str] = Header(None, alias="x-signature"),
):
    """
    Automatic webhook handler.
    On success, it updates the Payment record and increments the UsageCounter.
    """

    # 1. Signature Verification (Security First)
    raw_body = await request.body()
    if not x_signature or not verify_signature(raw_body, x_signature):
        logger.warning("Webhook rejected: Unauthorized or Invalid signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )

    # 2. Extract Data
    payload = payload_in
    tx_id = payload.get("transaction_id")
    status_value = payload.get("status")
    payer_phone = payload.get("payer_phone")
    amount = payload.get("amount")
    reference = payload.get("reference")  # Crucial for linking back to your DB

    if not tx_id or not status_value:
        raise HTTPException(status_code=400, detail="Missing required fields")

    # 3. Process Success Flow
    # Standardizing for providers that might send "SUCCESSFUL" or "COMPLETED"

    if status_value.lower() in ["success", "successful", "completed"]:
        try:
            # ✅ confirm_payment should now:
            # 1. Update Payment model status to SUCCESS
            # 2. Link the tx_id to the payment reference
            # 3. Call UsageRepository.record_usage(paid=True) to increment the user's limit
            confirmed = await confirm_payment(
                db=db,
                transaction_id=tx_id,
                payer_phone=payer_phone,
                amount=amount,
                reference=reference
            )

            if not confirmed:
                logger.info(f"Webhook: Transaction {tx_id} was already processed or not found.")
            else:
                logger.info(f"✅ Service activated via webhook for {tx_id}")

        except Exception as exc:
            logger.exception("Automatic confirmation failed for tx=%s", tx_id)
            # We return 500 so the provider retries the webhook later
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal processing error"
            ) from exc
    else:
        logger.info(f"Webhook: Ignoring non-success status '{status_value}' for {tx_id}.")

    # 4. Acknowledge Provider (Always return 200/OK if we received it successfully)
    return {"success": True, "transaction_id": tx_id}