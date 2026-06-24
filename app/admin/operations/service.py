from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payment.models import Payment, PaymentStatus
from app.repositories.payment_repo import PaymentRepository
from app.services.orchestrator import service_orchestrator

logger = logging.getLogger(__name__)


# =========================================================
# EXCEPTIONS
# =========================================================
class AdminOperationsError(Exception):
    """Base exception for admin operations."""


class AdminOperationValidationError(AdminOperationsError):
    """Raised when admin input or dependencies are invalid."""


class AdminOperationNotFoundError(AdminOperationsError):
    """Raised when the target payment or record cannot be found."""


class AdminOperationConflictError(AdminOperationsError):
    """Raised when the requested admin action conflicts with state."""


# =========================================================
# SERVICE
# =========================================================
class AdminOperationsService:
    """
    Enterprise-grade admin operations service.

    DESIGN RULES:
    - No FastAPI imports
    - No HTTP handling
    - No transaction ownership (router controls it)
    - Repository handles writes
    - Orchestrator handles side-effects
    - Service coordinates workflow

    REQUIRED USAGE:
        async with db.begin():
            await service.verify_payment_override(...)
    """

    def __init__(
        self,
        db: AsyncSession,
        payment_repo: Optional[PaymentRepository] = None,
        orchestrator: Any = None,
    ):
        if db is None:
            raise AdminOperationValidationError("db is required")

        self.db = db
        self.payment_repo = payment_repo or PaymentRepository(db)
        self.orchestrator = orchestrator or service_orchestrator

        self._validate_dependencies()

    # =========================================================
    # DEPENDENCY VALIDATION
    # =========================================================
    def _validate_dependencies(self) -> None:
        if not hasattr(self.payment_repo, "update_status"):
            raise AdminOperationValidationError(
                "PaymentRepository must implement update_status()"
            )

        if not hasattr(self.orchestrator, "activate_listing"):
            raise AdminOperationValidationError(
                "service_orchestrator must implement activate_listing()"
            )

    # =========================================================
    # CORE FLOW
    # =========================================================
    async def verify_payment_override(
        self,
        request: Any,
        admin_email: str,
    ) -> Dict[str, Any]:

        # -------- VALIDATION --------
        amount = self._normalize_amount(getattr(request, "amount", None))
        payer_phone = self._normalize_phone(getattr(request, "payer_phone", None))
        transaction_id = self._require_text(
            getattr(request, "transaction_id", None),
            "transaction_id",
        )
        admin_email = self._require_text(admin_email, "admin_email")

        # -------- FIND PAYMENT --------
        payment = await self._find_pending_payment(
            amount=amount,
            payer_phone=payer_phone,
        )

        if not payment:
            raise AdminOperationNotFoundError(
                "No matching pending payment found"
            )

        # -------- UPDATE STATE --------
        updated_payment = await self._mark_payment_success(
            payment=payment,
            transaction_id=transaction_id,
            admin_email=admin_email,
        )

        # -------- ORCHESTRATION --------
        try:
            await self._activate_service(updated_payment)
        except Exception as exc:
            logger.exception(
                "orchestration_failed",
                extra={
                    "payment_id": str(updated_payment.id),
                    "payment_type": getattr(updated_payment, "payment_type", None),
                },
            )

            # IMPORTANT: let router transaction rollback everything
            raise AdminOperationsError(
                "Payment updated but service activation failed"
            ) from exc

        # -------- AUDIT LOG --------
        logger.info(
            "admin_payment_override_verified",
            extra={
                "payment_id": str(updated_payment.id),
                "payment_type": getattr(updated_payment, "payment_type", None),
                "admin_email": admin_email,
            },
        )

        return {
            "success": True,
            "reference": str(updated_payment.id),
            "message": f"Service {updated_payment.payment_type} activated via admin bypass.",
        }

    # =========================================================
    # FIND PAYMENT (READ ONLY)
    # =========================================================
    async def _find_pending_payment(
        self,
        amount: Decimal,
        payer_phone: str,
    ) -> Optional[Payment]:

        stmt = (
            select(Payment)
            .where(
                Payment.status == PaymentStatus.PENDING,
                Payment.amount == amount,
            )
            .order_by(Payment.created_at.desc())
        )

        result = await self.db.execute(stmt)
        candidates: List[Payment] = result.scalars().all()

        if not candidates:
            return None

        for payment in candidates:
            try:
                if self._extract_phone_from_payment(payment) == payer_phone:
                    return payment
            except Exception:
                # defensive against bad metadata
                continue

        return None

    # =========================================================
    # UPDATE PAYMENT (WRITE VIA REPO)
    # =========================================================
    async def _mark_payment_success(
        self,
        payment: Payment,
        transaction_id: str,
        admin_email: str,
    ) -> Payment:

        updated_payment = await self.payment_repo.update_status(
            payment_id=payment.id,
            new_status=PaymentStatus.SUCCESS,
            provider_tx_id=transaction_id,
        )

        if not updated_payment:
            raise AdminOperationConflictError(
                "Transaction already verified or payment finalized"
            )

        metadata = getattr(updated_payment, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}

        metadata.update(
            {
                "verified_by": admin_email,
                "mode": "admin_bypass",
                "verified_at": "manual_override",
            }
        )

        updated_payment.metadata = metadata

        return updated_payment

    # =========================================================
    # ORCHESTRATION
    # =========================================================
    async def _activate_service(self, payment: Payment) -> None:
        await self.orchestrator.activate_listing(
            db=self.db,
            user_id=payment.user_id,
            service_type=payment.payment_type,
            activation_ref=payment.idempotency_key,
        )

    # =========================================================
    # HELPERS
    # =========================================================
    def _require_text(self, value: Any, field: str) -> str:
        if value is None:
            raise AdminOperationValidationError(f"{field} is required")

        text = str(value).strip()
        if not text:
            raise AdminOperationValidationError(f"{field} cannot be empty")

        return text

    def _normalize_phone(self, value: Any) -> str:
        raw = self._require_text(value, "payer_phone")
        digits = "".join(ch for ch in raw if ch.isdigit())

        if not digits:
            raise AdminOperationValidationError(
                "payer_phone must contain digits"
            )

        return digits

    def _normalize_amount(self, value: Any) -> Decimal:
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise AdminOperationValidationError(
                "amount must be numeric"
            ) from exc

        if amount <= 0:
            raise AdminOperationValidationError(
                "amount must be greater than zero"
            )

        return amount

    def _extract_phone_from_payment(self, payment: Payment) -> str:
        metadata = getattr(payment, "metadata", None)

        if isinstance(metadata, dict):
            phone = metadata.get("phone")
            if phone:
                return self._normalize_phone(phone)

        return ""

    # =========================================================
    # READ SUPPORT
    # =========================================================
    async def get_recent_payments(
        self,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:

        if not isinstance(limit, int) or limit <= 0:
            raise AdminOperationValidationError(
                "limit must be a positive integer"
            )

        stmt = (
            select(Payment)
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        payments = result.scalars().all()

        return [
            {
                "reference": str(p.id),
                "amount": p.amount,
                "status": p.status,
                "payment_type": getattr(p, "payment_type", None),
                "user_id": str(getattr(p, "user_id", "")),
                "created_at": getattr(p, "created_at", None),
            }
            for p in payments
        ]