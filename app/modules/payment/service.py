from __future__ import annotations

import logging
import re
import secrets
import string
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError


from app.modules.blood.wallet.models import Wallet, WalletTransaction
from app.modules.payment.models import PaymentStatus, Payment

try:
    from app.modules.security.fraud_detection import FraudDetector
except ImportError:  # fallback if you placed it under blood.security
    from app.modules.blood.security.fraud_detection import FraudDetector  # type: ignore

logger = logging.getLogger(__name__)


class PaymentService:
    """
    Production-grade payment service.

    Responsibilities:
    - initiate payment with a reference code
    - verify payment from SMS + transaction id
    - prevent duplicate payment processing
    - block suspicious payments via fraud detection
    - credit wallet after successful verification
    - expose admin/user payment utilities
    """

    DEFAULT_EXPIRY_MINUTES = 15
    DEFAULT_WALLET_OWNER_TYPE = "DONOR"

    def __init__(
        self,
        db: AsyncSession,
        fraud_detector: Optional[FraudDetector] = None,
        wallet_owner_type: str = DEFAULT_WALLET_OWNER_TYPE,
    ):
        self.db = db
        self.wallet_owner_type = wallet_owner_type.upper().strip()
        self.fraud_detector = fraud_detector or FraudDetector(db)

    # =========================================================
    # INITIATE PAYMENT
    # =========================================================
    async def initiate_payment(
        self,
        user_id: UUID,
        amount: Decimal,
        phone: str,
        currency: str = "XAF",
        provider: str = "MTN",
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a pending/awaiting-verification payment.
        The user must include the generated reference_code as the payment reason.
        """

        amount = self._normalize_amount(amount)
        if amount <= 0:
            raise ValueError("Amount must be greater than zero")

        currency = (currency or "XAF").upper().strip()
        provider = (provider or "UNKNOWN").upper().strip()
        phone = (phone or "").strip()

        if idempotency_key:
            existing = await self._get_payment_by_idempotency(idempotency_key)
            if existing:
                return self._serialize_payment(existing)

        reference_code = self._generate_reference_code(6)

        payment = self._build_payment(
            user_id=user_id,
            amount=amount,
            currency=currency,
            phone=phone,
            provider=provider,
            reference_code=reference_code,
            idempotency_key=idempotency_key,
            payment_status=PaymentStatus.AWAITING_VERIFICATION,
            metadata={
                **(metadata or {}),
                "initiated_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": (
                    datetime.now(timezone.utc)
                    + timedelta(minutes=self.DEFAULT_EXPIRY_MINUTES)
                ).isoformat(),
            },
        )

        try:
            self.db.add(payment)
            await self.db.flush()
            await self.db.commit()
            await self.db.refresh(payment)

            logger.info("Payment initiated user=%s ref=%s", user_id, reference_code)

            return {
                "paymentId": str(payment.id),
                "referenceCode": reference_code,
                "amount": str(payment.amount),
                "currency": payment.currency,
                "status": payment.status.value if hasattr(payment.status, "value") else str(payment.status),
                "instruction": f"Use code '{reference_code}' as reason/message for the transfer.",
                "expiresAt": payment.metadata.get("expires_at") if getattr(payment, "metadata", None) else None,
            }

        except SQLAlchemyError as exc:
            await self.db.rollback()
            logger.exception("Failed to initiate payment")
            raise exc

    # =========================================================
    # VERIFY PAYMENT
    # =========================================================
    async def verify_payment(
        self,
        user_id: UUID,
        transaction_id: str,
        sms_message: str,
        phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Verifies payment using:
        - transaction_id from SMS
        - reference code embedded in the SMS reason/message
        """

        transaction_id = (transaction_id or "").strip()
        sms_message = sms_message or ""
        phone = (phone or "").strip()

        reference_code = self._extract_reference_code(sms_message)
        if not reference_code:
            return {
                "status": "failed",
                "reason": "reference_code_not_found",
            }

        amount_from_sms = self._extract_amount_from_sms(sms_message)

        try:
            payment = await self._get_payment_for_update(
                user_id=user_id,
                reference_code=reference_code,
            )

            if not payment:
                return {
                    "status": "failed",
                    "reason": "invalid_reference_code",
                    "referenceCode": reference_code,
                }

            if payment.status == PaymentStatus.SUCCESS:
                return {
                    "status": "duplicate",
                    "reason": "already_processed",
                    "paymentId": str(payment.id),
                    "referenceCode": reference_code,
                }

            if getattr(payment, "provider_transaction_id", None):
                if str(payment.provider_transaction_id) == transaction_id:
                    return {
                        "status": "duplicate",
                        "reason": "transaction_already_used",
                        "paymentId": str(payment.id),
                        "referenceCode": reference_code,
                    }

            if amount_from_sms is not None:
                sms_amount = self._normalize_amount(amount_from_sms)
                if sms_amount != self._normalize_amount(payment.amount):
                    payment.status = PaymentStatus.FAILED
                    self._append_metadata(payment, {
                        "verification_reason": "amount_mismatch",
                        "sms_message": sms_message,
                        "transaction_id": transaction_id,
                        "reference_code": reference_code,
                        "sms_amount": str(sms_amount),
                    })
                    await self.db.commit()
                    return {
                        "status": "failed",
                        "reason": "amount_mismatch",
                        "paymentId": str(payment.id),
                        "referenceCode": reference_code,
                    }

            fraud_result = await self.fraud_detector.check(
                user_id=str(payment.user_id),
                amount=self._normalize_amount(payment.amount),
                phone=phone or getattr(payment, "phone_number", "") or "",
                idempotency_key=getattr(payment, "idempotency_key", None),
                provider_tx_id=transaction_id,
            )

            if fraud_result.is_fraud:
                payment.status = PaymentStatus.BLOCKED
                payment.provider_transaction_id = transaction_id
                self._append_metadata(payment, {
                    "verification_reason": "fraud_blocked",
                    "sms_message": sms_message,
                    "reference_code": reference_code,
                    "fraud": {
                        "risk_score": fraud_result.risk_score,
                        "reasons": fraud_result.reasons,
                        "metadata": fraud_result.metadata,
                    },
                })
                await self.db.commit()

                return {
                    "status": "blocked",
                    "reason": "fraud_detected",
                    "paymentId": str(payment.id),
                    "referenceCode": reference_code,
                    "riskScore": fraud_result.risk_score,
                    "reasons": fraud_result.reasons,
                }

            wallet = await self._credit_wallet(
                owner_id=payment.user_id,
                owner_type=self.wallet_owner_type,
                amount=self._normalize_amount(payment.amount),
                reference_code=reference_code,
                transaction_id=transaction_id,
                description="Payment verification credit",
            )

            payment.status = PaymentStatus.SUCCESS
            payment.provider_transaction_id = transaction_id
            payment.wallet_id = wallet.id
            self._append_metadata(payment, {
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "sms_message": sms_message,
                "reference_code": reference_code,
                "wallet_id": str(wallet.id),
                "fraud_risk_score": fraud_result.risk_score,
            })

            await self.db.commit()
            await self.db.refresh(payment)
            await self.db.refresh(wallet)

            logger.info(
                "Payment verified user=%s payment=%s ref=%s tx=%s",
                user_id,
                payment.id,
                reference_code,
                transaction_id,
            )

            return {
                "status": "success",
                "paymentId": str(payment.id),
                "referenceCode": reference_code,
                "transactionId": transaction_id,
                "walletId": str(wallet.id),
                "walletBalance": str(wallet.balance),
                "amount": str(payment.amount),
            }

        except SQLAlchemyError as exc:
            await self.db.rollback()
            logger.exception("Payment verification failed")
            raise exc
        except Exception as exc:
            await self.db.rollback()
            logger.exception("Unexpected verification error")
            raise exc

    # =========================================================
    # GET USER PAYMENTS
    # =========================================================
    async def get_user_payments(
        self,
        user_id: UUID,
        status: Optional[PaymentStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        stmt = (
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(desc(Payment.created_at))
            .offset(offset)
            .limit(limit)
        )

        if status is not None:
            stmt = stmt.where(Payment.status == status)

        result = await self.db.execute(stmt)
        items = result.scalars().all()

        return {
            "total": len(items),
            "items": [self._serialize_payment(p) for p in items],
        }

    # =========================================================
    # GET PAYMENT BY ID
    # =========================================================
    async def get_payment(self, payment_id: UUID) -> Optional[Dict[str, Any]]:
        payment = await self._get_payment_by_id(payment_id)
        if not payment:
            return None
        return self._serialize_payment(payment)

    # =========================================================
    # CANCEL PAYMENT
    # =========================================================
    async def cancel_payment(
        self,
        payment_id: UUID,
        user_id: UUID,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            payment = await self._get_payment_by_id(payment_id, user_id=user_id)

            if not payment:
                return {
                    "status": "failed",
                    "reason": "payment_not_found",
                }

            if payment.status == PaymentStatus.SUCCESS:
                return {
                    "status": "failed",
                    "reason": "already_successful",
                    "paymentId": str(payment.id),
                }

            payment.status = PaymentStatus.FAILED
            self._append_metadata(payment, {
                "cancelled_at": datetime.now(timezone.utc).isoformat(),
                "cancel_reason": reason or "user_cancelled",
            })

            await self.db.commit()

            return {
                "status": "success",
                "paymentId": str(payment.id),
                "message": "Payment cancelled",
            }

        except SQLAlchemyError as exc:
            await self.db.rollback()
            logger.exception("Cancel payment failed")
            raise exc

    # =========================================================
    # ADMIN: LIST ALL PAYMENTS
    # =========================================================
    async def get_all_payments(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[PaymentStatus] = None,
    ) -> Dict[str, Any]:
        stmt = (
            select(Payment)
            .order_by(desc(Payment.created_at))
            .offset(offset)
            .limit(limit)
        )

        if status is not None:
            stmt = stmt.where(Payment.status == status)

        result = await self.db.execute(stmt)
        items = result.scalars().all()

        return {
            "total": len(items),
            "items": [self._serialize_payment(p) for p in items],
        }

    # =========================================================
    # ADMIN: FORCE VERIFY
    # =========================================================
    async def force_verify(self, payment_id: UUID) -> Dict[str, Any]:
        try:
            payment = await self._get_payment_by_id(payment_id)

            if not payment:
                return {
                    "status": "failed",
                    "reason": "payment_not_found",
                }

            if payment.status == PaymentStatus.SUCCESS:
                return {
                    "status": "duplicate",
                    "reason": "already_successful",
                    "paymentId": str(payment.id),
                }

            wallet = await self._credit_wallet(
                owner_id=payment.user_id,
                owner_type=self.wallet_owner_type,
                amount=self._normalize_amount(payment.amount),
                reference_code=payment.reference_code,
                transaction_id=payment.provider_transaction_id or f"ADMIN-{payment.id}",
                description="Admin force verify credit",
            )

            payment.status = PaymentStatus.SUCCESS
            payment.wallet_id = wallet.id
            self._append_metadata(payment, {
                "force_verified_at": datetime.now(timezone.utc).isoformat(),
                "verified_by_admin": True,
                "wallet_id": str(wallet.id),
            })

            await self.db.commit()

            return {
                "status": "success",
                "paymentId": str(payment.id),
                "walletId": str(wallet.id),
                "walletBalance": str(wallet.balance),
            }

        except SQLAlchemyError as exc:
            await self.db.rollback()
            logger.exception("Force verify failed")
            raise exc

    # =========================================================
    # ADMIN: BLOCK PAYMENT
    # =========================================================
    async def block_payment(self, payment_id: UUID, reason: str) -> Dict[str, Any]:
        try:
            payment = await self._get_payment_by_id(payment_id)

            if not payment:
                return {
                    "status": "failed",
                    "reason": "payment_not_found",
                }

            payment.status = PaymentStatus.BLOCKED
            self._append_metadata(payment, {
                "blocked_at": datetime.now(timezone.utc).isoformat(),
                "block_reason": reason,
            })

            await self.db.commit()

            return {
                "status": "success",
                "paymentId": str(payment.id),
                "message": "Payment blocked",
            }

        except SQLAlchemyError as exc:
            await self.db.rollback()
            logger.exception("Block payment failed")
            raise exc

    # =========================================================
    # HELPERS
    # =========================================================
    def _generate_reference_code(self, length: int = 6) -> str:
        alphabet = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def _normalize_amount(self, value: Any) -> Decimal:
        try:
            amount = Decimal(str(value)).quantize(Decimal("0.01"))
            return amount
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("Invalid amount")

    def _extract_reference_code(self, sms_message: str) -> Optional[str]:
        if not sms_message:
            return None

        patterns = [
            r"Message from sender:\s*([A-Z0-9]{4,20})",
            r"(?:reason|reference|ref|code)\s*[:\-]\s*([A-Z0-9]{4,20})",
            r"\b([A-Z][A-Z0-9]{3,11})\b",
        ]

        text = sms_message.upper()

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                token = match.group(1).strip().upper()
                if token not in {"XAF", "MOMO", "MTN", "ORANGE", "SUCCESS", "FAILED"}:
                    return token

        return None

    def _extract_amount_from_sms(self, sms_message: str) -> Optional[Decimal]:
        if not sms_message:
            return None

        patterns = [
            r"received\s+([\d,]+(?:\.\d+)?)\s*XAF",
            r"amount\s*[:\-]\s*([\d,]+(?:\.\d+)?)",
            r"\b([\d,]+(?:\.\d+)?)\s*XAF\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, sms_message, flags=re.IGNORECASE)
            if match:
                raw = match.group(1).replace(",", "")
                try:
                    return Decimal(raw).quantize(Decimal("0.01"))
                except Exception:
                    continue

        return None

    def _build_payment(
        self,
        user_id: UUID,
        amount: Decimal,
        currency: str,
        phone: str,
        provider: str,
        reference_code: str,
        idempotency_key: Optional[str],
        payment_status: PaymentStatus,
        metadata: Dict[str, Any],
    ) -> Payment:
        """
        Build Payment with field-name fallback for mixed model versions.
        """

        common_kwargs = {
            "user_id": user_id,
            "amount": amount,
            "currency": currency,
            "phone_number": phone,
            "provider": provider,
            "status": payment_status,
            "reference_code": reference_code,
            "idempotency_key": idempotency_key,
            "metadata": metadata,
        }

        try:
            return Payment(
                payment_type="DEPOSIT",
                **common_kwargs,
            )
        except TypeError:
            return Payment(
                type="DEPOSIT",
                **common_kwargs,
            )

    async def _get_payment_by_idempotency(self, key: str) -> Optional[Payment]:
        stmt = select(Payment).where(Payment.idempotency_key == key)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_payment_for_update(
        self,
        user_id: UUID,
        reference_code: str,
    ) -> Optional[Payment]:
        stmt = (
            select(Payment)
            .where(
                Payment.user_id == user_id,
                Payment.reference_code == reference_code,
            )
            .with_for_update()
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_payment_by_id(
        self,
        payment_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[Payment]:
        stmt = select(Payment).where(Payment.id == payment_id)
        if user_id is not None:
            stmt = stmt.where(Payment.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _credit_wallet(
        self,
        owner_id: UUID,
        owner_type: str,
        amount: Decimal,
        reference_code: str,
        transaction_id: str,
        description: str,
    ) -> Wallet:
        owner_type = owner_type.upper().strip()

        wallet_stmt = (
            select(Wallet)
            .where(
                Wallet.owner_id == owner_id,
                Wallet.owner_type == owner_type,
            )
            .with_for_update()
        )
        result = await self.db.execute(wallet_stmt)
        wallet = result.scalar_one_or_none()

        if not wallet:
            wallet = Wallet(
                owner_id=owner_id,
                owner_type=owner_type,
                balance=Decimal("0.00"),
                currency="XAF",
                is_active=True,
                is_locked=False,
            )
            self.db.add(wallet)
            await self.db.flush()

        tx = WalletTransaction(
            wallet_id=wallet.id,
            type="CREDIT",
            amount=amount,
            reference_id=reference_code,
            description=description,
            status="completed",
            is_flagged=False,
        )

        self.db.add(tx)
        wallet.balance = (wallet.balance or Decimal("0.00")) + amount

        await self.db.flush()
        return wallet

    def _append_metadata(self, payment: Payment, extra: Dict[str, Any]) -> None:
        current = getattr(payment, "metadata", None)
        if not isinstance(current, dict):
            current = {}
        current.update(extra)
        setattr(payment, "metadata", current)

    def _serialize_payment(self, payment: Payment) -> Dict[str, Any]:
        return {
            "id": str(payment.id),
            "userId": str(payment.user_id),
            "walletId": str(payment.wallet_id) if getattr(payment, "wallet_id", None) else None,
            "amount": str(payment.amount),
            "currency": getattr(payment, "currency", "XAF"),
            "phoneNumber": getattr(payment, "phone_number", None),
            "provider": getattr(payment, "provider", None),
            "status": payment.status.value if hasattr(payment.status, "value") else str(payment.status),
            "referenceCode": getattr(payment, "reference_code", None),
            "transactionId": getattr(payment, "provider_transaction_id", None),
            "metadata": getattr(payment, "metadata", None),
            "createdAt": getattr(payment, "created_at", None),
            "updatedAt": getattr(payment, "updated_at", None),
        }