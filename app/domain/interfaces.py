from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List

# ================================================================
# PAYMENT GATEWAY INTERFACE
# ================================================================

class IPaymentGateway(ABC):
    """
    Abstraction for mobile money (MTN, Orange) or cards.
    """

    @abstractmethod
    async def charge(
        self,
        phone: str,          # Support for flexible billing (charge any phone)
        amount: float,
        description: str,    # Label for the USSD/Push prompt
    ) -> str:
        """
        Initiates a payment request. Returns provider_transaction_id.
        Raises ValueError (Low balance) or ConnectionError.
        """
        raise NotImplementedError

    @abstractmethod
    async def verify(self, provider_tx_id: str) -> str:
        """Return status: 'success', 'failed', or 'pending'."""
        raise NotImplementedError


# ================================================================
# CALL / VOICE GATEWAY INTERFACE
# ================================================================

class ICallGateway(ABC):
    @abstractmethod
    async def create_call_room(
        self,
        channel: str,
        user_id: str,
        recipient_id: str
    ) -> str:
        """Creates a VOIP/Video room and returns the room_id."""
        raise NotImplementedError

    @abstractmethod
    async def send_call(self, phone_number: str, message: str) -> bool:
        raise NotImplementedError


# ================================================================
# CHAT GATEWAY INTERFACE
# ================================================================

class IChatGateway(ABC):
    @abstractmethod
    async def create_chat_room(self, user_id: str, recipient_id: str) -> str:
        """Should return a unique chat_room_id."""
        raise NotImplementedError


# ================================================================
# USAGE / QUOTA REPOSITORY (Critical for Idempotency)
# ================================================================

class IUsageRepository(ABC):
    """
    Tracks free limits and record usage with idempotency protection.
    """

    @abstractmethod
    async def count_uses(self, user_id: str, service: str) -> int:
        """Count how many times a user has used a specific service."""
        raise NotImplementedError

    @abstractmethod
    async def record_usage(
        self,
        user_id: str,
        service: str,
        paid: bool,
        amount: float,
        transaction_id: Optional[str] = None,
        idempotency_key: Optional[str] = None, # Key to block duplicates
        request_id: Optional[str] = None       # Stores the room_id generated
    ) -> None:
        """Records a successful usage event."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_idempotency_key(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Checks if a request with this key was already processed.
        Returns the record if found, allowing the system to return existing Room IDs.
        """
        raise NotImplementedError


# ================================================================
# PAYMENT LEDGER / TRANSACTION REPOSITORY
# ================================================================

class IPaymentLedgerRepository(ABC):
    @abstractmethod
    async def create_payment(
        self,
        user_id: str,
        category: str,
        amount: float,
        status: str,
        idempotency_key: Optional[str] = None,
        provider_tx_id: Optional[str] = None,
    ) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def update_status(self, internal_tx_id: str, status: str) -> None:
        raise NotImplementedError