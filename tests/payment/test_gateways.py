import pytest
from unittest.mock import AsyncMock, patch
from app.gateways.mock_adapter import MockAdapter

@pytest.mark.asyncio
async def test_mock_adapter_charge_success():
    adapter = MockAdapter()
    mock_user_id = "user123"
    tx_id = await adapter.charge(user_id=mock_user_id, amount=100)
    assert tx_id.startswith("mock-user123-")
    # Optional: verify tx_id using adapter.verify
    assert await adapter.verify(tx_id) is True

@pytest.mark.asyncio
@patch("app.gateways.stripe_adapter.httpx.AsyncClient.post")
async def test_stripe_adapter_charge_mock(mock_post):
    from app.gateways.stripe_adapter import StripeAdapter

    # Mock the async HTTP response
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "txn_123"}

    # Patch the async context manager returned by post()
    mock_post.return_value.__aenter__.return_value = mock_response

    adapter = StripeAdapter(api_key="sk_test_dummy")
    tx_id = await adapter.charge(user_id="user123", amount=100)
    assert tx_id == "txn_123"
    # Optional: verify tx_id using adapter.verify
    assert await adapter.verify(tx_id) is True

