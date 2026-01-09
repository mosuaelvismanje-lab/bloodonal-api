import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status
from main import app
from app.api.dependencies import get_current_user, get_db_session


# 1. Setup localized mocks to isolate this test file
class MockUser:
    def __init__(self):
        self.uid = "user_bike_test_123"


async def override_get_current_user():
    return MockUser()


async def override_get_db():
    yield "mock_session"


# Apply the overrides to the app instance
app.dependency_overrides[get_current_user] = override_get_current_user
app.dependency_overrides[get_db_session] = override_get_db


@pytest.mark.asyncio
async def test_pay_bike_success(monkeypatch):
    """
    Test successful bike payment initiation.
    Matches schema requirements (9-digit phone) and router logic.
    """

    # 2. Mock the handle method in the usecase
    # This prevents the test from actually hitting your Neon database
    async def mock_handle(*args, **kwargs):
        return "mock-bike-tx-id"

    monkeypatch.setattr(
        "app.domain.usecases.ConsultationUseCase.handle",
        mock_handle
    )

    # 3. Valid Payload (exactly 9 digits for 'phone' as per your schema)
    payload = {
        "phone": "677123456",
        "metadata": {"source": "mobile_app"}
    }

    # 4. Use ASGITransport for testing FastAPI directly
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/v1/payments/bike/",  # Ensure the trailing slash matches your router
            json=payload,
            headers={"Authorization": "Bearer fake-token"}
        )

    # 5. Assertions
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert "mock-bike-tx-id" in data["message"]
    assert data["status"] == "PENDING"