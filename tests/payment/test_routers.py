import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status
from main import app

# 1. Correct paths for Dependency Overrides
from app.api.dependencies import get_current_user, get_db_session

# -------------------------------------------------------------------
# Shared helpers & Mocks
# -------------------------------------------------------------------

class MockUser:
    """Mock object to simulate a logged-in user with required attributes."""
    def __init__(self):
        self.uid = "user123"
        self.id = "user123"
        self.email = "test@example.com"

class MockPaymentResult:
    """Matches the expected structure for payment service returns."""
    def __init__(self, transaction_id: str, amount: int):
        self.transaction_id = transaction_id
        self.amount = amount
        self.success = True

# 2. Dependency Override Functions
async def override_get_current_user():
    return MockUser()

async def override_get_db():
    yield "mock_db_session"

# Apply overrides globally to the app instance for testing
app.dependency_overrides[get_current_user] = override_get_current_user
app.dependency_overrides[get_db_session] = override_get_db

def get_transport() -> ASGITransport:
    return ASGITransport(app=app)

# Standard Authorization header to bypass initial security checks
auth_headers = {"Authorization": "Bearer dummy-token"}

# -------------------------------------------------------------------
# TEST CASES
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pay_doctor(monkeypatch):
    async def mock_handle(uid, service, phone):
        return "doctor-user123-123456"

    # Patching the UseCase handle method which is called by the router
    monkeypatch.setattr("app.api.routers.payments.ConsultationUseCase.handle", mock_handle)

    # Clean JSON payload: phone is now part of the body per your new schema
    payload = {"phone": "677000001"}

    async with AsyncClient(transport=get_transport(), base_url="http://test") as ac:
        # Route: /v1/payments/doctor-consults
        response = await ac.post("/v1/payments/doctor-consults", json=payload, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json().get("transaction_id") == "doctor-user123-123456"

@pytest.mark.asyncio
async def test_pay_nurse(monkeypatch):
    async def mock_handle(uid, service, phone):
        return "nurse-user123-789000"

    monkeypatch.setattr("app.api.routers.payments.ConsultationUseCase.handle", mock_handle)

    payload = {"phone": "677000002"}

    async with AsyncClient(transport=get_transport(), base_url="http://test") as ac:
        response = await ac.post("/v1/payments/nurse", json=payload, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json().get("service") == "nurse"

@pytest.mark.asyncio
async def test_pay_bike(monkeypatch):
    async def mock_handle(uid, service, phone):
        return "bike-user123-456789"

    monkeypatch.setattr("app.api.routers.payments.ConsultationUseCase.handle", mock_handle)

    payload = {"phone": "677000003"}

    async with AsyncClient(transport=get_transport(), base_url="http://test") as ac:
        response = await ac.post("/v1/payments/bike", json=payload, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK

@pytest.mark.asyncio
async def test_pay_taxi(monkeypatch):
    async def mock_handle(uid, service, phone):
        return "taxi-user123-999999"

    monkeypatch.setattr("app.api.routers.payments.ConsultationUseCase.handle", mock_handle)

    payload = {"phone": "677000004"}

    async with AsyncClient(transport=get_transport(), base_url="http://test") as ac:
        response = await ac.post("/v1/payments/taxi", json=payload, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK

@pytest.mark.asyncio
async def test_pay_blood_request(monkeypatch):
    async def mock_handle(uid, service, phone):
        return "blood-user123-111222"

    monkeypatch.setattr("app.api.routers.payments.ConsultationUseCase.handle", mock_handle)

    # Sending the phone in the body as required by PaymentRequest schema
    payload = {"phone": "677000005"}

    async with AsyncClient(transport=get_transport(), base_url="http://test") as ac:
        response = await ac.post(
            "/v1/payments/blood-request",
            json=payload,
            headers=auth_headers
        )

    data = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert data.get("transaction_id") == "blood-user123-111222"