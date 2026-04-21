import logging
from typing import Union, Any

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status, BackgroundTasks

# ✅ MASTER ENGINE IMPORTS
from app.services.payment_service import PaymentService
from app.services.orchestrator import ServiceOrchestrator
from app.services.notification_service import notification_service
from app.crud.blood_request import create_blood_request as crud_create_blood_request
from app.schemas.blood_requests import BloodRequestCreate
from app.schemas.payment import PaymentResponseOut

logger = logging.getLogger(__name__)


class BloodRequestService:
    """
    2026 Unified Blood Request Engine
    - Payment-first architecture
    - Free usage auto-activation
    - Background notifications
    """

    CATEGORY = "blood-request"
    NOTIFICATION_CATEGORY = "medical"

    def __init__(self, db: AsyncSession):
        self.db = db
        self.orchestrator = ServiceOrchestrator(db)

    # =========================================================
    # MAIN ENTRY POINT (FIXED NAME FOR ROUTER COMPATIBILITY)
    # =========================================================
    async def create_blood_request_orchestrator(
        self,
        req: BloodRequestCreate,
        user_uid: str,
        background_tasks: BackgroundTasks
    ) -> Union[Any, PaymentResponseOut]:

        """
        1. Check payment / quota via PaymentService
        2. If PENDING → return USSD response immediately
        3. If SUCCESS → create record + orchestrate + notify
        """

        # -----------------------------
        # 1. PAYMENT ENGINE CALL
        # -----------------------------
        payment_status = await PaymentService.process_payment(
            db=self.db,
            user_id=user_uid,
            user_phone=req.phone,
            category=self.CATEGORY,
            req_data=req.model_dump() if hasattr(req, "model_dump") else req.dict()
        )

        # -----------------------------
        # 2. PAYMENT REQUIRED FLOW
        # -----------------------------
        if payment_status.status == "PENDING":
            logger.info(f"💳 Payment required for {user_uid}")
            return payment_status

        # -----------------------------
        # 3. FREE / SUCCESS FLOW
        # -----------------------------
        try:
            # Create DB record
            br = await crud_create_blood_request(
                self.db,
                req,
                user_id=user_uid
            )

            # Activate via orchestrator
            activated = await self.orchestrator.handle_free_activation(
                user_id=user_uid,
                service_type=self.CATEGORY
            )

            if not activated:
                raise Exception("Orchestrator activation failed")

            await self.db.refresh(br)

            # -----------------------------
            # 4. ASYNC NOTIFICATIONS
            # -----------------------------
            background_tasks.add_task(
                notification_service.trigger_service_notifications,
                service_type=self.CATEGORY,
                category=self.NOTIFICATION_CATEGORY,
                listing_id=str(br.id),
                user_id=user_uid
            )

            logger.info(f"✅ Blood request activated: {br.id} for {user_uid}")
            return br

        except Exception as e:
            await self.db.rollback()
            logger.error(f"💥 BloodRequestService error: {e}", exc_info=True)

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process blood request"
            )