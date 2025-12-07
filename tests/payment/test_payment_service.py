import pytest
from unittest.mock import AsyncMock

from app.services.payment_service import PaymentService, FREE_LIMITS, BASE_FEE
from app.schemas.payment import PaymentRequest


@pytest.mark.asyncio
async def test_free_quota():
    """User has used 0 of their free quota."""
    mock_db = AsyncMock()
    mock_db.scalar.return_value = 0  # no usage yet

    remaining = await PaymentService.get_remaining_free_uses(
        mock_db,
        user_id="user123",
        category="doctor"
    )

    assert remaining == FREE_LIMITS["doctor"]  # default is 5


@pytest.mark.asyncio
async def test_paid_when_quota_exceeded():
    """User already consumed all free quota."""
    mock_db = AsyncMock()
    mock_db.scalar.return_value = FREE_LIMITS["doctor"]  # all used up

    remaining = await PaymentService.get_remaining_free_uses(
        mock_db,
        user_id="user123",
        category="doctor"
    )

    assert remaining == 0


@pytest.mark.asyncio
async def test_record_payment_returns_tx_id():
    """Ensure a payment is recorded and returns a valid tx_id."""
    mock_db = AsyncMock()

    req = PaymentRequest(
        amount=BASE_FEE["doctor"],
        metadata={"unit_test": True}
    )

    result = await PaymentService.process_payment(
        mock_db,
        user_id="user123",
        category="doctor",
        req=req
    )

    # Validate returned transaction ID
    assert result.transaction_id.startswith("doctor-user123-")

    # Ensure DB was used
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
