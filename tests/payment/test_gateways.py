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
@patch("app.gateways.stripe_adapter.httpx.AsyncClient.post")
async def test_stripe_adapter_charge_mock(mock_post):
    from app.gateways.stripe_adapter import StripeAdapter

    # 1. Create the mock response object
    mock_response = MagicMock()
    mock_response.status_code = 200

    # 2. Force .json() to return a real dictionary.
    # This prevents Pydantic from trying to "validate" a Mock object.
    mock_response.json.return_value = {"id": "txn_123"}

    # 3. Since httpx.AsyncClient.post is an ASYNC function,
    # the mock must return the response as a result of an awaitable.
    mock_post.return_value = mock_response

    adapter = StripeAdapter(api_key="sk_test_dummy")

    # 4. Execute the charge
    tx_id = await adapter.charge(user_id="user123", amount=100)

    # 5. Assertions
    # If tx_id was coming back as a Mock, this is where it failed before.
    assert tx_id == "txn_123"

    # Check verify (ensure your StripeAdapter.verify is also mocked/handled)
    assert await adapter.verify(tx_id) is True