import pytest
from fastapi import status
from unittest.mock import AsyncMock


# =========================================================
# PAY DOCTOR CONSULT (SUCCESS PATH)
# =========================================================
@pytest.mark.asyncio
async def test_pay_doctor_consult_success(client, monkeypatch):
    """
    Test successful doctor consultation payment initiation
    and verify correct payload passed to PaymentService.
    """

    from app.schemas.payment import PaymentResponseOut, PaymentStatus
    from datetime import datetime, timezone, timedelta

    mock_out = PaymentResponseOut(
        success=True,
        reference="DOC-REF-789",
        status=PaymentStatus.PENDING,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        message="Payment initiated",
        ussd_string="*123#"
    )

    mock_service = AsyncMock(return_value=mock_out)

    # 🔥 CRITICAL FIX: PATCH THE ACTUAL IMPORT PATH USED IN ROUTER
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.process_payment",
        mock_service
    )

    payload = {"phone": "670000000"}

    response = await client.post(
        "/v1/payments/doctor-consults",
        json=payload,
        headers={"X-Idempotency-Key": "doc-idempotency-789"}
    )

    assert response.status_code == status.HTTP_200_OK

    # Verify service was called
    mock_service.assert_called_once()

    _, kwargs = mock_service.call_args

    # 🔥 FIXED: match real router signature (IMPORTANT)
    assert kwargs["user_phone"] == "670000000"
    assert kwargs["category"] == "doctor"
    assert "user_id" in kwargs


# =========================================================
# GET REMAINING DOCTOR CONSULTS
# =========================================================
@pytest.mark.asyncio
async def test_get_remaining_doctor_consults(client, monkeypatch):
    """
    Test remaining free doctor consults endpoint.
    """

    mock_service = AsyncMock(return_value=5)

    # 🔥 FIX: correct patch path used in router
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.get_remaining_free_uses",
        mock_service
    )

    response = await client.get("/v1/payments/doctor-consults/remaining")

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["remaining"] == 5