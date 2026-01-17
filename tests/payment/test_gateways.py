import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.gateways.mock_adapter import MockAdapter

@pytest.mark.asyncio
async def test_mock_adapter_charge_success():
    adapter = MockAdapter()
    mock_user_id = "user123"

    tx_id = await adapter.charge(user_id=mock_user_id, amount=100)

    assert tx_id.startswith("mock-user123-")
    assert await adapter.verify(tx_id) is True


@pytest.mark.asyncio
# 1. Use new_callable=AsyncMock to ensure the patched method is awaitable
@patch("app.gateways.stripe_adapter.httpx.AsyncClient.post", new_callable=AsyncMock)
async def test_stripe_adapter_charge_mock(mock_post):
    from app.gateways.stripe_adapter import StripeAdapter

    # 2. Create the mock response object
    mock_response = MagicMock()
    mock_response.status_code = 200

    # 3. Force .json() to return a real dictionary.
    # This stops the 'Mock chain' (post().model_dump_json().get())
    mock_response.json.return_value = {"id": "txn_123"}

    # 4. Set the return value for the awaited call
    mock_post.return_value = mock_response

    adapter = StripeAdapter(api_key="sk_test_dummy")

    # 5. Execute the charge
    tx_id = await adapter.charge(user_id="user123", amount=100)

    # 6. Final Assertions
    assert tx_id == "txn_123"