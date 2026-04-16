#app/domain/interfaces
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from dataclasses import dataclass

# ================================================================
# PAYMENT MODELS & GATEWAY INTERFACE
# ================================================================

@dataclass
class GatewayResponse:
    """Standardized response from any payment provider (MTN, Orange, etc.)"""
    provider_tx_id: str
    status: str  # e.g., "PENDING", "SUCCESS", "FAILED"
    ussd_string: Optional[str] = None  # Crucial for Android dialer integration
    raw_response: Optional[Dict[str, Any]] = None

class IPaymentGateway(ABC):
    """
    Abstraction for mobile money (MTN, Orange) or cards.
    Standardized for manual and automated adapters.
    """

    @abstractmethod
    async def charge(
        self,
        phone: str,
        amount: int,
        description: Optional[str] = None,
        merchant_number: Optional[str] = None # ✅ Added: Allows routing to specific .env admin numbers
    ) -> GatewayResponse:
        """
        Initiates a payment request. Returns a GatewayResponse object.
        Merchant number can be passed from settings for USSD construction.
        """
        raise NotImplementedError

    @abstractmethod
    async def verify(self, provider_tx_id: str) -> bool:
        """
        Returns True if transaction is valid/confirmed, False otherwise.
        """
        raise NotImplementedError


# ================================================================
# CALL / CHAT GATEWAY INTERFACES
# ================================================================

class ICallGateway(ABC):
    @abstractmethod
    async def create_call_room(self, channel: str, user_id: str, recipient_id: str) -> str:
        """Creates a VOIP/Video room and returns the room_id."""
        raise NotImplementedError

    @abstractmethod
    async def send_call(self, phone_number: str, message: str) -> bool:
        """Sends an automated voice notification/call."""
        raise NotImplementedError

class IChatGateway(ABC):
    @abstractmethod
    async def create_chat_room(self, user_id: str, recipient_id: str) -> str:
        """Returns a unique chat_room_id."""
        raise NotImplementedError


# ================================================================
# USAGE / QUOTA REPOSITORY (Atomic & Idempotent)
# ================================================================

class IUsageRepository(ABC):
    """
    Tracks free limits and records usage with idempotency protection.
    Synced with SQLAlchemyUsageRepository and UsageCounter model.
    """

    @abstractmethod
    async def count_uses(self, user_id: str, service: str) -> int:
        """Count how many times a user has used a specific service (e.g., 'blood-request')."""
        raise NotImplementedError

    @abstractmethod
    async def record_usage(
        self,
        user_id: str,
        service: str,
        paid: bool,
        amount: float,
        transaction_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> None:
        """Records a successful usage event in the database."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_idempotency_key(self, key: str) -> Optional[Dict[str, Any]]:
        """Checks if a request with this key was already processed to prevent double-charging."""
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
        phone: Optional[str] = None, # ✅ Added phone for record keeping
        idempotency_key: Optional[str] = None,
        provider_tx_id: Optional[str] = None,
    ) -> Any:
        """Creates an initial pending transaction in the ledger."""
        raise NotImplementedError

    @abstractmethod
    async def update_status(self, internal_tx_id: str, status: str) -> None:
        """Updates the status of a payment after provider verification."""
        raise NotImplementedError