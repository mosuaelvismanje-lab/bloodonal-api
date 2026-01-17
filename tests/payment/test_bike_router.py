import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status
from main import app
from app.api.dependencies import get_current_user, get_db_session

# -------------------------
# 1. Setup localized mocks
# -------------------------
class MockUser:
    def __init__(self):
        self.uid = "user_bike_test_123"

async def override_get_current_user():
    return MockUser()

async def override_get_db():
    # We yield a string because we are monkeypatching the Repositories
    # that would normally use this session.
    yield "mock_session"

# Apply the overrides to the app instance globally for this test session
app.dependency_overrides[get_current_user] = override_get_current_user
app.dependency_overrides[get_db_session] = override_get_db

@pytest.mark.asyncio
async def test_pay_bike_success(monkeypatch):
    """
    Test successful bike payment initiation.
    """

    # 2. Mock UseCase __init__
    def mock_init(self, usage_repo, payment_gateway, call_gateway, chat_gateway):
        pass

    monkeypatch.setattr(
        "app.domain.usecases.ConsultationUseCase.__init__",
        mock_init
    )

    # 3. Mock UseCase handle method
    async def mock_handle(*args, **kwargs):
        return "mock-bike-tx-id"

    monkeypatch.setattr(
        "app.domain.usecases.ConsultationUseCase.handle",
        mock_handle
    )

    # 4. Valid Payload
    payload = {
        "phone": "677123456",
        "metadata": {"source": "mobile_app"}
    }

    # 5. Execute Request
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/v1/payments/bike",
            json=payload,
            headers={
                "Authorization": "Bearer fake-token",
                "X-Idempotency-Key": "test-idempotency-key-123"
            }
        )

    # 6. Assertions
    assert response.status_code == status.HTTP_200_OK
    # ✅ FIX: HTTPX Response uses .json(), not .model_dump_json()
    data = response.json()
    assert data["success"] is True
    assert "mock-bike-tx-id" in data["message"]
    assert data["status"] == "PENDING"

@pytest.mark.asyncio
async def test_get_remaining_bike_rides(monkeypatch):
    """
    Test the GET endpoint for remaining free rides.
    """
    # 1. Mock the Repository count method
    async def mock_count(self, user_id: str, service: str):
        assert service == "bike"
        return 2  # Simulate 2 rides already used

    monkeypatch.setattr(
        "app.data.repositories.UsageRepository.count",
        mock_count
    )

    # 2. Execute Request
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/payments/bike/remaining?user_id=test_123")

    # 3. Debugging (only shows if assertion fails)
    if response.status_code != 200:
        # ✅ FIX: Use .json() here as well
        print(f"Error Body: {response.json()}")

    # 4. Assertions
    assert response.status_code == status.HTTP_200_OK
    # ✅ FIX: Use .json() to get the dictionary
    data = response.json()
    assert "remaining" in data
    assert data["remaining"] >= 0
