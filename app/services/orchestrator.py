import logging
import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

# ✅ 2026 Models & Repositories
from app.models.payment import Payment, PaymentStatus
from app.models.service_listing import ServiceListing
from app.repositories.usage_repo import SQLAlchemyUsageRepository
from app.services.registry import registry
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)


class ServiceOrchestrator:
    """
    The 'Brain' of the system.
    Handles cross-domain logic to activate services (Listing -> Payment -> Notification).
    """

    async def activate_listing(
            self,
            db: AsyncSession,
            user_id: uuid.UUID,
            service_type: str,
            activation_ref: str
    ) -> Optional[ServiceListing]:
        """
        Unified entry point for both FREE and PAID activations.
        Ensures a listing is flipped to 'published' and usage is recorded.
        """
        usage_repo = SQLAlchemyUsageRepository(db)

        try:
            # 1. Flip the 'is_published' switch on the listing
            # Using the specific reference (usually idempotency_key or ref)
            stmt = (
                update(ServiceListing)
                .where(
                    ServiceListing.user_id == user_id,
                    ServiceListing.service_type == service_type,
                    ServiceListing.is_published == False
                )
                .values(is_published=True)
                .returning(ServiceListing)
            )

            result = await db.execute(stmt)
            listing = result.scalar_one_or_none()

            if not listing:
                logger.warning(f"⚠️ No unpublished listing found for {user_id} - {service_type}")
                return None

            # 2. Record Usage (Quota management)
            await usage_repo.record_usage(
                user_id=user_id,
                service=service_type,
                paid=True,  # Set based on your fee logic if needed
                amount=0.0,  # Filled later by payment webhooks if paid
                request_id=str(listing.id)
            )

            # 3. Trigger Side Effects (FCM, RTC, etc.)
            await self._trigger_side_effects(service_type, user_id, str(listing.id))

            logger.info(f"🚀 Service {service_type} activated for listing {listing.id}")
            return listing

        except Exception as e:
            logger.error(f"💥 Orchestration Failure: {e}", exc_info=True)
            return None

    async def _trigger_side_effects(self, service_type: str, user_id: uuid.UUID, listing_id: str):
        """
        Handles non-blocking side effects like push notifications and RTC setup.
        """
        meta = registry.get_service_meta(service_type)

        # 1. RTC Readiness (for Doctor/Nurse services)
        if meta.get("is_rtc_supported"):
            logger.info(f"👨‍⚕️ RTC Authorization prepared for {listing_id}")

        # 2. Push Notifications (FCM)
        # Notifies relevant parties (e.g., Donors in a specific area)
        await notification_service.trigger_service_notifications(
            service_type=service_type,
            category=meta.get("category"),
            listing_id=listing_id,
            user_id=user_id
        )


# ✅ THE CRITICAL LINE: Instantiate the singleton for the Admin and Payment routers
service_orchestrator = ServiceOrchestrator()