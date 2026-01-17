import pytest
from unittest.mock import patch, AsyncMock
from app.gateways.mock_adapter import MockAdapter

# ✅ Use a simple class instead of MagicMock to bypass Pydantic's mock-inspection
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
    # Verify is typically async in these adapters
    assert await adapter.verify(tx_id) is True


@pytest.mark.asyncio
# Patch the AsyncClient.post to return our DummyResponse
@patch("app.gateways.stripe_adapter.httpx.AsyncClient.post", new_callable=AsyncMock)
async def test_stripe_adapter_charge_mock(mock_post):
    from app.gateways.stripe_adapter import StripeAdapter

    # 1. Setup the Fake response object
    # This prevents the "post().model_dump_json().get()" error
    # because this object doesn't have a model_dump_json method for Pydantic to find.
    mock_post.return_value = DummyResponse(
        json_data={"id": "txn_123"},
        status_code=200
    )

    adapter = StripeAdapter(api_key="sk_test_dummy")

    # 2. Execute the charge
    tx_id = await adapter.charge(user_id="user123", amount=100)

    # 3. Final Assertions
    assert tx_id == "txn_123"