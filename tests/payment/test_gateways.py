import pytest
from unittest.mock import patch, AsyncMock
from app.gateways.mock_adapter import MockAdapter
from app.gateways.stripe_adapter import StripeAdapter


# Standardized DummyResponse
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

    # Ensuring the adapter respects the service's fee/phone interface
    amount = 500
    phone = "677123456"

    response = await adapter.charge(phone=phone, amount=amount)

    assert response.reference.startswith("TX-")  # Aligned with generate_reference()
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
    mock_post.return_value = DummyResponse(
        json_data={"id": "TX-STRIPE-123", "status": "succeeded"},
        status_code=200
    )

    adapter = StripeAdapter(api_key="sk_test_dummy")

    response = await adapter.charge(phone="677123456", amount=500)

    # Assertions align with PaymentResponseOut structure used in PaymentService
    assert response.reference == "TX-STRIPE-123"
    assert response.status == "SUCCESS"
    assert await adapter.verify_transaction(response.reference) == "SUCCESS"

    mock_post.assert_called_once()