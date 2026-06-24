from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .models import Wallet, WalletTransaction, WalletPayout, WalletBilling
from .repository import WalletRepository

logger = logging.getLogger(__name__)


class WalletService:
    """
    Production-grade wallet service.

    Responsibilities:
    - donor and hospital wallet management
    - ledger-based credits/debits
    - payout requests and approval flow
    - hospital billing records
    - safe balance operations with locking
    - no business rules in repository
    """

    MIN_PAYOUT_AMOUNT = Decimal("1.00")
    MAX_SINGLE_CREDIT = Decimal("10000.00")
    MAX_SINGLE_DEBIT = Decimal("10000.00")

    def __init__(self) -> None:
        self.repo = WalletRepository()

    # =========================================================
    # INTERNAL HELPERS
    # =========================================================
    def _to_decimal(self, value: Any) -> Decimal:
        try:
            amount = Decimal(str(value)).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid amount",
            )
        return amount

    def _validate_positive_amount(self, amount: Decimal) -> None:
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount must be greater than zero",
            )

    def _validate_owner_type(self, owner_type: str) -> str:
        normalized = (owner_type or "").strip().upper()
        if normalized not in {"DONOR", "HOSPITAL"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="owner_type must be DONOR or HOSPITAL",
            )
        return normalized

    def _apply_ranked_flag(self, tx_type: str) -> bool:
        return tx_type in {"SURGE", "BONUS", "REFUND"}

    # =========================================================
    # WALLET CORE
    # =========================================================
    def get_or_create_wallet(
        self,
        db: Session,
        owner_id: UUID,
        owner_type: str,
        currency: str = "USD",
    ) -> Wallet:
        owner_type = self._validate_owner_type(owner_type)

        wallet = self.repo.get_wallet(db, owner_id, owner_type)
        if wallet:
            return wallet

        wallet = Wallet(
            owner_id=owner_id,
            owner_type=owner_type,
            currency=(currency or "USD").upper().strip(),
            balance=Decimal("0.00"),
            is_active=True,
            is_locked=False,
        )
        wallet = self.repo.create_wallet(db, wallet)
        db.commit()
        db.refresh(wallet)
        return wallet

    def get_wallet(
        self,
        db: Session,
        owner_id: UUID,
        owner_type: str,
    ) -> Optional[Wallet]:
        owner_type = self._validate_owner_type(owner_type)
        return self.repo.get_wallet(db, owner_id, owner_type)

    def get_wallet_summary(
        self,
        db: Session,
        owner_id: UUID,
        owner_type: str,
    ) -> Dict[str, Any]:
        wallet = self.get_or_create_wallet(db, owner_id, owner_type)

        transactions = self.repo.list_transactions(db, wallet.id, limit=20)
        payouts = self.repo.list_payouts(db, wallet.id)

        return {
            "walletId": str(wallet.id),
            "ownerId": str(wallet.owner_id),
            "ownerType": wallet.owner_type,
            "balance": str(wallet.balance),
            "currency": wallet.currency,
            "isActive": wallet.is_active,
            "isLocked": wallet.is_locked,
            "transactions": [
                {
                    "id": str(tx.id),
                    "type": tx.type,
                    "amount": str(tx.amount),
                    "referenceId": tx.reference_id,
                    "description": tx.description,
                    "status": tx.status,
                    "isFlagged": tx.is_flagged,
                    "createdAt": tx.created_at,
                }
                for tx in transactions
            ],
            "payouts": [
                {
                    "id": str(p.id),
                    "amount": str(p.amount),
                    "method": p.method,
                    "accountNumber": p.account_number,
                    "accountName": p.account_name,
                    "status": p.status,
                    "requestedAt": p.requested_at,
                    "processedAt": p.processed_at,
                    "isFlagged": p.is_flagged,
                }
                for p in payouts
            ],
        }

    # =========================================================
    # CREDIT
    # =========================================================
    def credit_wallet(
        self,
        db: Session,
        owner_id: UUID,
        owner_type: str,
        amount: Any,
        reference_id: Optional[str] = None,
        description: Optional[str] = None,
        tx_type: str = "CREDIT",
    ) -> Dict[str, Any]:
        owner_type = self._validate_owner_type(owner_type)
        amount_dec = self._to_decimal(amount)
        self._validate_positive_amount(amount_dec)

        if amount_dec > self.MAX_SINGLE_CREDIT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Credit amount exceeds maximum allowed",
            )

        wallet = self.get_or_create_wallet(db, owner_id, owner_type)

        try:
            wallet = self.repo.lock_wallet(db, wallet.id)
            if not wallet:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Wallet not found",
                )

            if not wallet.is_active or wallet.is_locked:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Wallet is not available",
                )

            tx = WalletTransaction(
                wallet_id=wallet.id,
                type=tx_type,
                amount=amount_dec,
                reference_id=reference_id,
                description=description or "Wallet credit",
                status="completed",
                is_flagged=self._apply_ranked_flag(tx_type),
            )

            self.repo.create_transaction(db, tx)
            wallet.balance = (wallet.balance or Decimal("0.00")) + amount_dec

            db.commit()
            db.refresh(wallet)
            db.refresh(tx)

            return {
                "status": "success",
                "walletId": str(wallet.id),
                "balance": str(wallet.balance),
                "transactionId": str(tx.id),
                "credited": str(amount_dec),
            }

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.exception("Credit failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Credit failed: {str(e)}",
            )

    # =========================================================
    # DEBIT
    # =========================================================
    def debit_wallet(
        self,
        db: Session,
        owner_id: UUID,
        owner_type: str,
        amount: Any,
        reference_id: Optional[str] = None,
        description: Optional[str] = None,
        tx_type: str = "DEBIT",
    ) -> Dict[str, Any]:
        owner_type = self._validate_owner_type(owner_type)
        amount_dec = self._to_decimal(amount)
        self._validate_positive_amount(amount_dec)

        if amount_dec > self.MAX_SINGLE_DEBIT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debit amount exceeds maximum allowed",
            )

        wallet = self.get_or_create_wallet(db, owner_id, owner_type)

        try:
            wallet = self.repo.lock_wallet(db, wallet.id)
            if not wallet:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Wallet not found",
                )

            if not wallet.is_active or wallet.is_locked:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Wallet is not available",
                )

            current_balance = wallet.balance or Decimal("0.00")
            if current_balance < amount_dec:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Insufficient wallet balance",
                )

            tx = WalletTransaction(
                wallet_id=wallet.id,
                type=tx_type,
                amount=amount_dec,
                reference_id=reference_id,
                description=description or "Wallet debit",
                status="completed",
                is_flagged=self._apply_ranked_flag(tx_type),
            )

            self.repo.create_transaction(db, tx)
            wallet.balance = current_balance - amount_dec

            db.commit()
            db.refresh(wallet)
            db.refresh(tx)

            return {
                "status": "success",
                "walletId": str(wallet.id),
                "balance": str(wallet.balance),
                "transactionId": str(tx.id),
                "debited": str(amount_dec),
            }

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.exception("Debit failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Debit failed: {str(e)}",
            )

    # =========================================================
    # SURGE / BONUS CREDIT
    # =========================================================
    def credit_surge_bonus(
        self,
        db: Session,
        owner_id: UUID,
        owner_type: str,
        amount: Any,
        reference_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.credit_wallet(
            db=db,
            owner_id=owner_id,
            owner_type=owner_type,
            amount=amount,
            reference_id=reference_id,
            description=description or "Emergency surge bonus",
            tx_type="SURGE",
        )

    # =========================================================
    # REFERRAL / BONUS CREDIT
    # =========================================================
    def credit_bonus(
        self,
        db: Session,
        owner_id: UUID,
        owner_type: str,
        amount: Any,
        reference_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.credit_wallet(
            db=db,
            owner_id=owner_id,
            owner_type=owner_type,
            amount=amount,
            reference_id=reference_id,
            description=description or "Bonus credit",
            tx_type="BONUS",
        )

    # =========================================================
    # REFUND
    # =========================================================
    def refund_wallet(
        self,
        db: Session,
        owner_id: UUID,
        owner_type: str,
        amount: Any,
        reference_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.credit_wallet(
            db=db,
            owner_id=owner_id,
            owner_type=owner_type,
            amount=amount,
            reference_id=reference_id,
            description=description or "Refund",
            tx_type="REFUND",
        )

    # =========================================================
    # PAYOUT REQUEST
    # =========================================================
    def request_payout(
        self,
        db: Session,
        owner_id: UUID,
        owner_type: str,
        amount: Any,
        method: str,
        account_number: str,
        account_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        owner_type = self._validate_owner_type(owner_type)
        amount_dec = self._to_decimal(amount)
        self._validate_positive_amount(amount_dec)

        if amount_dec < self.MIN_PAYOUT_AMOUNT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Minimum payout amount is {self.MIN_PAYOUT_AMOUNT}",
            )

        wallet = self.get_or_create_wallet(db, owner_id, owner_type)

        try:
            wallet = self.repo.lock_wallet(db, wallet.id)
            if not wallet:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Wallet not found",
                )

            if not wallet.is_active or wallet.is_locked:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Wallet is not available",
                )

            current_balance = wallet.balance or Decimal("0.00")
            if current_balance < amount_dec:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Insufficient balance for payout",
                )

            wallet.balance = current_balance - amount_dec
            wallet.is_locked = True

            payout = WalletPayout(
                wallet_id=wallet.id,
                amount=amount_dec,
                method=method.strip().upper(),
                account_number=account_number.strip(),
                account_name=account_name.strip() if account_name else None,
                status="pending",
                is_flagged=False,
            )

            tx = WalletTransaction(
                wallet_id=wallet.id,
                type="WITHDRAWAL",
                amount=amount_dec,
                reference_id=None,
                description="Payout request",
                status="completed",
                is_flagged=False,
            )

            self.repo.create_payout(db, payout)
            self.repo.create_transaction(db, tx)

            db.commit()
            db.refresh(wallet)
            db.refresh(payout)
            db.refresh(tx)

            return {
                "status": "pending",
                "walletId": str(wallet.id),
                "payoutId": str(payout.id),
                "amount": str(amount_dec),
                "method": payout.method,
            }

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.exception("Payout request failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Payout request failed: {str(e)}",
            )

    # =========================================================
    # APPROVE PAYOUT
    # =========================================================
    def approve_payout(
        self,
        db: Session,
        payout_id: UUID,
        processed_by: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        try:
            payout = self.repo.get_payout(db, payout_id)
            if not payout:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payout not found",
                )

            wallet = self.repo.lock_wallet(db, payout.wallet_id)
            if not wallet:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Wallet not found",
                )

            payout.status = "paid"
            payout.processed_by = processed_by
            payout.processed_at = datetime.utcnow()
            wallet.is_locked = False

            db.commit()
            db.refresh(payout)
            db.refresh(wallet)

            return {
                "status": "paid",
                "payoutId": str(payout.id),
                "walletId": str(wallet.id),
            }

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.exception("Approve payout failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Approve payout failed: {str(e)}",
            )

    # =========================================================
    # REJECT PAYOUT
    # =========================================================
    def reject_payout(
        self,
        db: Session,
        payout_id: UUID,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            payout = self.repo.get_payout(db, payout_id)
            if not payout:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payout not found",
                )

            wallet = self.repo.lock_wallet(db, payout.wallet_id)
            if not wallet:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Wallet not found",
                )

            payout.status = "rejected"
            payout.processed_at = datetime.utcnow()
            wallet.balance = (wallet.balance or Decimal("0.00")) + payout.amount
            wallet.is_locked = False

            tx = WalletTransaction(
                wallet_id=wallet.id,
                type="REFUND",
                amount=payout.amount,
                reference_id=str(payout.id),
                description=reason or "Rejected payout refund",
                status="completed",
                is_flagged=False,
            )
            self.repo.create_transaction(db, tx)

            db.commit()
            db.refresh(payout)
            db.refresh(wallet)
            db.refresh(tx)

            return {
                "status": "rejected",
                "payoutId": str(payout.id),
                "walletId": str(wallet.id),
                "refunded": str(payout.amount),
            }

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.exception("Reject payout failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Reject payout failed: {str(e)}",
            )

    # =========================================================
    # BILLING (HOSPITAL SIDE)
    # =========================================================
    def create_billing(
        self,
        db: Session,
        hospital_id: UUID,
        amount: Any,
        billing_type: str,
        reference_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        amount_dec = self._to_decimal(amount)
        self._validate_positive_amount(amount_dec)

        try:
            billing = WalletBilling(
                hospital_id=hospital_id,
                amount=amount_dec,
                type=billing_type.strip().upper(),
                reference_id=reference_id,
                status="pending",
            )
            self.repo.create_billing(db, billing)
            db.commit()
            db.refresh(billing)

            return {
                "status": "pending",
                "billingId": str(billing.id),
                "hospitalId": str(billing.hospital_id),
                "amount": str(billing.amount),
                "type": billing.type,
            }

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.exception("Billing creation failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Billing creation failed: {str(e)}",
            )

    def mark_billing_paid(
        self,
        db: Session,
        billing_id: UUID,
    ) -> Dict[str, Any]:
        try:
            billing = db.query(WalletBilling).filter(WalletBilling.id == billing_id).first()
            if not billing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Billing record not found",
                )

            billing.status = "paid"
            billing.paid_at = datetime.utcnow()

            db.commit()
            db.refresh(billing)

            return {
                "status": "paid",
                "billingId": str(billing.id),
                "hospitalId": str(billing.hospital_id),
            }

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.exception("Mark billing paid failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Mark billing paid failed: {str(e)}",
            )

    # =========================================================
    # HISTORY
    # =========================================================
    def list_transactions(
        self,
        db: Session,
        owner_id: UUID,
        owner_type: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        wallet = self.get_or_create_wallet(db, owner_id, owner_type)
        txs = self.repo.list_transactions(db, wallet.id, limit=limit)

        return [
            {
                "id": str(tx.id),
                "walletId": str(tx.wallet_id),
                "type": tx.type,
                "amount": str(tx.amount),
                "referenceId": tx.reference_id,
                "description": tx.description,
                "status": tx.status,
                "isFlagged": tx.is_flagged,
                "createdAt": tx.created_at,
            }
            for tx in txs
        ]

    def list_payouts(
        self,
        db: Session,
        owner_id: UUID,
        owner_type: str,
    ) -> List[Dict[str, Any]]:
        wallet = self.get_or_create_wallet(db, owner_id, owner_type)
        payouts = self.repo.list_payouts(db, wallet.id)

        return [
            {
                "id": str(p.id),
                "walletId": str(p.wallet_id),
                "amount": str(p.amount),
                "method": p.method,
                "accountNumber": p.account_number,
                "accountName": p.account_name,
                "status": p.status,
                "requestedAt": p.requested_at,
                "processedAt": p.processed_at,
                "isFlagged": p.is_flagged,
            }
            for p in payouts
        ]

    def list_billings(
        self,
        db: Session,
        hospital_id: UUID,
    ) -> List[Dict[str, Any]]:
        items = self.repo.list_billings(db, hospital_id)

        return [
            {
                "id": str(b.id),
                "hospitalId": str(b.hospital_id),
                "amount": str(b.amount),
                "type": b.type,
                "referenceId": b.reference_id,
                "status": b.status,
                "createdAt": b.created_at,
                "paidAt": b.paid_at,
            }
            for b in items
        ]