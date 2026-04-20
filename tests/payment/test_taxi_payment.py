import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status
from main import app
from app.api.dependencies import get_current_user, get_db
from unittest.mock import AsyncMock


# -------------------------
# 1. Standardized Mocks
# -------------------------
class MockUser:
    uid = "taxi_test_user_555"


async def override_get_current_user():
    return MockUser()


async def override_get_db():
    yield AsyncMock()


@pytest.fixture
async def client():
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# -------------------------
# 2. Test Cases
# -------------------------

@pytest.mark.asyncio
async def test_pay_taxi_success(client, monkeypatch):
    """
    Test successful taxi payment with engine argument verification.
    """
    from app.schemas.payment import PaymentResponseOut, PaymentStatus
    from datetime import datetime, timezone, timedelta

    mock_out = PaymentResponseOut(
        success=True,
        reference="TAXI-REF-999",
        status=PaymentStatus.PENDING,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        message="Taxi ride payment initiated",
        ussd_string="*123#"
    )

    # ✅ FIX: Mock service and prepare to verify call arguments
    mock_service = AsyncMock(return_value=mock_out)
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.process_payment",
        mock_service
    )

    payload = {"phone": "670000000"}

    response = await client.post(
        "/v1/payments/taxi",
        json=payload,
        headers={"X-Idempotency-Key": "taxi-key-555"}
    )

    assert response.status_code == status.HTTP_200_OK

    # ✅ Verify that the router passes the correct mapped data to the PaymentService Engine
    mock_service.assert_called_once()
    _, kwargs = mock_service.call_args
    assert kwargs['user_id'] == "taxi_test_user_555"
    assert kwargs['user_phone'] == "670000000"
    assert kwargs['category'] == "taxi"  # Engine expects 'taxi' category


@pytest.mark.asyncio
async def test_get_remaining_taxi_rides(client, monkeypatch):
    """
    Test the GET endpoint using the Service layer to ensure consistency.
    """
    mock_service = AsyncMock(return_value=2)
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.get_remaining_free_uses",
        mock_service
    )

    response = await client.get("/v1/payments/taxi/remaining")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["remaining"] == 2

    # Verify the router passes the correct category
    mock_service.assert_called_once()
    assert mock_service.call_args[0][2] == "taxi"