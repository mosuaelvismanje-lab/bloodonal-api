#app/domain/usecases.py
import logging
from typing import Optional
from app.domain.interfaces import IPaymentGateway, IUsageRepository, ICallGateway, IChatGateway
from app.domain.consultation_models import RequestResponse, UserRoles, ChannelType

logger = logging.getLogger(__name__)

# Per-service free-use allowances
SERVICE_FREE_LIMITS: dict[tuple[ChannelType, UserRoles], int] = {
    (ChannelType.CHAT, UserRoles.DOCTOR): 5,
    (ChannelType.VOICE, UserRoles.DOCTOR): 5,
    (ChannelType.VIDEO, UserRoles.DOCTOR): 5,
    (ChannelType.VOICE, UserRoles.BLOOD_REQUESTER): 10,
}

# Per-service fees (XAF)
SERVICE_FEES: dict[tuple[ChannelType, UserRoles], int] = {
    (ChannelType.CHAT, UserRoles.DOCTOR): 300,
    (ChannelType.VOICE, UserRoles.DOCTOR): 300,
    (ChannelType.VIDEO, UserRoles.DOCTOR): 600,
    (ChannelType.VOICE, UserRoles.BLOOD_REQUESTER): 0,  # Blood requests are free
}


class ConsultationUseCase:
    class FreeQuotaExceeded(Exception):
        """Raised when free quota has been exhausted for a user."""
        pass

    def __init__(
            self,
            usage_repo: IUsageRepository,
            payment_gateway: IPaymentGateway,
            call_gateway: ICallGateway,
            chat_gateway: IChatGateway
    ):
        self.usage_repo = usage_repo
        self.payment_gateway = payment_gateway
        self.call_gateway = call_gateway
        self.chat_gateway = chat_gateway

    def _get_service_key(self, channel: ChannelType, recipient_role: UserRoles):
        return (channel, recipient_role)

    def _get_service_str(self, channel: ChannelType, recipient_role: UserRoles):
        return f"{channel.value}_{recipient_role.value}"

    async def handle(
            self,
            caller_id: str,
            recipient_id: str,
            caller_phone: str,
            channel: ChannelType,
            recipient_role: UserRoles,
            idempotency_key: Optional[str] = None  # NEW: Pass key from router
    ) -> RequestResponse:
        service_key = self._get_service_key(channel, recipient_role)
        service_str = self._get_service_str(channel, recipient_role)

        # 1. IDEMPOTENCY CHECK (Double Charge Protection)
        if idempotency_key:
            existing = await self.usage_repo.get_by_idempotency_key(idempotency_key)
            if existing:
                logger.info(f"Duplicate request detected for key: {idempotency_key}")
                return RequestResponse(
                    success=True,
                    message="Request already processed successfully.",
                    request_id=existing.get("request_id"),
                    transaction_id=existing.get("transaction_id"),
                    remaining_free_uses=-2  # Indicator for 'duplicate'
                )

        # 2. FREE QUOTA LOGIC
        free_limit = SERVICE_FREE_LIMITS.get(service_key, 0)
        used_count = await self.usage_repo.count_uses(caller_id, service_str)

        if used_count < free_limit:
            room_id = await self._open_service_room(channel, caller_id, recipient_id)
            await self.usage_repo.record_usage(
                user_id=caller_id,
                service=service_str,
                paid=False,
                amount=0,
                transaction_id=None,
                idempotency_key=idempotency_key  # Save key to prevent re-use
            )
            remaining = max(free_limit - used_count - 1, 0)
            return RequestResponse(
                success=True,
                message=f"Free usage granted. {remaining} remaining.",
                request_id=room_id,
                remaining_free_uses=remaining
            )

        # 3. PAID SERVICE LOGIC
        amount = SERVICE_FEES.get(service_key, 0)
        if amount > 0:
            # We only charge if the idempotency check above didn't find a record
            tx_id = await self.payment_gateway.charge(caller_phone, amount)
            if not tx_id:
                return RequestResponse(success=False, message="Payment failed.")

            room_id = await self._open_service_room(channel, caller_id, recipient_id)
            await self.usage_repo.record_usage(
                user_id=caller_id,
                service=service_str,
                paid=True,
                amount=amount,
                transaction_id=tx_id,
                idempotency_key=idempotency_key, # Link key to this successful payment
                request_id=room_id              # Recommended: store room_id for retries
            )
            return RequestResponse(
                success=True,
                message="Paid request successful.",
                request_id=room_id,
                transaction_id=tx_id
            )

        # 4. ALWAYS-FREE SERVICE (e.g., Blood Requests)
        if amount == 0 and (free_limit == 0 or used_count >= free_limit):
            room_id = await self._open_service_room(channel, caller_id, recipient_id)
            return RequestResponse(
                success=True,
                message="Free service granted.",
                request_id=room_id,
                remaining_free_uses=-1
            )

        raise self.FreeQuotaExceeded(
            f"Free limit of {free_limit} reached for {service_str}, and no fee is configured."
        )

    async def _open_service_room(
            self,
            channel: ChannelType,
            user_id: str,
            recipient_id: str
    ) -> str:
        if channel == ChannelType.CHAT:
            return await self.chat_gateway.create_chat_room(user_id, recipient_id)
        else:  # VOICE or VIDEO
            return await self.call_gateway.create_call_room(channel, user_id, recipient_id)