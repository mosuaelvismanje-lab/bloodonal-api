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
    uid = "nurse_test_user_789"


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
async def test_pay_nurse_success(client, monkeypatch):
    """
    Test successful nurse service payment with engine argument verification.
    """
    from app.schemas.payment import PaymentResponseOut, PaymentStatus
    from datetime import datetime, timezone, timedelta

    mock_out = PaymentResponseOut(
        success=True,
        reference="NURSE-REF-123",
        status=PaymentStatus.PENDING,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        message="Nurse service initiated",
        ussd_string="*123#"
    )

    # ✅ FIX: Mock the service and use it for argument validation
    mock_service = AsyncMock(return_value=mock_out)
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.process_payment",
        mock_service
    )

    payload = {"phone": "670000000"}

    response = await client.post(
        "/v1/payments/nurse-services",
        json=payload,
        headers={"X-Idempotency-Key": "nurse-test-key-123"}
    )

    assert response.status_code == status.HTTP_200_OK

    # ✅ Verify the router passed the correct arguments to the PaymentService Engine
    mock_service.assert_called_once()
    _, kwargs = mock_service.call_args
    assert kwargs['user_id'] == "nurse_test_user_789"
    assert kwargs['user_phone'] == "670000000"
    assert kwargs['category'] == "nurse-services"  # Aligned with service replacement logic