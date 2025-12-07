import pytest
from httpx import AsyncClient
from fastapi import status
from main import app  # your FastAPI app

@pytest.mark.asyncio
async def test_remaining_doctor_consults(monkeypatch):
    async def mock_get_remaining_free_count(db, user_id, payment_type):
        return 3

    monkeypatch.setattr(
        "app.routers.doctor_payment.get_remaining_free_count",
        mock_get_remaining_free_count
    )

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get(
            "/v1/payments/doctor-consults/remaining",
            params={"user_id": "user123"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"remaining": 3}

@pytest.mark.asyncio
async def test_pay_doctor_consult_free(monkeypatch):
    async def mock_get_remaining_free_count(db, user_id, payment_type):
        return 1  # user has free quota

    async def mock_record_payment(db, user_id, payment_type, amount):
        return "doctor-user123-123456"

    monkeypatch.setattr(
        "app.routers.doctor_payment.get_remaining_free_count",
        mock_get_remaining_free_count
    )
    monkeypatch.setattr(
        "app.routers.doctor_payment.record_payment",
        mock_record_payment
    )

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/v1/payments/doctor-consults",
            json={"user_id": "user123"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["transaction_id"] == "doctor-user123-123456"
        assert data["success"] is True

