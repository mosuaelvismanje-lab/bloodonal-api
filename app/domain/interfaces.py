from abc import ABC, abstractmethod
from typing import Optional

from app.domain.consultation_models import RequestResponse

class ICallGateway(ABC):
    """Interface for services that manage voice/video call rooms."""
    @abstractmethod
    async def create_call_room(self, channel_type: str, user_id: str, recipient_id: str) -> str:
        pass

class IChatGateway(ABC):
    """Interface for services that manage chat rooms."""
    @abstractmethod
    async def create_chat_room(self, user_id: str, recipient_id: str) -> str:
        pass

class IPaymentGateway(ABC):
    """Interface for services that handle mobile money payments."""
    @abstractmethod
    async def charge(self, phone: str, amount: int) -> str | None:
        """Charges a user and returns a transaction ID on success."""
        pass

class IUsageRepository(ABC):
    """Interface for storing and retrieving usage data."""
    @abstractmethod
    async def count_uses(self, user_id: str, service: str) -> int:
        pass

    @abstractmethod
    async def record_usage(
        self,
        user_id: str,
        service: str,
        paid: bool,
        amount: Optional[int],
        transaction_id: Optional[str]
    ):
        pass