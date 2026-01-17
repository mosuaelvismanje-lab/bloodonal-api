import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.gateways.mock_adapter import MockAdapter


@pytest.mark.asyncio
async def test_mock_adapter_charge_success():
    adapter = MockAdapter()
    mock_user_id = "user123"

    tx_id = await adapter.charge(user_id=mock_user_id, amount=100)

    assert tx_id.startswith("mock-user123-")
    # Note: If your MockAdapter verify is async, use await
    assert await adapter.verify(tx_id) is True


@pytest.mark.asyncio
@patch("app.gateways.stripe_adapter.httpx.AsyncClient.post")
async def test_stripe_adapter_charge_mock(mock_post):
    from app.gateways.stripe_adapter import StripeAdapter

    # 1. Create a mock response object
    mock_response = MagicMock()
    mock_response.status_code = 200

    # 2. Ensure .json() returns a REAL dictionary.
    # This stops the chain of Mocks that caused your CI error.
    mock_response.json.return_value = {"id": "txn_123"}

    # 3. FIX: Use AsyncMock for the return value of the post call
    # This allows the 'await client.post' in your code to work correctly.
    mock_post.return_value = mock_response

    adapter = StripeAdapter(api_key="sk_test_dummy")

    # 4. Execute the call
    tx_id = await adapter.charge(user_id="user123", amount=100)

    # 5. Assertions
    assert tx_id == "txn_123"


