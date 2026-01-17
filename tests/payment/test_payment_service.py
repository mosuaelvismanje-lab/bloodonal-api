import pytest
from unittest.mock import patch, AsyncMock
from app.gateways.mock_adapter import MockAdapter

# ✅ Improved "Fake" class to satisfy the httpx.Response interface
class DummyResponse:
    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code
        # Added .text attribute so the adapter's error handling doesn't crash
        self.text = str(json_data)

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
# ✅ Using AsyncMock handles 'await client.post' correctly
@patch("app.gateways.stripe_adapter.httpx.AsyncClient.post", new_callable=AsyncMock)
async def test_stripe_adapter_charge_mock(mock_post):
    from app.gateways.stripe_adapter import StripeAdapter

    # 1. Provide the DummyResponse object.
    # Since this is a standard class (not a MagicMock), Pydantic V2
    # will not try to "inspect" it or call model_dump_json() on it.
    mock_post.return_value = DummyResponse(
        json_data={"id": "txn_123"},
        status_code=200
    )

    adapter = StripeAdapter(api_key="sk_test_dummy")

    # 2. Execute the call
    # This now works because adapter calls resp.json() which DummyResponse provides.
    tx_id = await adapter.charge(user_id="user123", amount=100)

    # 3. Final Assertions
    assert tx_id == "txn_123"
    assert await adapter.verify(tx_id) is True

