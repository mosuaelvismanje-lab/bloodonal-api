import pytest
from fastapi import status
from unittest.mock import AsyncMock
from app.schemas.payment import PaymentResponseOut, PaymentStatus
from datetime import datetime, timezone, timedelta


def create_mock_payment_response(success: bool = True, ref: str = "TAXI-REF-999"):
    return PaymentResponseOut(
        success=success,
        reference=ref,
        status=PaymentStatus.PENDING,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        message="Taxi ride payment initiated",
        ussd_string="*123#"
    )


# =========================================================
# TEST 1: SUCCESS CASE (FREE RIDE CONSUMED)
# =========================================================
@pytest.mark.asyncio
async def test_pay_taxi_success(client, monkeypatch):

    mock_repo = AsyncMock()
    mock_repo.try_consume_free_usage = AsyncMock(return_value=True)

    monkeypatch.setattr(
        "app.routers.taxi_payment.SQLAlchemyUsageRepository",
        lambda db: mock_repo
    )

    response = await client.post(
        "/v1/payments/taxi",
        json={"phone": "670000000", "taxi_driver_id": "DRV-123", "ride_distance_km": 5.0}
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "SUCCESS"
    assert "reference" in response.json()

    mock_repo.try_consume_free_usage.assert_called_once()


# =========================================================
# TEST 2: GET REMAINING RIDES
# =========================================================
@pytest.mark.asyncio
async def test_get_remaining_taxi_rides(client, monkeypatch):

    mock_repo = AsyncMock()
    mock_repo.count_uses = AsyncMock(return_value=2)

    monkeypatch.setattr(
        "app.routers.taxi_payment.SQLAlchemyUsageRepository",
        lambda db: mock_repo
    )

    response = await client.get("/v1/payments/taxi/remaining")

    assert response.status_code == status.HTTP_200_OK
    assert "remaining" in response.json()


# =========================================================
# TEST 3: NO FREE RIDES (FALLBACK TO PAYMENT)
# =========================================================
@pytest.mark.asyncio
async def test_pay_taxi_exceeds_limit(client, monkeypatch):

    mock_repo = AsyncMock()
    mock_repo.try_consume_free_usage = AsyncMock(return_value=False)

    monkeypatch.setattr(
        "app.routers.taxi_payment.SQLAlchemyUsageRepository",
        lambda db: mock_repo
    )

    response = await client.post(
        "/v1/payments/taxi",
        json={"phone": "670000000"}
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "PENDING"
    assert "ussd_string" in response.json()

    mock_repo.try_consume_free_usage.assert_called_once()