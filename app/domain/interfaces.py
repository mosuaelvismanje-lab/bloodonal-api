from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession


# ================================================================
# PAYMENT GATEWAY INTERFACE
# ================================================================

class IPaymentGateway(ABC):
    """
    Abstraction for any external payment provider (MTN, OM, Stripe, PayPal, etc).
    """

    @abstractmethod
    async def charge(
        self,
        user_id: str,
        amount: float,
        currency: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Charge user and return provider_transaction_id.
        Should raise errors on failures.
        """
        raise NotImplementedError

    @abstractmethod
    async def verify(
        self,
        provider_tx_id: str
    ) -> str:
        """
        Return status: 'success', 'failed', or 'pending'.
        """
        raise NotImplementedError


# ================================================================
# CALL / VOICE GATEWAY INTERFACE
# ================================================================

class ICallGateway(ABC):
    """
    Interface for voice/call alerts (nurse, consultation call, emergency dispatch, etc).
    """

    @abstractmethod
    async def send_call(
        self,
        phone_number: str,
        message: str
    ) -> bool:
        """
        Returns True if call sent successfully.
        """
        raise NotImplementedError


# ================================================================
# CHAT GATEWAY INTERFACE
# ================================================================

class IChatGateway(ABC):
    """
    Interface for creating and managing chat rooms (doctor-patient, support, etc).
    """

    @abstractmethod
    async def create_chat_room(
        self,
        user_id: str,
        recipient_id: str
    ) -> str:
        """
        Should return a unique chat_room_id.
        """
        raise NotImplementedError

    @abstractmethod
    async def send_message(
        self,
        room_id: str,
        sender_id: str,
        content: str
    ) -> bool:
        """
        Returns True if message was delivered.
        """
        raise NotImplementedError


# ================================================================
# SMS / NOTIFICATION GATEWAY
# ================================================================

class ISmsGateway(ABC):
    """
    Abstraction for SMS and notification services.
    """

    @abstractmethod
    async def send_sms(
        self,
        phone_number: str,
        message: str
    ) -> bool:
        raise NotImplementedError


# ================================================================
# USAGE / QUOTA REPOSITORY
# ================================================================

class IUsageRepository(ABC):
    """
    Manages user usage/quota for categories (consultation, chat, call, AI analysis, etc).
    """

    @abstractmethod
    async def get_usage(
        self,
        db: AsyncSession,
        user_id: str,
        category: str
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    async def increment_usage(
        self,
        db: AsyncSession,
        user_id: str,
        category: str
    ) -> None:
        raise NotImplementedError


# ================================================================
# PAYMENT LEDGER / TRANSACTION REPOSITORY
# ================================================================

class IPaymentLedgerRepository(ABC):
    """
    Interface for storing and updating payment transactions internally.
    """

    @abstractmethod
    async def create_payment(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        category: str,
        amount: float,
        status: str,
        internal_tx_id: str,
        provider_tx_id: Optional[str],
        metadata: Dict[str, Any],
    ) -> Any:
        """
        Must return DB record or primary key of created payment.
        """
        raise NotImplementedError

    @abstractmethod
    async def update_status(
        self,
        db: AsyncSession,
        internal_tx_id: str,
        status: str
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_pending_transactions(
        self,
        db: AsyncSession
    ) -> List[Any]:
        """
        Get all pending payments for reconciliation.
        """
        raise NotImplementedError


# ================================================================
# TOP-LEVEL SERVICE ORCHESTRATION
# ================================================================

class IPaymentProcessor(ABC):
    """
    High-level interface for orchestrating complete payment flows.
    """

    @abstractmethod
    async def process(
        self,
        db: AsyncSession,
        user_id: str,
        category: str,
        amount: Optional[float],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        raise NotImplementedError
