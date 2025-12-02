# app/domain/interfaces.py

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession


# ================================================================
# PAYMENT GATEWAY INTERFACE
# ================================================================

class IPaymentGateway(ABC):
    """
    Contract for any external payment provider.
    Your app does NOT depend on MTN, OM, Stripe, PayPal, etc.
    Only this interface.
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
        Returns provider transaction ID.
        Must raise errors for invalid payment.
        """
        raise NotImplementedError

    @abstractmethod
    async def verify(
        self,
        provider_tx_id: str
    ) -> str:
        """
        Return: "success", "failed", or "pending".
        """
        raise NotImplementedError


# ================================================================
# CALL / VOICE GATEWAY INTERFACE
# ================================================================

class ICallGateway(ABC):
    """
    Handles call/voice notifications (optional).
    Example: emergency nurse call, ambulance dispatch, etc.
    """

    @abstractmethod
    async def send_call(
        self,
        phone_number: str,
        message: str
    ) -> bool:
        """
        Return True if call connection success.
        """
        raise NotImplementedError


# ================================================================
# SMS / NOTIFICATION GATEWAY
# ================================================================

class ISmsGateway(ABC):
    """
    Contract for sending SMS / notifications.
    """

    @abstractmethod
    async def send_sms(
        self,
        phone_number: str,
        message: str,
    ) -> bool:
        raise NotImplementedError


# ================================================================
# USAGE / QUOTA REPOSITORY
# ================================================================

class IUsageRepository(ABC):
    """
    Abstracts how 'free usage' is stored.
    Could be stored in:
    - Postgres
    - Redis (fast)
    - MongoDB
    - Firebase
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
    Storing transaction records internally.
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
        Return DB record or ID.
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
    ) -> list:
        """
        For reconciliation service.
        """
        raise NotImplementedError


# ================================================================
# SERVICE ORCHESTRATION CONTRACT
# ================================================================

class IPaymentProcessor(ABC):
    """
    The highest-level abstraction:
    Any payment flow MUST implement this.
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
