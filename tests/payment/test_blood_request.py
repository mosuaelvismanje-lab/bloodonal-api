import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status
from main import app
from app.api.dependencies import get_current_user, get_db_session
from unittest.mock import AsyncMock

# -------------------------
# 1. Setup localized mocks (Same as Doctor Pattern)
# -------------------------
class MockUser:
    def __init__(self):
        self.uid = "blood_test_user_123"

async def override_get_current_user():
    return MockUser()

async def override_get_db_session():
    # Yield a mock db session to satisfy the dependency
    yield AsyncMock()

# Apply overrides globally for this test module
app.dependency_overrides[get_current_user] = override_get_current_user
app.dependency_overrides[get_db_session] = override_get_db_session

@pytest.mark.asyncio
async def test_pay_blood_request_success(monkeypatch):
    """
    Test successful blood request payment initiation.
    Fully aligned with Doctor/Bike payload requirements.
    """

    # 2. Mock ConsultationUseCase.handle (Domain logic)
    async def mock_handle(*args, **kwargs):
        # We return a string ID that the router wraps in "transaction:{tx_id}"
        return "mock_tx_uuid_789"

    monkeypatch.setattr(
        "app.domain.usecases.ConsultationUseCase.handle",
        mock_handle
    )

    # 3. Valid Payload (ADDED user_id and phone to align with Schema)
    payload = {
        "user_id": "blood_test_user_123",
        "phone": "670000000"
    }

    # 4. Execute Request
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/v1/payments/blood-request",
            json=payload,
            headers={"X-Idempotency-Key": "blood-key-123"}
        )

    # 5. Assertions
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    # Verify the router properly formatted the message string
    assert "transaction:mock_tx_uuid_789" in data["message"]
    assert data["status"] == "PENDING"

@pytest.mark.asyncio
async def test_get_remaining_blood_requests(monkeypatch):
    """
    Test remaining free blood requests endpoint.
    Aligned with Doctor GET pattern.
    """

    # 1. Mock the Repository count method (Internal Repository Mock)
    async def mock_count(*args, **kwargs):
        # Simulate that the user has already used 2 requests
        return 2

    monkeypatch.setattr(
        "app.data.repositories.UsageRepository.count",
        mock_count
    )

    # 2. Execute Request
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Passes user_id as a query param just like Doctor GET
        response = await ac.get(
            "/v1/payments/blood-request/remaining?user_id=blood_test_user_123"
        )

    # 3. Assertions
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "remaining" in data
    # Router logic: max(0, free_limit(0) - used(2)) = 0
    assert data["remaining"] == 0

    # Clean up overrides after tests
    app.dependency_overrides.clear()