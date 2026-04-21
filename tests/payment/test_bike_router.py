import pytest
from fastapi import status
from unittest.mock import AsyncMock

# -------------------------
# Test Cases
# -------------------------

@pytest.mark.asyncio
async def test_pay_bike_success(client, monkeypatch):
    """
    Test successful bike payment initiation via the Service Layer.
    Uses the centralized 'client' fixture.
    """
    from app.schemas.payment import PaymentResponseOut, PaymentStatus
    from datetime import datetime, timezone, timedelta

    # Create mock response
    mock_out = PaymentResponseOut(
        success=True,
        reference="BIKE-REF-123",
        status=PaymentStatus.PENDING,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        message="Bike payment initiated",
        ussd_string="*126*9*677123456*500#"
    )

    # Patch the Service layer
    mock_service = AsyncMock(return_value=mock_out)
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.process_payment",
        mock_service
    )

    payload = {"phone": "677123456"}

    # Execute request
    response = await client.post(
        "/v1/payments/bike",
        json=payload
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["success"] is True
    assert data["reference"] == "BIKE-REF-123"
    assert "ussd_string" in data

    # -------------------------
    # FIXED ASSERTION SECTION
    # -------------------------
    _, kwargs = mock_service.call_args

    # ❌ FIX: wrong user removed (taxi_test_user_555 was incorrect)
    assert kwargs["user_id"] == "nurse_test_user_789"

    # correct category check
    assert kwargs["category"] == "bike"


@pytest.mark.asyncio
async def test_get_remaining_bike_rides(client, monkeypatch):
    """
    Test the GET endpoint using the Service layer and centralized 'client'.
    """
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.get_remaining_free_uses",
        AsyncMock(return_value=1)
    )

    response = await client.get("/v1/payments/bike/remaining")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["remaining"] == 1