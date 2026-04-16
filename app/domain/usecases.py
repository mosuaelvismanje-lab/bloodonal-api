
#app/domain/usecases
import logging
from typing import Optional, Dict
from app.domain.interfaces import IPaymentGateway, IUsageRepository, ICallGateway, IChatGateway
from app.domain.consultation_models import RequestResponse, UserRoles, ChannelType
from app.config import settings  # ✅ Source of Truth

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# 1. ADVANCED QUOTA LOGIC (For ConsultationUseCase)
# ---------------------------------------------------------
# ✅ Link these directly to the corrected .env-mapped variables
SERVICE_FREE_LIMITS: dict[tuple[ChannelType, UserRoles], int] = {
    (ChannelType.CHAT, UserRoles.DOCTOR): settings.LIMIT_DOCTOR_CONSULT,
    (ChannelType.VOICE, UserRoles.DOCTOR): settings.LIMIT_DOCTOR_CONSULT,
    (ChannelType.VIDEO, UserRoles.DOCTOR): settings.LIMIT_DOCTOR_CONSULT,
    (ChannelType.VOICE, UserRoles.BLOOD_REQUESTER): settings.LIMIT_BLOOD_REQUEST,
}

class ConsultationUseCase:
    """
    Handles orchestration of consultation requests, balancing
    free quota limits against paid mobile money transactions.
    """
    class FreeQuotaExceeded(Exception):
        """Raised when free quota has been exhausted."""
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
        # ✅ Standardized hyphenated naming to match settings.fee_map and DB
        role_map = {
            UserRoles.DOCTOR: "doctor-consult",
            UserRoles.NURSE: "nurse-consult",
            UserRoles.BLOOD_REQUESTER: "blood-request"
        }
        return role_map.get(recipient_role, f"{channel.value}-{recipient_role.value}")

    async def handle(
            self,
            caller_id: str,
            recipient_id: str,
            caller_phone: str,
            channel: ChannelType,
            recipient_role: UserRoles,
            amount: Optional[int] = None,
            idempotency_key: Optional[str] = None
    ) -> RequestResponse:
        service_key = self._get_service_key(channel, recipient_role)
        service_str = self._get_service_str(channel, recipient_role)

        # ✅ DYNAMIC FEE LOOKUP: Correctly pulls 500 from .env via settings.fee_map
        if amount is None:
            amount = settings.fee_map.get(service_str, 500)

        # 1. IDEMPOTENCY CHECK
        if idempotency_key:
            existing = await self.usage_repo.get_by_idempotency_key(idempotency_key)
            if existing:
                logger.info(f"Duplicate request detected: {idempotency_key}")
                return RequestResponse(
                    success=True,
                    message="Request already processed.",
                    request_id=existing.get("request_id"),
                    transaction_id=existing.get("transaction_id"),
                    amount_charged=existing.get("amount", 0)
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
                idempotency_key=idempotency_key,
                request_id=room_id
            )
            remaining = max(free_limit - used_count - 1, 0)
            return RequestResponse(
                success=True,
                message=f"Free usage granted. {remaining} remaining.",
                request_id=room_id,
                amount_charged=0,
                remaining_free_uses=remaining
            )

        # 3. PAID SERVICE LOGIC (Check for "mock" security in handle)
        if amount > 0:
            # ✅ Security Guard: Check if we are accidentally using mock in production
            if settings.PAYMENT_GATEWAY == "mock" and settings.ENVIRONMENT == "production":
                logger.critical("SECURITY ALERT: Mock payment gateway triggered in production!")
                return RequestResponse(success=False, message="Payment service unavailable.")

            pay_res = await self.payment_gateway.charge(
                phone=caller_phone,
                amount=amount,
                description=f"Consultation: {service_str}"
            )

            if not pay_res or not pay_res.provider_tx_id:
                return RequestResponse(success=False, message="Payment initiation failed.")

            room_id = await self._open_service_room(channel, caller_id, recipient_id)

            await self.usage_repo.record_usage(
                user_id=caller_id,
                service=service_str,
                paid=True,
                amount=amount,
                transaction_id=pay_res.provider_tx_id,
                idempotency_key=idempotency_key,
                request_id=room_id
            )

            return RequestResponse(
                success=True,
                message="Payment reference generated. USSD prompt sent.",
                request_id=room_id,
                transaction_id=pay_res.provider_tx_id,
                ussd_string=pay_res.ussd_string,
                amount_charged=amount
            )

        # 4. ALWAYS-FREE FALLBACK
        room_id = await self._open_service_room(channel, caller_id, recipient_id)
        return RequestResponse(
            success=True,
            message="Service granted.",
            request_id=room_id,
            amount_charged=0,
            remaining_free_uses=-1
        )

    async def _open_service_room(
            self,
            channel: ChannelType,
            user_id: str,
            recipient_id: str
    ) -> str:
        if channel == ChannelType.CHAT:
            return await self.chat_gateway.create_chat_room(user_id, recipient_id)
        else:
            return await self.call_gateway.create_call_room(channel, user_id, recipient_id)

# ---------------------------------------------------------
# 2. SIMPLE CONSTANTS (Pulled from settings properties)
# ---------------------------------------------------------

# ✅ Directly utilize the @property Dicts we defined in Settings
SERVICE_FEES: Dict[str, int] = settings.fee_map

SERVICE_FREE_LIMITS_SIMPLE: Dict[str, int] = settings.free_limits