import pytest
from fastapi import status
from unittest.mock import AsyncMock


# =========================================================
# BIKE PAYMENT TEST
# =========================================================
@pytest.mark.asyncio
async def test_pay_bike_success(client, monkeypatch):
    """
    Test successful bike payment initiation via Service layer.
    Uses centralized client fixture (user injected per test).
    """

    from app.schemas.payment import PaymentResponseOut, PaymentStatus
    from datetime import datetime, timezone, timedelta

    # -------------------------
    # MOCK RESPONSE
    # -------------------------
    mock_out = PaymentResponseOut(
        success=True,
        reference="BIKE-REF-123",
        status=PaymentStatus.PENDING,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        message="Bike payment initiated",
        ussd_string="*126*9*677123456*500#"
    )

    mock_service = AsyncMock(return_value=mock_out)

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.process_payment",
        mock_service
    )

    payload = {"phone": "677123456"}

    # -------------------------
    # REQUEST
    # -------------------------
    response = await client.post(
        "/v1/payments/bike",
        json=payload
    )

    # -------------------------
    # ASSERT RESPONSE
    # -------------------------
    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["success"] is True
    assert data["reference"] == "BIKE-REF-123"
    assert data["status"] == "PENDING"
    assert data["ussd_string"] == "*126*9*677123456*500#"

    # -------------------------
    # ASSERT SERVICE CALL
    # -------------------------
    assert mock_service.call_count == 1

    _, kwargs = mock_service.call_args

    # ✅ correct assertions
    assert kwargs["user_phone"] == "677123456"
    assert kwargs["category"] == "bike"

    # ✅ FIXED: do NOT access client.app
    assert "user_id" in kwargs
    assert kwargs["user_id"] is not None


# =========================================================
# REMAINING BIKE RIDES TEST
# =========================================================
@pytest.mark.asyncio
async def test_get_remaining_bike_rides(client, monkeypatch):
    """
    Test GET remaining free rides endpoint using service layer.
    """

    mock_service = AsyncMock(return_value=1)

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.get_remaining_free_uses",
        mock_service
    )

    response = await client.get("/v1/payments/bike/remaining")

    # -------------------------
    # ASSERT RESPONSE
    # -------------------------
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["remaining"] == 1

    # -------------------------
    # ASSERT SERVICE CALL
    # -------------------------
    assert mock_service.call_count == 1

    _, kwargs = mock_service.call_args

    # ✅ ensure correct category passed
    assert kwargs["category"] == "bike"

    # ✅ FIXED: safe user check
    assert "user_id" in kwargs
    assert kwargs["user_id"] is not None