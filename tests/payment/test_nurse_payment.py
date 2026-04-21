import pytest
from fastapi import status
from unittest.mock import AsyncMock


# -------------------------
# Test Cases
# -------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("client", ["nurse_test_user_789"], indirect=True)
async def test_pay_nurse_success(client, monkeypatch):
    """
    Test successful nurse service payment with engine argument verification.
    Uses the centralized 'client' fixture from tests/conftest.py.
    """

    from app.schemas.payment import PaymentResponseOut, PaymentStatus
    from datetime import datetime, timezone, timedelta

    mock_out = PaymentResponseOut(
        success=True,
        reference="NURSE-REF-123",
        status=PaymentStatus.PENDING,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        message="Nurse service initiated",
        ussd_string="*123#"
    )

    # Patch service
    mock_service = AsyncMock(return_value=mock_out)

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.process_payment",
        mock_service
    )

    payload = {"phone": "670000000"}

    response = await client.post(
        "/v1/payments/nurse-services",
        json=payload,
        headers={"X-Idempotency-Key": "nurse-test-key-123"}
    )

    assert response.status_code == status.HTTP_200_OK

    # Ensure service was called
    assert mock_service.call_count == 1

    _, kwargs = mock_service.call_args

    # ✅ VALID ASSERTIONS
    assert kwargs["user_phone"] == "670000000"
    assert kwargs["category"] == "nurse-services"

    # ✅ CORRECT USER ASSERTION (comes from parametrize)
    assert kwargs["user_id"] == "nurse_test_user_789"