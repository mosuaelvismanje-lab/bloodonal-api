import logging
from typing import Union, Any
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status, BackgroundTasks

# ✅ MASTER ENGINE IMPORTS
from app.services.payment_service import PaymentService
from app.services.orchestrator import ServiceOrchestrator  # ✅ NEW: For activation
from app.services.notification_service import notification_service  # ✅ NEW: For clean dispatch
from app.crud.blood_request import create_blood_request as crud_create_blood_request
from app.schemas.blood_requests import BloodRequestCreate
from app.schemas.payment import PaymentResponseOut

logger = logging.getLogger(__name__)


class BloodRequestService:
    def __init__(self, db: AsyncSession):
        self.db = db
        # Initialize the orchestrator to handle the publication logic
        self.orchestrator = ServiceOrchestrator(db)

    async def create_request_orchestrator(
            self,
            req: BloodRequestCreate,
            user_uid: str,
            background_tasks: BackgroundTasks
    ) -> Union[Any, PaymentResponseOut]:
        """
        2026 Modular Orchestrator:
        1. Delegates Quota/Payment to Master PaymentService.
        2. If Payment is PENDING (USSD), exits and returns USSD payload.
        3. If Payment is SUCCESS (Free/Promo), persists data and triggers Orchestrator.
        """

        # --- 1. DELEGATE TO MASTER PAYMENT ENGINE ---
        # This handles: Quota checks, Promo switches, and USSD generation
        payment_status = await PaymentService.process_payment(
            db=self.db,
            user_id=user_uid,
            user_phone=req.phone,
            category="blood-request"
        )

        # If user must pay or has a pending transaction, return the USSD info immediately
        if payment_status.status == "PENDING":
            logger.info(f"Payment Required for User {user_uid}. Returning USSD.")
            return payment_status

        # --- 2. PERSIST MEDICAL DATA (Cleared Path) ---
        try:
            # Step A: Create the actual Blood Request medical record
            # We do not commit yet; we want the orchestrator to finish the job
            br = await crud_create_blood_request(self.db, req, user_id=user_uid)

            # Step B: Trigger Orchestrator for FREE/SUCCESS path
            # This marks the ServiceListing as published and handles notifications
            activated = await self.orchestrator.handle_free_activation(
                user_id=user_uid,
                service_type="blood-request"
            )

            if not activated:
                raise Exception("Service Orchestrator failed to publish listing.")

            # We refresh to ensure we return the final state
            await self.db.refresh(br)

            # --- 3. DISPATCH NOTIFICATIONS (Async) ---
            # We now use the dedicated notification_service instead of importing from endpoints
            background_tasks.add_task(
                notification_service.trigger_service_notifications,
                service_type="blood-request",
                category="medical",
                listing_id=str(br.id),
                user_id=user_uid
            )

            logger.info(f"✅ Blood Request {br.id} activated via Orchestrator for {user_uid}")
            return br

        except Exception as e:
            await self.db.rollback()
            logger.error(f"💥 BLOOD_SERVICE_ERROR: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to finalize blood request activation."
            )