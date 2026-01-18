import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status
from main import app
from app.api.dependencies import get_current_user
from app.database import get_async_session


# -------------------------
# 1. Setup localized mocks
# -------------------------
class MockUser:
    def __init__(self):
        self.uid = "doctor_test_user_456"


async def override_get_current_user():
    return MockUser()


async def override_get_async_session():
    # Yield a string or mock object since we monkeypatch the service
    yield "mock_db_session"


# Apply overrides to the app
app.dependency_overrides[get_current_user] = override_get_current_user
app.dependency_overrides[get_async_session] = override_get_async_session


@pytest.mark.asyncio
async def test_pay_doctor_consult_success(monkeypatch):
    """
    Test successful doctor consultation payment initiation.
    """

    # 2. Mock the service process_payment call
    # The router expects an object with specific attributes (reference, expires_at, etc.)
    class MockPaymentResult:
        def __init__(self):
            self.reference = "DOC-REF-789"
            self.message = "Payment initiated"
            self.ussd_string = "*123#"
            # datetime is handled by the router's getattr default if not provided

    async def mock_process_payment(*args, **kwargs):
        return MockPaymentResult()

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.process_payment",
        mock_process_payment
    )

    # 3. Valid Payload
    payload = {
        "user_id": "doctor_test_user_456",
        "phone": "670000000",
        "amount": 300.0,
        "currency": "XAF"
    }

    # 4. Execute Request
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/v1/payments/doctor-consults",
            json=payload,
            headers={"X-Idempotency-Key": "doc-idempotency-789"}
        )

    # 5. Assertions
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert data["reference"] == "DOC-REF-789"
    assert data["status"] == "PENDING"


@pytest.mark.asyncio
async def test_get_remaining_doctor_consults(monkeypatch):
    """
    Test the GET endpoint for remaining free doctor consultations.
    """

    # 1. Mock the Service get_remaining_free_uses method
    async def mock_remaining(*args, **kwargs):
        # The router passes category="doctor"
        return 5

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.get_remaining_free_uses",
        mock_remaining
    )

    # 2. Execute Request
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # The router requires user_id as a query param
        response = await ac.get("/v1/payments/doctor-consults/remaining?user_id=doctor_test_user_456")

    # 3. Assertions
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "remaining" in data
    assert data["remaining"] == 5