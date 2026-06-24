from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_listing import ServiceListing

logger = logging.getLogger(__name__)


# =========================================================
# EXCEPTIONS
# =========================================================
class ListingServiceError(Exception):
    """Base exception for listing business logic errors."""


class ListingServiceValidationError(ListingServiceError):
    """Raised when input or dependencies are invalid."""


class ListingServiceNotFoundError(ListingServiceError):
    """Raised when a listing cannot be found."""


class ListingServiceConflictError(ListingServiceError):
    """Raised when a listing state transition is invalid."""


# =========================================================
# SERVICE
# =========================================================
class ListingService:
    """
    Enterprise-grade ServiceListing business logic.

    Responsibilities:
    - Create and manage service listings
    - Publish/unpublish listings
    - Query listing state safely
    - Enforce domain rules

    Rules:
    - No FastAPI imports
    - No HTTP handling
    - No notification side effects
    - No orchestration here
    - No commit ownership here
    """

    def __init__(self, db: AsyncSession):
        if db is None:
            raise ListingServiceValidationError("db is required")
        self.db = db

    # =========================================================
    # VALIDATION HELPERS
    # =========================================================
    def _require_text(self, value: Any, field: str) -> str:
        if value is None:
            raise ListingServiceValidationError(f"{field} is required")
        text = str(value).strip()
        if not text:
            raise ListingServiceValidationError(f"{field} cannot be empty")
        return text

    def _require_uuid(self, value: Any, field: str) -> UUID:
        try:
            return UUID(str(value))
        except Exception as exc:
            raise ListingServiceValidationError(f"{field} must be a valid UUID") from exc

    def _normalize_service_type(self, value: Any) -> str:
        return self._require_text(value, "service_type").lower()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _touch_updated_at(self, listing: ServiceListing) -> None:
        if hasattr(listing, "updated_at"):
            setattr(listing, "updated_at", self._now())

    def _extract_amount(self, payload: Dict[str, Any]) -> Decimal:
        if not isinstance(payload, dict):
            raise ListingServiceValidationError("payload must be a dictionary")

        for key in ("amount", "fee", "price", "cost"):
            if key in payload and payload[key] is not None:
                try:
                    amount = Decimal(str(payload[key]))
                except Exception as exc:
                    raise ListingServiceValidationError(f"{key} must be numeric") from exc

                if amount < 0:
                    raise ListingServiceValidationError(f"{key} cannot be negative")

                return amount

        return Decimal("0")

    def _ensure_listing_contract(self, listing: ServiceListing) -> None:
        if not isinstance(listing, ServiceListing):
            raise ListingServiceValidationError(
                "listing must be a ServiceListing instance"
            )

    # =========================================================
    # CREATE
    # =========================================================
    async def create_listing(
        self,
        *,
        user_id: UUID,
        service_type: str,
        activation_ref: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> ServiceListing:
        """
        Create a new listing in draft/unpublished state.
        """
        if user_id is None:
            raise ListingServiceValidationError("user_id is required")

        service_type_norm = self._normalize_service_type(service_type)
        activation_ref_norm = (
            self._require_text(activation_ref, "activation_ref")
            if activation_ref
            else None
        )
        payload = payload or {}

        listing = ServiceListing(
            user_id=user_id,
            service_type=service_type_norm,
            is_published=False,
        )

        if hasattr(listing, "activation_ref") and activation_ref_norm:
            setattr(listing, "activation_ref", activation_ref_norm)
        elif hasattr(listing, "idempotency_key") and activation_ref_norm:
            setattr(listing, "idempotency_key", activation_ref_norm)

        if hasattr(listing, "amount"):
            setattr(listing, "amount", self._extract_amount(payload))
        elif hasattr(listing, "fee") and payload.get("fee") is not None:
            setattr(listing, "fee", self._extract_amount(payload))

        if hasattr(listing, "published_at"):
            setattr(listing, "published_at", None)

        if hasattr(listing, "created_at"):
            setattr(listing, "created_at", self._now())

        self._touch_updated_at(listing)

        self.db.add(listing)
        await self.db.flush()
        await self.db.refresh(listing)

        logger.info(
            "listing_created",
            extra={
                "listing_id": str(getattr(listing, "id", "")),
                "user_id": str(user_id),
                "service_type": service_type_norm,
            },
        )

        return listing

    # =========================================================
    # READ
    # =========================================================
    async def get_listing_by_id(
        self,
        listing_id: Any,
        *,
        for_update: bool = False,
    ) -> ServiceListing:
        listing_uuid = self._require_uuid(listing_id, "listing_id")

        stmt = select(ServiceListing).where(ServiceListing.id == listing_uuid)
        if for_update:
            stmt = stmt.with_for_update()

        result = await self.db.execute(stmt)
        listing = result.scalar_one_or_none()

        if not listing:
            raise ListingServiceNotFoundError(f"Listing {listing_uuid} not found")

        return listing

    async def get_user_listings(
        self,
        user_id: Any,
        *,
        service_type: Optional[str] = None,
        published_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ServiceListing]:
        if limit <= 0:
            raise ListingServiceValidationError("limit must be greater than zero")
        if offset < 0:
            raise ListingServiceValidationError("offset cannot be negative")

        user_uuid = self._require_uuid(user_id, "user_id")

        stmt = select(ServiceListing).where(ServiceListing.user_id == user_uuid)

        if service_type:
            stmt = stmt.where(
                ServiceListing.service_type == self._normalize_service_type(service_type)
            )

        if published_only and hasattr(ServiceListing, "is_published"):
            stmt = stmt.where(ServiceListing.is_published.is_(True))

        if hasattr(ServiceListing, "updated_at"):
            stmt = stmt.order_by(ServiceListing.updated_at.desc())
        elif hasattr(ServiceListing, "created_at"):
            stmt = stmt.order_by(ServiceListing.created_at.desc())
        else:
            stmt = stmt.order_by(ServiceListing.id.desc())

        stmt = stmt.offset(offset).limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_unpublished_listing(
        self,
        *,
        user_id: Any,
        service_type: str,
        activation_ref: Optional[str] = None,
    ) -> Optional[ServiceListing]:
        """
        Finds a listing that is eligible for activation.
        Used by orchestrator / admin activation flows.
        """
        user_uuid = self._require_uuid(user_id, "user_id")
        service_type_norm = self._normalize_service_type(service_type)

        stmt = (
            select(ServiceListing)
            .where(
                ServiceListing.user_id == user_uuid,
                ServiceListing.service_type == service_type_norm,
                ServiceListing.is_published.is_(False),
            )
            .with_for_update()
        )

        if activation_ref:
            activation_ref_norm = self._require_text(activation_ref, "activation_ref")
            if hasattr(ServiceListing, "activation_ref"):
                stmt = stmt.where(ServiceListing.activation_ref == activation_ref_norm)
            elif hasattr(ServiceListing, "idempotency_key"):
                stmt = stmt.where(ServiceListing.idempotency_key == activation_ref_norm)

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # =========================================================
    # STATE TRANSITIONS
    # =========================================================
    async def publish_listing(self, listing_id: Any) -> ServiceListing:
        listing = await self.get_listing_by_id(listing_id, for_update=True)

        if getattr(listing, "is_published", False):
            raise ListingServiceConflictError("Listing is already published")

        listing.is_published = True

        if hasattr(listing, "published_at"):
            setattr(listing, "published_at", self._now())

        self._touch_updated_at(listing)

        await self.db.flush()
        await self.db.refresh(listing)

        logger.info(
            "listing_published",
            extra={"listing_id": str(listing.id)},
        )

        return listing

    async def unpublish_listing(self, listing_id: Any) -> ServiceListing:
        listing = await self.get_listing_by_id(listing_id, for_update=True)

        if not getattr(listing, "is_published", False):
            raise ListingServiceConflictError("Listing is already unpublished")

        listing.is_published = False

        if hasattr(listing, "published_at"):
            setattr(listing, "published_at", None)

        self._touch_updated_at(listing)

        await self.db.flush()
        await self.db.refresh(listing)

        logger.info(
            "listing_unpublished",
            extra={"listing_id": str(listing.id)},
        )

        return listing

    async def update_listing_fields(
        self,
        listing_id: Any,
        data: Dict[str, Any],
    ) -> ServiceListing:
        """
        Safe partial updates for listing fields.
        """
        if not isinstance(data, dict):
            raise ListingServiceValidationError("data must be a dictionary")

        listing = await self.get_listing_by_id(listing_id, for_update=True)

        allowed_fields = {
            "title",
            "description",
            "service_type",
            "amount",
            "fee",
            "price",
            "cost",
            "activation_ref",
            "idempotency_key",
        }

        for key, value in data.items():
            if key not in allowed_fields:
                continue

            if key == "service_type":
                setattr(listing, key, self._normalize_service_type(value))
            elif key in {"activation_ref", "idempotency_key"}:
                if value is not None:
                    setattr(listing, key, self._require_text(value, key))
            elif key in {"amount", "fee", "price", "cost"}:
                try:
                    setattr(listing, key, Decimal(str(value)))
                except Exception as exc:
                    raise ListingServiceValidationError(f"{key} must be numeric") from exc
            else:
                setattr(listing, key, value)

        self._touch_updated_at(listing)

        await self.db.flush()
        await self.db.refresh(listing)

        logger.info(
            "listing_updated",
            extra={"listing_id": str(listing.id)},
        )

        return listing

    async def delete_listing(self, listing_id: Any) -> None:
        listing = await self.get_listing_by_id(listing_id, for_update=True)
        await self.db.delete(listing)
        await self.db.flush()

        logger.info(
            "listing_deleted",
            extra={"listing_id": str(listing.id)},
        )