from abc import ABC, abstractmethod
from typing import Optional


class IPaymentGateway(ABC):
    """
    Interface for Mobile Money Providers (MTN, Orange, etc.)
    """

    @abstractmethod
    async def charge(
            self,
            phone: str,
            amount: int,
            description: Optional[str] = None
    ) -> str:
        """
        Initiates a mobile money pull (collect) request.

        Args:
            phone: The mobile money number to charge (e.g., "677123456").
            amount: The total amount in XAF.
            description: A short label shown to the user on their USSD/Push prompt.

        Returns:
            str: A unique transaction reference from the provider.

        Raises:
            ValueError: For business logic failures (Insufficient funds, User rejected).
            RuntimeError: For technical failures (Provider API is down, Timeout).
        """
        pass


class ICallGateway(ABC):
    @abstractmethod
    async def create_call_room(self, channel: str, user_id: str, recipient_id: str) -> str:
        """Create a voice or video session and return the room ID."""
        pass


class IChatGateway(ABC):
    @abstractmethod
    async def create_chat_room(self, user_id: str, recipient_id: str) -> str:
        """Create a chat session and return the room ID."""
        pass