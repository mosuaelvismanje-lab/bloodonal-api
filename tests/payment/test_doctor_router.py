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
    uid = "doctor_test_user_456"


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
async def test_pay_doctor_consult_success(client, monkeypatch):
    """
    Test successful doctor consultation payment initiation with argument verification.
    """
    from app.schemas.payment import PaymentResponseOut, PaymentStatus
    from datetime import datetime, timezone, timedelta

    mock_out = PaymentResponseOut(
        success=True,
        reference="DOC-REF-789",
        status=PaymentStatus.PENDING,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        message="Payment initiated",
        ussd_string="*123#"
    )

    # ✅ FIX: Mock the Service and capture the call arguments
    mock_service = AsyncMock(return_value=mock_out)
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.process_payment",
        mock_service
    )

    payload = {"phone": "670000000"}

    response = await client.post(
        "/v1/payments/doctor-consults",
        json=payload,
        headers={"X-Idempotency-Key": "doc-idempotency-789"}
    )

    assert response.status_code == status.HTTP_200_OK

    # ✅ Verify the router passes the correct mapped data to the engine
    mock_service.assert_called_once()
    _, kwargs = mock_service.call_args
    assert kwargs['user_id'] == "doctor_test_user_456"
    assert kwargs['user_phone'] == "670000000"
    assert kwargs['category'] == "doctor-consult"  # Matches service logic


@pytest.mark.asyncio
async def test_get_remaining_doctor_consults(client, monkeypatch):
    """
    Test the GET endpoint using the Service layer to ensure consistency.
    """
    # Patch the service method rather than the repo
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.get_remaining_free_uses",
        AsyncMock(return_value=5)
    )

    response = await client.get("/v1/payments/doctor-consults/remaining")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["remaining"] == 5