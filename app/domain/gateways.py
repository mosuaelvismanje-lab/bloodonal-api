#app/domain/gateways
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
    """
    Interface for Mobile Money Providers (MTN, Orange, etc.)
    Ensures the application logic remains decoupled from specific provider APIs.
    """

    @abstractmethod
    async def charge(
            self,
            phone: str,
            amount: int,
            description: Optional[str] = None,
            merchant_number: Optional[str] = None  # ✅ Added: Supports routing to .env admin wallets
    ) -> GatewayPaymentResponse:
        """
        Initiates a mobile money collection (pull) request.

        Args:
            phone: The mobile money number to charge (e.g., "677123456").
            amount: The total amount in XAF.
            description: Short label for the USSD/Push prompt.
            merchant_number: Optional destination wallet for manual USSD generation.

        Returns:
            GatewayPaymentResponse: Standardized object containing reference and optional USSD.

        Raises:
            ValueError: Business failures (Insufficient funds, Invalid number format).
            RuntimeError: Technical failures (Network timeout, Provider API down).
        """
        pass

    @abstractmethod
    async def verify_transaction(self, reference: str) -> str:
        """
        Checks the current status of a transaction with the provider.
        Necessary for polling the final result of 'PENDING' transactions.
        """
        pass


class ICallGateway(ABC):
    """Interface for voice/video providers (e.g., Agora, Twilio)."""
    @abstractmethod
    async def create_call_room(self, channel: str, user_id: str, recipient_id: str) -> str:
        """Create a voice or video session and return the room ID."""
        pass


class IChatGateway(ABC):
    """Interface for real-time messaging providers."""
    @abstractmethod
    async def create_chat_room(self, user_id: str, recipient_id: str) -> str:
        """Create a chat session and return the room ID."""
        pass