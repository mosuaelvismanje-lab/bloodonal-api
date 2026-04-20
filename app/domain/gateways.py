from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class GatewayPaymentResponse:
    """Standardized response from any mobile money provider implementation."""
    reference: str
    status: str  # e.g., "PENDING", "SUCCESS", "FAILED"
    ussd_string: Optional[str] = None
    provider_raw_response: Optional[Dict[str, Any]] = None

class IPaymentGateway(ABC):
    """Interface for Mobile Money Providers."""

    @abstractmethod
    async def charge(
            self,
            phone: str,
            amount: int,
            description: Optional[str] = None,
            merchant_number: Optional[str] = None
    ) -> GatewayPaymentResponse:
        """Initiates a collection request. No user_id here; that's service-level logic."""
        pass

    @abstractmethod
    async def verify_transaction(self, reference: str) -> str:
        """Returns: 'SUCCESS', 'FAILED', or 'PENDING'"""
        pass