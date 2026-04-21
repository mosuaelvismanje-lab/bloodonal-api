import pytest
from fastapi import status
from unittest.mock import AsyncMock


# =========================================================
# NURSE PAYMENT TEST
# =========================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("client", ["nurse_test_user_789"], indirect=True)
async def test_pay_nurse_success(client, monkeypatch):

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

    # -------------------------
    # ASSERT RESPONSE
    # -------------------------
    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["success"] is True
    assert data["reference"] == "NURSE-REF-123"
    assert data["status"] == "PENDING"
    assert data["ussd_string"] == "*123#"

    # -------------------------
    # ASSERT SERVICE CALL
    # -------------------------
    assert mock_service.call_count == 1

    _, kwargs = mock_service.call_args

    assert kwargs["user_phone"] == "670000000"
    assert kwargs["category"] == "nurse-services"

    # ✅ strict and consistent user validation
    assert kwargs["user_id"] == client.test_user.uid