import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status
from main import app
from app.api.dependencies import get_current_user, get_db_session
from unittest.mock import AsyncMock


# 1. Setup localized mocks
class MockUser:
    uid = "taxi_test_user_555"


async def override_get_current_user():
    return MockUser()


async def override_get_db_session():
    # Yield a mock db session to satisfy dependency injection
    yield AsyncMock()


@pytest.mark.asyncio
async def test_pay_taxi_success(monkeypatch):
    """
    Test successful taxi payment initiation.
    Aligned with the unified PaymentService pattern.
    """
    # Apply overrides
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db_session] = override_get_db_session

    # 2. Mock PaymentService.process_payment
    async def mock_process(*args, **kwargs):
        class Result:
            reference = "TAXI-REF-999"
            message = "Taxi ride payment initiated"

        return Result()

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.process_payment",
        mock_process
    )

    # 3. Valid Payload (Standardized PaymentRequest)
    payload = {
        "user_id": "taxi_test_user_555",
        "phone": "670000000"
    }

    # 4. Execute Request
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/v1/payments/taxi",
            json=payload,
            headers={"X-Idempotency-Key": "taxi-key-555"}
        )

    # 5. Assertions and Cleanup
    app.dependency_overrides.clear()
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert data["reference"] == "TAXI-REF-999"


@pytest.mark.asyncio
async def test_get_remaining_taxi_rides(monkeypatch):
    """
    Test remaining free taxi rides endpoint.
    FIXED: Added get_current_user override to prevent 422 error.
    """
    # ✅ Both dependencies must be overridden to satisfy the router
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db_session] = override_get_db_session

    # Mock the static method in PaymentService
    async def mock_remaining(*args, **kwargs):
        return 2

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.get_remaining_free_uses",
        mock_remaining
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # The URL must match the prefix in the router (without /v1 if using api_router)
        response = await ac.get("/v1/payments/taxi/remaining?user_id=taxi_test_user_555")

    # Clean up overrides after test
    app.dependency_overrides.clear()

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["remaining"] == 2