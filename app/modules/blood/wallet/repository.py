from __future__ import annotations

from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from .models import Wallet, WalletTransaction, WalletPayout, WalletBilling


class WalletRepository:
    """
    Production-grade Wallet Repository

    Responsibilities:
    -------------------------------------------------
    ✔ Safe DB access
    ✔ Row-level locking for balance updates
    ✔ Transaction persistence (ledger)
    ✔ Payout + billing handling
    ✔ No business logic here
    """

    # =========================================================
    # WALLET
    # =========================================================
    def get_wallet(
        self,
        db: Session,
        owner_id: UUID,
        owner_type: str,
    ) -> Optional[Wallet]:
        return db.query(Wallet).filter(
            Wallet.owner_id == owner_id,
            Wallet.owner_type == owner_type,
        ).first()

    def create_wallet(
        self,
        db: Session,
        wallet: Wallet,
    ) -> Wallet:
        db.add(wallet)
        db.flush()  # get ID immediately
        return wallet

    def get_or_create_wallet(
        self,
        db: Session,
        owner_id: UUID,
        owner_type: str,
    ) -> Wallet:
        wallet = self.get_wallet(db, owner_id, owner_type)

        if not wallet:
            wallet = Wallet(
                owner_id=owner_id,
                owner_type=owner_type,
            )
            wallet = self.create_wallet(db, wallet)

        return wallet

    # =========================================================
    # 🔒 LOCK WALLET (CRITICAL FOR MONEY SAFETY)
    # =========================================================
    def lock_wallet(
        self,
        db: Session,
        wallet_id: UUID,
    ) -> Optional[Wallet]:
        """
        SELECT ... FOR UPDATE
        Prevents race conditions (double spending)
        """
        stmt = (
            select(Wallet)
            .where(Wallet.id == wallet_id)
            .with_for_update()
        )

        result = db.execute(stmt).scalar_one_or_none()
        return result

    def update_balance(
        self,
        db: Session,
        wallet_id: UUID,
        amount_delta,
    ) -> Optional[Wallet]:
        """
        Safe balance update (after lock)
        """
        wallet = self.lock_wallet(db, wallet_id)

        if not wallet:
            return None

        wallet.balance = wallet.balance + amount_delta
        db.flush()

        return wallet

    # =========================================================
    # 💳 TRANSACTIONS (LEDGER)
    # =========================================================
    def create_transaction(
        self,
        db: Session,
        tx: WalletTransaction,
    ) -> WalletTransaction:
        db.add(tx)
        db.flush()
        return tx

    def list_transactions(
        self,
        db: Session,
        wallet_id: UUID,
        limit: int = 50,
    ) -> List[WalletTransaction]:
        return db.query(WalletTransaction).filter(
            WalletTransaction.wallet_id == wallet_id
        ).order_by(
            WalletTransaction.created_at.desc()
        ).limit(limit).all()

    # =========================================================
    # 💸 PAYOUTS
    # =========================================================
    def create_payout(
        self,
        db: Session,
        payout: WalletPayout,
    ) -> WalletPayout:
        db.add(payout)
        db.flush()
        return payout

    def get_payout(
        self,
        db: Session,
        payout_id: UUID,
    ) -> Optional[WalletPayout]:
        return db.query(WalletPayout).filter(
            WalletPayout.id == payout_id
        ).first()

    def update_payout_status(
        self,
        db: Session,
        payout_id: UUID,
        status: str,
    ) -> Optional[WalletPayout]:
        payout = self.get_payout(db, payout_id)

        if not payout:
            return None

        payout.status = status
        db.flush()
        return payout

    def list_payouts(
        self,
        db: Session,
        wallet_id: UUID,
    ) -> List[WalletPayout]:
        return db.query(WalletPayout).filter(
            WalletPayout.wallet_id == wallet_id
        ).order_by(
            WalletPayout.requested_at.desc()
        ).all()

    # =========================================================
    # 🏥 BILLING (HOSPITAL SIDE)
    # =========================================================
    def create_billing(
        self,
        db: Session,
        billing: WalletBilling,
    ) -> WalletBilling:
        db.add(billing)
        db.flush()
        return billing

    def list_billings(
        self,
        db: Session,
        hospital_id: UUID,
    ) -> List[WalletBilling]:
        return db.query(WalletBilling).filter(
            WalletBilling.hospital_id == hospital_id
        ).order_by(
            WalletBilling.created_at.desc()
        ).all()

    def update_billing_status(
        self,
        db: Session,
        billing_id: UUID,
        status: str,
    ) -> Optional[WalletBilling]:
        billing = db.query(WalletBilling).filter(
            WalletBilling.id == billing_id
        ).first()

        if not billing:
            return None

        billing.status = status
        db.flush()
        return billing