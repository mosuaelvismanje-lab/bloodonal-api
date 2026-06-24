from __future__ import annotations

import inspect
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_listing import ServiceListing
from app.modules.notification.notification_service import notification_service
from app.repositories.usage_repo import SQLAlchemyUsageRepository
from app.services.registry import registry

logger = logging.getLogger(__name__)


class ServiceOrchestratorError(Exception):
    pass


class ServiceOrchestratorValidationError(ServiceOrchestratorError):
    pass


class ServiceOrchestratorNotFoundError(ServiceOrchestratorError):
    pass


class ServiceOrchestratorConflictError(ServiceOrchestratorError):
    pass


class ServiceOrchestrator:
    def __init__(
        self,
        registry_client: Any = registry,
        notifier: Any = notification_service,
    ):
        if registry_client is None:
            raise ServiceOrchestratorValidationError("registry_client is required")
        if notifier is None:
            raise ServiceOrchestratorValidationError("notifier is required")

        self.registry = registry_client
        self.notifier = notifier
        self._validate_dependencies()

    def _validate_dependencies(self) -> None:
        if not hasattr(self.registry, "get_service_meta"):
            raise ServiceOrchestratorValidationError(
                "registry must implement get_service_meta()"
            )

        trigger = getattr(self.notifier, "trigger_service_notifications", None)
        if not callable(trigger):
            raise ServiceOrchestratorValidationError(
                f"notifier must implement trigger_service_notifications(), got {type(self.notifier)!r}"
            )

    async def activate_listing(
        self,
        db: AsyncSession,
        user_id: UUID,
        service_type: str,
        activation_ref: str,
    ) -> Optional[ServiceListing]:
        if db is None:
            raise ServiceOrchestratorValidationError("db is required")

        service_type = self._require_text(service_type, "service_type")
        activation_ref = self._require_text(activation_ref, "activation_ref")

        usage_repo = SQLAlchemyUsageRepository(db)

        listing = await self._find_unpublished_listing(
            db=db,
            user_id=user_id,
            service_type=service_type,
            activation_ref=activation_ref,
        )

        if not listing:
            logger.warning(
                "orchestrator_listing_not_found",
                extra={
                    "user_id": str(user_id),
                    "service_type": service_type,
                    "activation_ref": activation_ref,
                },
            )
            return None

        now = datetime.now(timezone.utc)

        try:
            listing.is_published = True

            if hasattr(listing, "published_at"):
                setattr(listing, "published_at", now)

            if hasattr(listing, "updated_at"):
                setattr(listing, "updated_at", now)

            await db.flush()
            await db.refresh(listing)

            amount = self._extract_listing_amount(listing)

            await self._maybe_await(
                usage_repo.record_usage(
                    user_id=user_id,
                    service=service_type,
                    paid=amount > Decimal("0"),
                    amount=float(amount),
                    request_id=str(listing.id),
                )
            )

            await self._trigger_side_effects(
                service_type=service_type,
                user_id=user_id,
                listing_id=str(listing.id),
            )

            logger.info(
                "service_activated",
                extra={
                    "listing_id": str(listing.id),
                    "user_id": str(user_id),
                    "service_type": service_type,
                    "activation_ref": activation_ref,
                },
            )

            return listing

        except Exception as exc:
            logger.exception(
                "service_activation_failed",
                extra={
                    "user_id": str(user_id),
                    "service_type": service_type,
                    "activation_ref": activation_ref,
                },
            )
            raise ServiceOrchestratorError("Failed to activate listing") from exc

    async def _find_unpublished_listing(
        self,
        db: AsyncSession,
        user_id: UUID,
        service_type: str,
        activation_ref: str,
    ) -> Optional[ServiceListing]:
        stmt = (
            select(ServiceListing)
            .where(
                ServiceListing.user_id == user_id,
                ServiceListing.service_type == service_type,
                ServiceListing.is_published.is_(False),
            )
            .with_for_update()
        )

        if hasattr(ServiceListing, "activation_ref"):
            stmt = stmt.where(ServiceListing.activation_ref == activation_ref)
        elif hasattr(ServiceListing, "idempotency_key"):
            stmt = stmt.where(ServiceListing.idempotency_key == activation_ref)

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _trigger_side_effects(
        self,
        service_type: str,
        user_id: UUID,
        listing_id: str,
    ) -> None:
        meta = {}
        try:
            meta = self.registry.get_service_meta(service_type) or {}
        except Exception:
            logger.exception("registry_lookup_failed", extra={"service_type": service_type})

        try:
            if meta.get("is_rtc_supported"):
                logger.info(
                    "rtc_prepared",
                    extra={"service_type": service_type, "listing_id": listing_id},
                )
        except Exception:
            logger.exception(
                "rtc_preparation_failed",
                extra={"service_type": service_type, "listing_id": listing_id},
            )

        try:
            result = self.notifier.trigger_service_notifications(
                service_type=service_type,
                category=meta.get("category", "GENERAL"),
                listing_id=listing_id,
                user_id=user_id,
            )
            await self._maybe_await(result)
        except Exception:
            logger.exception(
                "notification_trigger_failed",
                extra={
                    "service_type": service_type,
                    "listing_id": listing_id,
                    "user_id": str(user_id),
                },
            )

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    def _extract_listing_amount(self, listing: ServiceListing) -> Decimal:
        for field in ("amount", "fee", "price", "cost"):
            if hasattr(listing, field):
                raw = getattr(listing, field)
                if raw is not None:
                    try:
                        return Decimal(str(raw))
                    except Exception:
                        break
        return Decimal("0")

    def _require_text(self, value: Any, field: str) -> str:
        if value is None:
            raise ServiceOrchestratorValidationError(f"{field} is required")
        text = str(value).strip()
        if not text:
            raise ServiceOrchestratorValidationError(f"{field} cannot be empty")
        return text


service_orchestrator = ServiceOrchestrator()