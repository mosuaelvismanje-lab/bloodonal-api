import pytest
import asyncio
from unittest.mock import AsyncMock
from app.services.payment_service import get_remaining_free_count, record_payment, FEE_AMOUNT

@pytest.mark.asyncio
async def test_free_quota():
    # Mock DB session
    mock_db = AsyncMock()
    # Simulate 0 used out of 5 free quotas
    mock_db.scalar.return_value = 0
    remaining = await get_remaining_free_count(mock_db, user_id="user123", payment_type="doctor")
    assert remaining == 5

@pytest.mark.asyncio
async def test_paid_when_quota_exceeded():
    mock_db = AsyncMock()
    # Simulate all free quotas used
    mock_db.scalar.return_value = 5
    remaining = await get_remaining_free_count(mock_db, user_id="user123", payment_type="doctor")
    assert remaining == 0

@pytest.mark.asyncio
async def test_record_payment_returns_tx_id():
    mock_db = AsyncMock()
    tx_id = await record_payment(mock_db, user_id="user123", payment_type="doctor", amount=FEE_AMOUNT)
    assert tx_id.startswith("doctor-user123-")
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()
