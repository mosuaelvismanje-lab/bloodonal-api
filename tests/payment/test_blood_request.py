import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status
from main import app
from app.api.dependencies import get_current_user, get_db
from app.models.payment import PaymentStatus
from unittest.mock import AsyncMock
from datetime import datetime, timezone, timedelta


# -------------------------
# 1. Standardized Mocks
# -------------------------
class MockUser:
    uid = "blood_test_user_123"


async def override_get_current_user():
    return MockUser()


async def override_get_db():
    mock_db = AsyncMock()
    yield mock_db


# -------------------------
# 2. Test Suite
# -------------------------
@pytest.fixture
async def client():
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_pay_blood_request_success(client, monkeypatch):
    """Test FREE PATH with service argument validation."""
    from app.schemas.payment import PaymentResponseOut

    mock_out = PaymentResponseOut(
        success=True,
        status=PaymentStatus.SUCCESS,
        message="Free usage applied successfully",
        reference="FREE-TEST-REF",
        ussd_string=None,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=12)
    )

    # Patch and verify service calls
    mock_service = AsyncMock(return_value=mock_out)
    monkeypatch.setattr("app.services.payment_service.PaymentService.process_payment", mock_service)

    response = await client.post(
        "/v1/blood-request-payments",
        json={"phone": "670556321"},
        headers={"X-Idempotency-Key": "blood-key-123"}
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "SUCCESS"

    # Verify the router passed the correct arguments to the Service Engine
    mock_service.assert_called_once()
    _, kwargs = mock_service.call_args
    assert kwargs['user_id'] == "blood_test_user_123"
    assert kwargs['user_phone'] == "670556321"


@pytest.mark.asyncio
async def test_pay_blood_request_paid_path(client, monkeypatch):
    """Test PAID flow (MTN/Orange detection)."""
    from app.schemas.payment import PaymentResponseOut

    mock_out = PaymentResponseOut(
        success=True,
        status=PaymentStatus.PENDING,
        message="Please dial USSD.",
        reference="PAID-TEST-REF",
        ussd_string="*126*2*676657577*500#"
    )

    monkeypatch.setattr("app.services.payment_service.PaymentService.process_payment", AsyncMock(return_value=mock_out))

    response = await client.post("/v1/blood-request-payments", json={"phone": "677000000"})

    data = response.json()
    assert data["status"] == "PENDING"
    assert data["ussd_string"].startswith("*126*")


@pytest.mark.asyncio
async def test_get_remaining_blood_requests(client, monkeypatch):
    """Test quota checking endpoint."""
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.get_remaining_free_uses",
        AsyncMock(return_value=3)
    )

    response = await client.get("/v1/blood-request-payments/remaining", params={"category": "blood-request"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["remaining"] == 3