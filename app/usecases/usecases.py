# app/domain/usecases.py

import logging
from typing import Optional, Dict

from app.domain.interfaces import (
    IPaymentGateway,
    IUsageRepository,
    ICallGateway,
    IChatGateway
)

from app.domain.consultation_models import RequestResponse, UserRoles, ChannelType
from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# 1. QUOTA CONFIG (SOURCE OF TRUTH)
# ---------------------------------------------------------
SERVICE_FREE_LIMITS: dict[tuple[ChannelType, UserRoles], int] = {
    (ChannelType.CHAT, UserRoles.DOCTOR): settings.LIMIT_DOCTOR_CONSULT,
    (ChannelType.VOICE, UserRoles.DOCTOR): settings.LIMIT_DOCTOR_CONSULT,
    (ChannelType.VIDEO, UserRoles.DOCTOR): settings.LIMIT_DOCTOR_CONSULT,
    (ChannelType.VOICE, UserRoles.BLOOD_REQUESTER): settings.LIMIT_BLOOD_REQUEST,
}


class ConsultationUseCase:
    """
    Orchestrates consultation flow:
    - Free quota
    - Paid gateway
    - Room creation
    """

    class FreeQuotaExceeded(Exception):
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

    # ---------------------------------------------------------
    # SERVICE KEY MAPPING (IMPORTANT FIX FOR DOCTOR BUGS)
    # ---------------------------------------------------------
    def _get_service_key(self, channel: ChannelType, recipient_role: UserRoles):
        return (channel, recipient_role)

    def _get_service_str(self, channel: ChannelType, recipient_role: UserRoles):
        role_map = {
            UserRoles.DOCTOR: "doctor-consult",
            UserRoles.NURSE: "nurse-consult",
            UserRoles.BLOOD_REQUESTER: "blood-request"
        }
        return role_map.get(recipient_role, f"{channel.value}-{recipient_role.value}")

    # ---------------------------------------------------------
    # MAIN ENTRY
    # ---------------------------------------------------------
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

        # FIX: safe fee resolution
        if amount is None:
            amount = settings.fee_map.get(service_str, 500)

        # -----------------------------------------------------
        # 1. IDEMPOTENCY CHECK
        # -----------------------------------------------------
        if idempotency_key:
            existing = await self.usage_repo.get_by_idempotency_key(idempotency_key)
            if existing:
                logger.info(f"Duplicate request: {idempotency_key}")
                return RequestResponse(
                    success=True,
                    message="Request already processed.",
                    request_id=existing.get("request_id"),
                    transaction_id=existing.get("transaction_id"),
                    amount_charged=existing.get("amount", 0)
                )

        # -----------------------------------------------------
        # 2. FREE QUOTA CHECK (FIXED COROUTINE SAFETY)
        # -----------------------------------------------------
        free_limit = SERVICE_FREE_LIMITS.get(service_key, 0)

        used_count = await self.usage_repo.count_uses(caller_id, service_str)

        # HARD FIX: prevent coroutine leakage breaking logic
        if not isinstance(used_count, int):
            logger.error("Invalid usage count detected → forcing 0")
            used_count = 0

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

        # -----------------------------------------------------
        # 3. PAID FLOW
        # -----------------------------------------------------
        if amount > 0:

            # SAFETY CHECK (mock leakage protection)
            if settings.PAYMENT_GATEWAY == "mock" and settings.ENVIRONMENT == "production":
                logger.critical("Mock gateway blocked in production")
                return RequestResponse(success=False, message="Payment service unavailable.")

            pay_res = await self.payment_gateway.charge(
                phone=caller_phone,
                amount=amount,
                description=f"Consultation: {service_str}"
            )

            if not pay_res:
                return RequestResponse(success=False, message="Payment failed.")

            provider_tx = getattr(pay_res, "provider_tx_id", None)
            if not provider_tx:
                return RequestResponse(success=False, message="Invalid payment response.")

            room_id = await self._open_service_room(channel, caller_id, recipient_id)

            await self.usage_repo.record_usage(
                user_id=caller_id,
                service=service_str,
                paid=True,
                amount=amount,
                transaction_id=provider_tx,
                idempotency_key=idempotency_key,
                request_id=room_id
            )

            return RequestResponse(
                success=True,
                message="Payment initiated successfully.",
                request_id=room_id,
                transaction_id=provider_tx,
                ussd_string=getattr(pay_res, "ussd_string", None),
                amount_charged=amount
            )

        # -----------------------------------------------------
        # 4. FALLBACK (FREE ACCESS)
        # -----------------------------------------------------
        room_id = await self._open_service_room(channel, caller_id, recipient_id)

        return RequestResponse(
            success=True,
            message="Service granted.",
            request_id=room_id,
            amount_charged=0,
            remaining_free_uses=-1
        )

    # ---------------------------------------------------------
    # ROOM CREATION
    # ---------------------------------------------------------
    async def _open_service_room(
        self,
        channel: ChannelType,
        user_id: str,
        recipient_id: str
    ) -> str:

        if channel == ChannelType.CHAT:
            return await self.chat_gateway.create_chat_room(user_id, recipient_id)

        return await self.call_gateway.create_call_room(channel, user_id, recipient_id)


# ---------------------------------------------------------
# 2. PUBLIC CONSTANTS (SAFE EXPORTS)
# ---------------------------------------------------------
SERVICE_FEES: Dict[str, int] = settings.fee_map
SERVICE_FREE_LIMITS_SIMPLE: Dict[str, int] = settings.free_limits