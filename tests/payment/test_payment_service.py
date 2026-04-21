import pytest
from unittest.mock import patch, AsyncMock
from app.gateways.mock_adapter import MockAdapter
from app.gateways.stripe_adapter import StripeAdapter
from app.services.payment_service import generate_reference


# ✅ Standardized DummyResponse
class DummyResponse:
    def __init__(self, json_data: dict, status_code: int = 200):
        self._json_data = json_data
        self.status_code = status_code
        self.text = str(json_data)

    def json(self) -> dict:
        return self._json_data


# -------------------------
# 1. Mock Gateway Tests
# -------------------------
@pytest.mark.asyncio
async def test_mock_adapter_charge_success():
    """Verify MockAdapter produces references compatible with service logic."""
    adapter = MockAdapter()

    # Generate a standard reference matching service expectations
    expected_ref = generate_reference()

    # Override the default reference generation in the mock for strict testing
    with patch("uuid.uuid4") as mock_uuid:
        mock_uuid.return_value.hex = expected_ref.replace("TX-", "")

        phone = "677123456"
        amount = 500
        response = await adapter.charge(phone=phone, amount=amount)

    # ✅ ALIGNMENT: Verify reference starts with TX-
    assert response.reference.startswith("TX-")

    # Set status manually in the internal store to verify the transition
    adapter._tx_store[response.reference] = "SUCCESS"
    assert await adapter.verify_transaction(response.reference) == "SUCCESS"


# -------------------------
# 2. Stripe Gateway Tests
# -------------------------
@pytest.mark.asyncio
@patch("app.gateways.stripe_adapter.httpx.AsyncClient.post", new_callable=AsyncMock)
async def test_stripe_adapter_charge_mock(mock_post):
    """
    Test StripeAdapter integration.
    Matches the PaymentService expected status and reference format.
    """
    ref = generate_reference()

    mock_post.return_value = DummyResponse(
        json_data={"id": ref, "status": "succeeded"},
        status_code=200
    )

    adapter = StripeAdapter(api_key="sk_test_dummy")
    response = await adapter.charge(phone="677123456", amount=500)

    # ✅ ALIGNMENT: Assert against service-compatible attributes
    assert response.reference == ref
    assert response.status == "SUCCESS"

    # Test verification mapping
    with patch("app.gateways.stripe_adapter.httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = DummyResponse(json_data={"status": "succeeded"})
        assert await adapter.verify_transaction(response.reference) == "SUCCESS"

    mock_post.assert_called_once()