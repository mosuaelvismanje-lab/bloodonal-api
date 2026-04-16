import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status
from main import app
from app.api.dependencies import get_current_user, get_db
from app.models.payment import PaymentStatus
from unittest.mock import AsyncMock
from datetime import datetime, timezone


# -------------------------
# 1. Clean Mocking Pattern
# -------------------------
class MockUser:
    id = "blood_test_user_123"
    uid = "blood_test_user_123"


async def override_get_current_user():
    return MockUser()


async def override_get_db():
    mock_session = AsyncMock()
    # Ensure the mock session behaves like an AsyncSession in 2026
    yield mock_session


# Apply overrides globally
app.dependency_overrides[get_current_user] = override_get_current_user
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def client():
    """
    Standardized 2026 AsyncClient fixture using ASGITransport.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# -------------------------
# 2. Optimized Test Cases
# -------------------------

@pytest.mark.asyncio
async def test_pay_blood_request_success(client, monkeypatch):
    """
    Test FREE PATH using localized monkeypatch.
    """
    from app.schemas.payment import PaymentResponseOut

    mock_out = PaymentResponseOut(
        success=True,
        status=PaymentStatus.SUCCESS,
        message="Free usage applied successfully",
        reference="FREE-TEST-REF",
        ussd_string=None,
        expires_at=datetime.now(timezone.utc)
    )

    # Simplified mock using return_value for non-complex logic
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.process_payment",
        AsyncMock(return_value=mock_out)
    )

    response = await client.post(
        "/v1/blood-request-payments/",
        json={"phone": "670556321"},
        headers={"X-Idempotency-Key": "blood-key-123"}
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "SUCCESS"


@pytest.mark.asyncio
async def test_pay_blood_request_paid_path(client, monkeypatch):
    """
    Test PAID flow (MTN Cameroon *126*2*).
    """
    from app.schemas.payment import PaymentResponseOut

    mock_out = PaymentResponseOut(
        success=True,
        status=PaymentStatus.PENDING,
        message="Please dial USSD.",
        reference="PAID-TEST-REF",
        ussd_string="*126*2*676657577*500#"
    )

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.process_payment",
        AsyncMock(return_value=mock_out)
    )

    response = await client.post("/v1/blood-request-payments/", json={"phone": "677000000"})

    data = response.json()
    assert data["status"] == "PENDING"
    assert data["ussd_string"].startswith("*126*2*")


@pytest.mark.asyncio
async def test_get_remaining_blood_requests(client, monkeypatch):
    """
    Test quota checking.
    """
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.get_remaining_free_uses",
        AsyncMock(return_value=3)
    )

    response = await client.get("/v1/blood-request-payments/remaining", params={"category": "blood-request"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["remaining"] == 3


@pytest.fixture(scope="module", autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.clear()