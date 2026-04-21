import pytest
from fastapi import status
from unittest.mock import AsyncMock
from app.models.payment import PaymentStatus


# =========================================================
# FREE FLOW TEST
# =========================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("client", ["blood_user_free_001"], indirect=True)
async def test_pay_blood_request_success(client, monkeypatch):
    """Test FREE PATH with service argument validation."""

    from app.schemas.payment import PaymentResponseOut
    from datetime import datetime, timezone, timedelta

    mock_out = PaymentResponseOut(
        success=True,
        status=PaymentStatus.SUCCESS,
        message="Free usage applied successfully",
        reference="FREE-TEST-REF",
        ussd_string=None,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=12)
    )

    mock_service = AsyncMock(return_value=mock_out)

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.process_payment",
        mock_service
    )

    response = await client.post(
        "/v1/blood-request-payments",
        json={"phone": "670556321"},
        headers={"X-Idempotency-Key": "blood-key-123"}
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["status"] == "SUCCESS"
    assert data["reference"] == "FREE-TEST-REF"

    # Ensure service called
    assert mock_service.call_count == 1

    _, kwargs = mock_service.call_args

    # ✅ SAFE ASSERTIONS
    assert kwargs["user_phone"] == "670556321"
    assert kwargs["category"] == "blood-request"

    # ✅ CORRECT USER ASSERTION
    assert kwargs["user_id"] == "blood_user_free_001"


# =========================================================
# PAID FLOW TEST
# =========================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("client", ["blood_user_paid_002"], indirect=True)
async def test_pay_blood_request_paid_path(client, monkeypatch):
    """Test PAID flow (USSD generation)."""

    from app.schemas.payment import PaymentResponseOut

    mock_out = PaymentResponseOut(
        success=True,
        status=PaymentStatus.PENDING,
        message="Please dial USSD.",
        reference="PAID-TEST-REF",
        ussd_string="*126*2*676657577*500#"
    )

    mock_service = AsyncMock(return_value=mock_out)

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.process_payment",
        mock_service
    )

    response = await client.post(
        "/v1/blood-request-payments",
        json={"phone": "677000000"},
        headers={"X-Idempotency-Key": "blood-paid-key"}
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["status"] == "PENDING"
    assert data["ussd_string"] == "*126*2*676657577*500#"

    assert mock_service.call_count == 1

    _, kwargs = mock_service.call_args

    # ✅ VALIDATE INPUT FLOW
    assert kwargs["user_phone"] == "677000000"
    assert kwargs["category"] == "blood-request"
    assert kwargs["user_id"] == "blood_user_paid_002"


# =========================================================
# REMAINING FREE USAGE TEST
# =========================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("client", ["blood_user_quota_003"], indirect=True)
async def test_get_remaining_blood_requests(client, monkeypatch):
    """Test quota checking endpoint."""

    mock_service = AsyncMock(return_value=3)

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.get_remaining_free_uses",
        mock_service
    )

    response = await client.get(
        "/v1/blood-request-payments/remaining",
        params={"category": "blood-request"}
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["remaining"] == 3

    assert mock_service.call_count == 1

    _, kwargs = mock_service.call_args

    # ✅ OPTIONAL BUT STRONG CHECK
    assert kwargs["user_id"] == "blood_user_quota_003"
    assert kwargs["category"] == "blood-request"