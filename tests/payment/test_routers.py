#tests/payment/test_router
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status
from main import app

from app.api.dependencies import get_current_user, get_db_session

# -------------------------------------------------------------------
# Shared helpers & Mocks
# -------------------------------------------------------------------

class MockUser:
    def __init__(self):
        self.uid = "user123"
        self.id = "user123"
        self.email = "test@example.com"

async def override_get_current_user():
    return MockUser()

async def override_get_db():
    yield "mock_db_session"

app.dependency_overrides[get_current_user] = override_get_current_user
app.dependency_overrides[get_db_session] = override_get_db

def get_transport() -> ASGITransport:
    return ASGITransport(app=app)

auth_headers = {"Authorization": "Bearer dummy-token"}

# -------------------------------------------------------------------
# TESTS
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pay_doctor(monkeypatch):
    async def mock_handle(*args, **kwargs):
        return "doctor-user123-123456"

    monkeypatch.setattr(
        "app.domain.usecases.ConsultationUseCase.handle",
        mock_handle
    )

    payload = {"phone": "677000001"}

    async with AsyncClient(transport=get_transport(), base_url="http://test") as ac:
        response = await ac.post(
            "/v1/payments/doctor-consults",
            json=payload,
            headers=auth_headers
        )

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_pay_nurse(monkeypatch):
    async def mock_handle(*args, **kwargs):
        return "nurse-user123-789000"

    monkeypatch.setattr(
        "app.domain.usecases.ConsultationUseCase.handle",
        mock_handle
    )

    payload = {"phone": "677000002"}

    async with AsyncClient(transport=get_transport(), base_url="http://test") as ac:
        response = await ac.post(
            "/v1/payments/nurse",
            json=payload,
            headers=auth_headers
        )

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_pay_bike(monkeypatch):
    async def mock_handle(*args, **kwargs):
        return "bike-user123-456789"

    monkeypatch.setattr(
        "app.domain.usecases.ConsultationUseCase.handle",
        mock_handle
    )

    payload = {"phone": "677000003"}

    async with AsyncClient(transport=get_transport(), base_url="http://test") as ac:
        response = await ac.post(
            "/v1/payments/bike",
            json=payload,
            headers=auth_headers
        )

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_pay_taxi(monkeypatch):
    async def mock_handle(*args, **kwargs):
        return "taxi-user123-999999"

    monkeypatch.setattr(
        "app.domain.usecases.ConsultationUseCase.handle",
        mock_handle
    )

    payload = {"phone": "677000004"}

    async with AsyncClient(transport=get_transport(), base_url="http://test") as ac:
        response = await ac.post(
            "/v1/payments/taxi",
            json=payload,
            headers=auth_headers
        )

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_pay_blood_request(monkeypatch):
    async def mock_handle(*args, **kwargs):
        return "blood-user123-111222"

    monkeypatch.setattr(
        "app.domain.usecases.ConsultationUseCase.handle",
        mock_handle
    )

    payload = {"phone": "677000005"}

    async with AsyncClient(transport=get_transport(), base_url="http://test") as ac:
        response = await ac.post(
            "/v1/payments/blood-request",
            json=payload,
            headers=auth_headers
        )

    assert response.status_code == status.HTTP_200_OK
