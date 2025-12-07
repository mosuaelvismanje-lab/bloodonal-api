import pytest
from unittest.mock import AsyncMock, patch
from app.gateways.mock_adapter import MockAdapter
from httpx import Response

@pytest.mark.asyncio
async def test_mock_adapter_charge_success():
    """Test that MockAdapter returns a mock transaction id."""
    adapter = MockAdapter()
    mock_user_id = "user123"
    tx_id = await adapter.charge(user_id=mock_user_id, amount=100)
    assert tx_id.startswith(f"mock-{mock_user_id}-")

@pytest.mark.asyncio
@patch("app.gateways.stripe_adapter.httpx.AsyncClient.post")
async def test_stripe_adapter_charge_mock(mock_post):
    """Test StripeAdapter using a mocked HTTP response."""
    from app.gateways.stripe_adapter import StripeAdapter
    from types import SimpleNamespace

    # Mock the async context manager
    mock_response = AsyncMock()
    # Simulate httpx.Response attributes
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "txn_123"}

    # Patch the post() call to return an async context manager
    mock_post.return_value.__aenter__.return_value = mock_response

    adapter = StripeAdapter(api_key="sk_test_dummy")
    tx_id = await adapter.charge(user_id="user123", amount=100)

    assert tx_id == "txn_123"

