import pytest
from unittest.mock import MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
from fastapi import status
from main import app
from app.api.dependencies import get_current_user, get_db

# -------------------------
# 1. Standardized Mocks
# -------------------------
class MockUser:
    def __init__(self):
        self.uid = "user_bike_test_123"

async def override_get_current_user():
    return MockUser()

async def override_get_db():
    mock_session = AsyncMock()
    # Ensure commit and rollback are awaitable
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    yield mock_session

@pytest.fixture(autouse=True)
def setup_overrides():
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()

# -------------------------
# 2. Test Cases
# -------------------------

@pytest.mark.asyncio
async def test_pay_bike_success(monkeypatch):
    """
    Test successful bike payment initiation via the Service Layer.
    """
    from app.schemas.payment import PaymentResponseOut, PaymentStatus
    from datetime import datetime, timezone, timedelta

    # Create a mock response matching the PaymentService return type
    mock_out = PaymentResponseOut(
        success=True,
        reference="BIKE-REF-123",
        status=PaymentStatus.PENDING,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        message="Bike payment initiated",
        ussd_string="*126*9*677123456*500#"
    )

    # Patch the Service layer
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.process_payment",
        AsyncMock(return_value=mock_out)
    )

    payload = {"phone": "677123456"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/v1/payments/bike",
            json=payload,
            headers={"Authorization": "Bearer fake-token"}
        )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert data["reference"] == "BIKE-REF-123"
    assert "ussd_string" in data

@pytest.mark.asyncio
async def test_get_remaining_bike_rides(monkeypatch):
    """
    Test the GET endpoint using the Service layer.
    """
    # Patch the Service layer method
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.get_remaining_free_uses",
        AsyncMock(return_value=1)
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/v1/payments/bike/remaining",
            headers={"Authorization": "Bearer fake-token"}
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["remaining"] == 1