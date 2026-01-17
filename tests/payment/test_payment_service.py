import pytest
from unittest.mock import patch, AsyncMock
from app.gateways.mock_adapter import MockAdapter

# ✅ A simple "Fake" class to prevent Pydantic V2 from inspecting a MagicMock
class DummyResponse:
    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data

@pytest.mark.asyncio
async def test_mock_adapter_charge_success():
    adapter = MockAdapter()
    mock_user_id = "user123"

    tx_id = await adapter.charge(user_id=mock_user_id, amount=100)

    assert tx_id.startswith("mock-user123-")
    assert await adapter.verify(tx_id) is True

@pytest.mark.asyncio
# ✅ We use AsyncMock for the network call itself
@patch("app.gateways.stripe_adapter.httpx.AsyncClient.post", new_callable=AsyncMock)
async def test_stripe_adapter_charge_mock(mock_post):
    from app.gateways.stripe_adapter import StripeAdapter

    # 1. Provide a REAL object as the return value.
    # This prevents the 'post().model_dump_json().get()' error
    # because Pydantic won't find 'magic' methods on this simple class.
    mock_post.return_value = DummyResponse(
        json_data={"id": "txn_123"},
        status_code=200
    )

    adapter = StripeAdapter(api_key="sk_test_dummy")

    # 2. Execute the call (this will now properly resolve the 'await')
    tx_id = await adapter.charge(user_id="user123", amount=100)

    # 3. Final Assertion
    assert tx_id == "txn_123"

