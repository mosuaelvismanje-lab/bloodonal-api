
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status
from main import app
from app.api.dependencies import get_current_user, get_db_session
from unittest.mock import AsyncMock

class MockUser:
    uid = "nurse_test_user_789"

@pytest.mark.asyncio
async def test_pay_nurse_success(monkeypatch):
    mock_db = AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: MockUser()
    app.dependency_overrides[get_db_session] = lambda: mock_db

    async def mock_process(*args, **kwargs):
        class Result:
            reference = "NURSE-REF-123"
            message = "Nurse service initiated"
        return Result()

    monkeypatch.setattr("app.services.payment_service.PaymentService.process_payment", mock_process)

    payload = {
        "user_id": "nurse_test_user_789",
        "phone": "670000000"
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/v1/payments/nurse-services", json=payload)

    app.dependency_overrides.clear()
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["reference"] == "NURSE-REF-123"
