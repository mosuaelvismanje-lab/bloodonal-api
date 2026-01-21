import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status
from main import app
from app.api.dependencies import get_current_user, get_db_session
from unittest.mock import AsyncMock

# -------------------------
# 1. Setup localized mocks
# -------------------------
class MockUser:
    def __init__(self):
        self.uid = "doctor_test_user_456"

async def override_get_current_user():
    return MockUser()

async def override_get_db_session():
    # Yield a mock session to satisfy the dependency
    yield AsyncMock()

@pytest.mark.asyncio
async def test_pay_doctor_consult_success(monkeypatch):
    """
    Test successful doctor consultation payment initiation.
    Fixes the 422 error by aligning payload with PaymentRequest schema.
    """
    # Apply overrides specifically for this test
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db_session] = override_get_db_session

    # 2. Mock the PaymentService.process_payment call
    class MockPaymentResult:
        def __init__(self):
            self.reference = "DOC-REF-789"
            self.message = "Payment initiated"
            self.ussd_string = "*123#"
            # status and expires_at are handled by the router/schema defaults

    async def mock_process_payment(*args, **kwargs):
        return MockPaymentResult()

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.process_payment",
        mock_process_payment
    )

    # 3. Valid Payload (STRICT: matches PaymentRequest schema)
    # Removing user_id, amount, and currency from body to avoid 422
    payload = {
        "phone": "670000000"
    }

    # 4. Execute Request
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/v1/payments/doctor-consults",
            json=payload,
            headers={"X-Idempotency-Key": "doc-idempotency-789"}
        )

    # Cleanup overrides
    app.dependency_overrides.clear()

    # 5. Assertions
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert data["reference"] == "DOC-REF-789"
    # Note: status comes from PaymentStatus.PENDING in the router
    assert data["status"] == "PENDING"


@pytest.mark.asyncio
async def test_get_remaining_doctor_consults(monkeypatch):
    """
    Test the GET endpoint for remaining free doctor consultations.
    """
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db_session] = override_get_db_session

    # 1. Mock the Service get_remaining_free_uses method
    async def mock_remaining(*args, **kwargs):
        return 5

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.get_remaining_free_uses",
        mock_remaining
    )

    # 2. Execute Request
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Testing query param logic
        response = await ac.get("/v1/payments/doctor-consults/remaining?user_id=doctor_test_user_456")

    app.dependency_overrides.clear()

    # 3. Assertions
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "remaining" in data
    assert data["remaining"] == 5