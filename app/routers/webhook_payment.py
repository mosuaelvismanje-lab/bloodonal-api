# app/routers/webhook_payment.py
import json
import hmac
import hashlib
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.services.payment_service import update_payment_status  # You will implement this

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/webhooks", tags=["payment-webhooks"])

# Secret used to validate provider webhook signatures
WEBHOOK_SECRET = "YOUR_WEBHOOK_SECRET_HERE"  # replace with env var


def verify_signature(payload: bytes, signature: str) -> bool:
    """
    HMAC (SHA256) verification for webhook authenticity.
    """
    try:
        expected = hmac.new(
            WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


@router.post("/payment")
async def payment_webhook(
        request: Request,
        db: AsyncSession = Depends(get_async_session),
        x_signature: Optional[str] = Header(None)
):
    """
    Generic webhook handler for payment provider callbacks.

    Expected payload example:
    {
        "transaction_id": "abc123",
        "status": "success",
        "provider": "stripe",
        "amount": 300,
        "user_id": "user123"
    }
    """

    raw_body = await request.body()

    # --- Step 1: Verify Signature ---
    if x_signature is None:
        logger.warning("Webhook rejected: Missing signature header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing signature"
        )

    if not verify_signature(raw_body, x_signature):
        logger.warning("Webhook rejected: Invalid signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )

    # --- Step 2: Parse Payload Safely ---
    try:
        payload = json.loads(raw_body.decode())
    except Exception:
        logger.exception("Webhook received invalid JSON")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    logger.info("Webhook received: %s", payload)

    # --- Step 3: Extract essential fields ---
    tx_id = payload.get("transaction_id")
    status_value = payload.get("status")

    if not tx_id or not status_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required fields"
        )

    # --- Step 4: Update DB ---
    try:
        await update_payment_status(db, transaction_id=tx_id, status=status_value)

    except Exception as exc:
        logger.exception("Failed to update payment status for tx=%s", tx_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update payment status"
        ) from exc

    # --- Step 5: Provider acknowledgement ---
    return {"success": True, "transaction_id": tx_id}
