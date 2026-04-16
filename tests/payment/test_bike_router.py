import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status
from main import app
from app.api.dependencies import get_current_user, get_db_session

# ✅ Updated Mock Class to match the SQLAlchemyUsageRepository logic
from app.repositories.usage_repo import SQLAlchemyUsageRepository

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

    # 1. Mock the new Repository methods so we don't need a real DB
    async def mock_count_uses(*args, **kwargs):
        return 0  # Assume 0 uses so we test the "Free" path

    async def mock_record_usage(*args, **kwargs):
        return None

    # ✅ Redirecting monkeypatch to the new repository path
    monkeypatch.setattr(
        "app.repositories.usage_repo.SQLAlchemyUsageRepository.count_uses",
        mock_count_uses
    )
    monkeypatch.setattr(
        "app.repositories.usage_repo.SQLAlchemyUsageRepository.record_usage",
        mock_record_usage
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
    data = response.json()
    assert data["success"] is True
    assert data["status"] == "SUCCESS"  # Since count was 0, it hits the FREE path

@pytest.mark.asyncio
async def test_get_remaining_bike_rides(monkeypatch):
    """
    Test the GET endpoint for remaining free rides.
    """
    # 1. Mock the NEW Repository count_uses method
    # ✅ FIX: Target the new SQLAlchemyUsageRepository
    async def mock_count_uses(self, user_id: str, service: str):
        assert service == "bike"
        return 1  # Simulate 1 ride already used

    monkeypatch.setattr(
        "app.repositories.usage_repo.SQLAlchemyUsageRepository.count_uses",
        mock_count_uses
    )

    # 2. Execute Request
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ✅ FIX: Ensure the URL includes /v1 to match the updated router
        response = await ac.get(
            "/v1/payments/bike/remaining",
            headers={"Authorization": "Bearer fake-token"}
        )

    # 3. Debugging (only shows if assertion fails)
    if response.status_code != 200:
        print(f"Error Body: {response.json()}")

    # 4. Assertions
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "remaining" in data
    # If limit is 2 and we mocked used as 1, remaining should be 1
    assert data["remaining"] == 1