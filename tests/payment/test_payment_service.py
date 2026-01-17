import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.gateways.mock_adapter import MockAdapter

@pytest.mark.asyncio
async def test_mock_adapter_charge_success():
    adapter = MockAdapter()
    mock_user_id = "user123"

    tx_id = await adapter.charge(user_id=mock_user_id, amount=100)

    assert tx_id.startswith("mock-user123-")
    # Verify is likely async
    assert await adapter.verify(tx_id) is True


@pytest.mark.asyncio
# ✅ FIX 1: Explicitly use new_callable=AsyncMock for the async post call
@patch("app.gateways.stripe_adapter.httpx.AsyncClient.post", new_callable=AsyncMock)
async def test_stripe_adapter_charge_mock(mock_post):
    from app.gateways.stripe_adapter import StripeAdapter

    # 1. Create a mock response object
    mock_response = MagicMock()
    mock_response.status_code = 200

    # ✅ FIX 2: Explicitly define the json() return as a DICTIONARY
    # This prevents the "Mock Chain" error in Pydantic models
    mock_response.json.return_value = {"id": "txn_123"}

    # 2. Set the return value for the awaited call
    mock_post.return_value = mock_response

    adapter = StripeAdapter(api_key="sk_test_dummy")

    # 3. Execute the call
    tx_id = await adapter.charge(user_id="user123", amount=100)

    # 4. Final Assertion
    # Because of FIX 1 and 2, tx_id will now be the string "txn_123"
    assert tx_id == "txn_123"


