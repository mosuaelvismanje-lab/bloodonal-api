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
    # Returning a string is fine because we mock the UseCase layer
    yield "mock_session"


# Apply the overrides to the app instance
app.dependency_overrides[get_current_user] = override_get_current_user
app.dependency_overrides[get_db_session] = override_get_db


@pytest.mark.asyncio
async def test_pay_bike_success(monkeypatch):
    """
    Test successful bike payment initiation.
    Matches the 4-argument ConsultationUseCase and specific BikePayment schemas.
    """

    # 2. Mock the __init__ to accept the 4 positional arguments required by the UseCase
    # (usage_repo, payment_gateway, call_gateway, chat_gateway)
    def mock_init(self, usage_repo, payment_gateway, call_gateway, chat_gateway):
        pass

    monkeypatch.setattr(
        "app.domain.usecases.ConsultationUseCase.__init__",
        mock_init
    )

    # 3. Mock the handle method
    # Must match the signature called in the router: (user_id, service, phone, idempotency_key)
    async def mock_handle(self, user_id, service, phone, idempotency_key=None):
        return "mock-bike-tx-id"

    monkeypatch.setattr(
        "app.domain.usecases.ConsultationUseCase.handle",
        mock_handle
    )

    # 4. Valid Payload
    # Enforces the 9-digit phone validation now present in BikePaymentRequest
    payload = {
        "phone": "677123456",
        "metadata": {"source": "mobile_app"}
    }

    # 5. Execute Request
    transport = ASGITransport(app=app)
    # follow_redirects=True handles the trailing slash (307 redirect) automatically
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as ac:
        response = await ac.post(
            "/v1/payments/bike/",
            json=payload,
            headers={"Authorization": "Bearer fake-token"}
        )

    # 6. Assertions
    # If this fails with 422, check the response body for Pydantic validation errors
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["success"] is True
    # The router wraps the tx_id in "transaction:{tx_id}"
    assert "mock-bike-tx-id" in data["message"]
    assert data["status"] == "PENDING"