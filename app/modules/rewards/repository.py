# G:\pycharm\bloodonal-api\app\modules\rewards\repository.py

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import RewardTransaction, DonorRewardProfile, RewardCatalog

logger = logging.getLogger(__name__)


class RewardRepository:
    """
    Enterprise-grade reward repository.

    Rules:
    - Async-only persistence API
    - Caller owns commit / rollback
    - No silent mutation
    - Strong audit trail
    - No business scoring inside repository
    """

    # =========================================================
    # TRANSACTIONS
    # =========================================================
    async def create_transaction(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        wallet_id: UUID,
        reference: str,
        reason: str,
        base_amount: Decimal,
        reward_points: int,
        wallet_credit: Decimal,
        status: str = "pending",
        message: Optional[str] = None,
        payment_reference: Optional[str] = None,
        reward_label: Optional[str] = None,
        surge_multiplier: float = 1.0,
        risk_score: float = 0.0,
        fraud_flags: Optional[List[str]] = None,
        is_fraud_blocked: bool = False,
        reward_context: Optional[Dict[str, Any]] = None,
        worker_meta: Optional[Dict[str, Any]] = None,
        donor_rank: Optional[str] = None,
        streak_count: int = 0,
        badges_awarded: Optional[List[str]] = None,
        referral_code: Optional[str] = None,
        referral_bonus_points: int = 0,
        referred_user_id: Optional[UUID] = None,
        processed_at: Optional[datetime] = None,
    ) -> RewardTransaction:
        """
        Create a reward transaction row.

        Caller decides whether to commit.
        """
        self._require_text(reference, "reference")
        self._require_text(reason, "reason")
        self._require_uuid(user_id, "user_id")
        self._require_uuid(wallet_id, "wallet_id")

        tx = RewardTransaction(
            id=uuid4(),
            user_id=user_id,
            wallet_id=wallet_id,
            reference=reference.strip(),
            reason=reason.strip(),
            base_amount=self._to_decimal(base_amount),
            reward_points=int(reward_points),
            wallet_credit=self._to_decimal(wallet_credit),
            status=status.strip(),
            message=message.strip() if isinstance(message, str) and message.strip() else message,
            payment_reference=payment_reference.strip() if isinstance(payment_reference, str) and payment_reference.strip() else payment_reference,
            reward_label=reward_label.strip() if isinstance(reward_label, str) and reward_label.strip() else reward_label,
            surge_multiplier=float(surge_multiplier),
            risk_score=float(risk_score),
            fraud_flags=self._normalize_string_list(fraud_flags),
            is_fraud_blocked=bool(is_fraud_blocked),
            reward_context=self._normalize_json(reward_context),
            worker_meta=self._normalize_json(worker_meta),
            donor_rank=donor_rank.strip() if isinstance(donor_rank, str) and donor_rank.strip() else donor_rank,
            streak_count=max(int(streak_count), 0),
            badges_awarded=self._normalize_string_list(badges_awarded),
            referral_code=referral_code.strip() if isinstance(referral_code, str) and referral_code.strip() else referral_code,
            referral_bonus_points=max(int(referral_bonus_points), 0),
            referred_user_id=referred_user_id,
            processed_at=processed_at,
        )

        db.add(tx)
        await db.flush()
        return tx

    async def get_transaction_by_id(
        self,
        db: AsyncSession,
        transaction_id: UUID,
    ) -> Optional[RewardTransaction]:
        self._require_uuid(transaction_id, "transaction_id")
        result = await db.execute(
            select(RewardTransaction).where(RewardTransaction.id == transaction_id)
        )
        return result.scalar_one_or_none()

    async def get_transaction_by_reference(
        self,
        db: AsyncSession,
        reference: str,
    ) -> Optional[RewardTransaction]:
        self._require_text(reference, "reference")
        result = await db.execute(
            select(RewardTransaction).where(RewardTransaction.reference == reference.strip())
        )
        return result.scalar_one_or_none()

    async def list_user_transactions(
        self,
        db: AsyncSession,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> List[RewardTransaction]:
        self._require_uuid(user_id, "user_id")
        limit = self._require_positive_int(limit, "limit")
        offset = max(int(offset), 0)

        result = await db.execute(
            select(RewardTransaction)
            .where(RewardTransaction.user_id == user_id)
            .order_by(RewardTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update_transaction_status(
        self,
        db: AsyncSession,
        transaction: RewardTransaction,
        *,
        status: str,
        message: Optional[str] = None,
        risk_score: Optional[float] = None,
        fraud_flags: Optional[List[str]] = None,
        processed_at: Optional[datetime] = None,
        worker_meta: Optional[Dict[str, Any]] = None,
    ) -> RewardTransaction:
        self._ensure_transaction(transaction)

        transaction.status = status.strip()
        if message is not None:
            transaction.message = message
        if risk_score is not None:
            transaction.risk_score = float(risk_score)
        if fraud_flags is not None:
            transaction.fraud_flags = self._normalize_string_list(fraud_flags)
        if worker_meta is not None:
            transaction.worker_meta = self._normalize_json(worker_meta)
        if processed_at is not None:
            transaction.processed_at = processed_at
        else:
            transaction.processed_at = datetime.now(timezone.utc)

        await db.flush()
        return transaction

    async def mark_transaction_processed(
        self,
        db: AsyncSession,
        reference: str,
        *,
        status: str = "success",
        message: Optional[str] = None,
        worker_meta: Optional[Dict[str, Any]] = None,
    ) -> Optional[RewardTransaction]:
        tx = await self.get_transaction_by_reference(db, reference)
        if tx is None:
            return None

        return await self.update_transaction_status(
            db,
            tx,
            status=status,
            message=message,
            worker_meta=worker_meta,
            processed_at=datetime.now(timezone.utc),
        )

    async def mark_transaction_blocked(
        self,
        db: AsyncSession,
        reference: str,
        *,
        risk_score: float = 0.0,
        fraud_flags: Optional[List[str]] = None,
        message: str = "Blocked by fraud detection",
    ) -> Optional[RewardTransaction]:
        tx = await self.get_transaction_by_reference(db, reference)
        if tx is None:
            return None

        return await self.update_transaction_status(
            db,
            tx,
            status="blocked",
            message=message,
            risk_score=risk_score,
            fraud_flags=fraud_flags,
            processed_at=datetime.now(timezone.utc),
        )

    # =========================================================
    # ANALYTICS
    # =========================================================
    async def get_reward_analytics(
        self,
        db: AsyncSession,
        *,
        user_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Returns a DTO-ready analytics payload.

        This is intentionally dict-based so it can be shaped into
        RewardAnalyticsSchema or directly returned from a service layer.
        """
        query = select(
            func.count(RewardTransaction.id),
            func.coalesce(func.sum(RewardTransaction.wallet_credit), 0),
            func.coalesce(func.avg(RewardTransaction.wallet_credit), 0),
            func.coalesce(func.sum(func.cast(RewardTransaction.status == "success", func.integer())), 0),
            func.coalesce(func.avg(RewardTransaction.surge_multiplier), 1.0),
        )

        if user_id is not None:
            self._require_uuid(user_id, "user_id")
            query = query.where(RewardTransaction.user_id == user_id)

        result = await db.execute(query)
        total_rewards, total_credits, avg_reward, success_count, avg_surge = result.one()

        total_rewards_int = int(total_rewards or 0)
        success_count_int = int(success_count or 0)
        success_rate = round((success_count_int / total_rewards_int) * 100, 2) if total_rewards_int > 0 else 0.0

        return {
            "user_id": str(user_id) if user_id is not None else None,
            "total_rewards": total_rewards_int,
            "total_credits": self._to_decimal(total_credits),
            "avg_reward": self._to_decimal(avg_reward),
            "success_rate": float(success_rate),
            "surge_multiplier": float(avg_surge or 1.0),
            "last_updated": datetime.now(timezone.utc),
        }

    async def count_user_rewards(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> int:
        self._require_uuid(user_id, "user_id")
        result = await db.execute(
            select(func.count(RewardTransaction.id)).where(RewardTransaction.user_id == user_id)
        )
        return int(result.scalar_one() or 0)

    async def sum_user_credits(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> Decimal:
        self._require_uuid(user_id, "user_id")
        result = await db.execute(
            select(func.coalesce(func.sum(RewardTransaction.wallet_credit), 0)).where(
                RewardTransaction.user_id == user_id
            )
        )
        return self._to_decimal(result.scalar_one())

    # =========================================================
    # DONOR REWARD PROFILE
    # =========================================================
    async def get_reward_profile(
        self,
        db: AsyncSession,
        donor_id: UUID,
    ) -> Optional[DonorRewardProfile]:
        self._require_uuid(donor_id, "donor_id")
        result = await db.execute(
            select(DonorRewardProfile).where(DonorRewardProfile.donor_id == donor_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create_reward_profile(
        self,
        db: AsyncSession,
        donor_id: UUID,
        *,
        referral_code: Optional[str] = None,
    ) -> DonorRewardProfile:
        self._require_uuid(donor_id, "donor_id")
        existing = await self.get_reward_profile(db, donor_id)
        if existing is not None:
            return existing

        profile = DonorRewardProfile(
            id=uuid4(),
            donor_id=donor_id,
            total_points=0,
            total_rewards=0,
            total_wallet_credit=Decimal("0"),
            current_rank="Bronze",
            next_rank="Silver",
            next_rank_points=1000,
            streak_count=0,
            highest_streak=0,
            badges=[],
            referral_code=referral_code.strip() if isinstance(referral_code, str) and referral_code.strip() else None,
            total_referrals=0,
            successful_referrals=0,
            referral_bonus_points=0,
        )

        db.add(profile)
        await db.flush()
        return profile

    async def update_reward_profile(
        self,
        db: AsyncSession,
        donor_id: UUID,
        *,
        points_delta: int = 0,
        rewards_delta: int = 0,
        wallet_credit_delta: Decimal | int | float = 0,
        rank: Optional[str] = None,
        next_rank: Optional[str] = None,
        next_rank_points: Optional[int] = None,
        streak_delta: int = 0,
        badge: Optional[str] = None,
        referral_bonus_points_delta: int = 0,
        total_referrals_delta: int = 0,
        successful_referrals_delta: int = 0,
    ) -> DonorRewardProfile:
        profile = await self.get_or_create_reward_profile(db, donor_id)

        profile.total_points = max(int(profile.total_points or 0) + int(points_delta), 0)
        profile.total_rewards = max(int(profile.total_rewards or 0) + int(rewards_delta), 0)
        profile.total_wallet_credit = self._to_decimal(profile.total_wallet_credit) + self._to_decimal(wallet_credit_delta)

        if rank is not None:
            profile.current_rank = rank
        if next_rank is not None:
            profile.next_rank = next_rank
        if next_rank_points is not None:
            profile.next_rank_points = max(int(next_rank_points), 0)

        profile.streak_count = max(int(profile.streak_count or 0) + int(streak_delta), 0)
        profile.highest_streak = max(int(profile.highest_streak or 0), profile.streak_count)

        profile.referral_bonus_points = max(
            int(profile.referral_bonus_points or 0) + int(referral_bonus_points_delta),
            0,
        )
        profile.total_referrals = max(
            int(profile.total_referrals or 0) + int(total_referrals_delta),
            0,
        )
        profile.successful_referrals = max(
            int(profile.successful_referrals or 0) + int(successful_referrals_delta),
            0,
        )

        if badge:
            existing_badges = self._normalize_string_list(profile.badges)
            if badge not in existing_badges:
                existing_badges.append(badge)
                profile.badges = existing_badges

        await db.flush()
        return profile

    async def award_from_transaction(
        self,
        db: AsyncSession,
        *,
        donor_id: UUID,
        reward_points: int,
        wallet_credit: Decimal | int | float,
        rank: Optional[str] = None,
        badge: Optional[str] = None,
        referral_bonus_points: int = 0,
    ) -> DonorRewardProfile:
        """
        Convenience method for updating donor gamification state after
        a successful reward transaction.
        """
        profile = await self.update_reward_profile(
            db,
            donor_id,
            points_delta=reward_points,
            rewards_delta=1,
            wallet_credit_delta=wallet_credit,
            rank=rank,
            badge=badge,
            referral_bonus_points_delta=referral_bonus_points,
        )
        return profile

    # =========================================================
    # REFERRALS
    # =========================================================
    async def find_profile_by_referral_code(
        self,
        db: AsyncSession,
        referral_code: str,
    ) -> Optional[DonorRewardProfile]:
        self._require_text(referral_code, "referral_code")
        result = await db.execute(
            select(DonorRewardProfile).where(DonorRewardProfile.referral_code == referral_code.strip())
        )
        return result.scalar_one_or_none()

    async def increment_referral_metrics(
        self,
        db: AsyncSession,
        donor_id: UUID,
        *,
        successful: bool = True,
        referral_bonus_points: int = 0,
    ) -> DonorRewardProfile:
        profile = await self.get_or_create_reward_profile(db, donor_id)
        profile.total_referrals = int(profile.total_referrals or 0) + 1
        if successful:
            profile.successful_referrals = int(profile.successful_referrals or 0) + 1
        profile.referral_bonus_points = int(profile.referral_bonus_points or 0) + max(int(referral_bonus_points), 0)
        await db.flush()
        return profile

    # =========================================================
    # CATALOG
    # =========================================================
    async def list_active_catalog(
        self,
        db: AsyncSession,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RewardCatalog]:
        limit = self._require_positive_int(limit, "limit")
        offset = max(int(offset), 0)

        result = await db.execute(
            select(RewardCatalog)
            .where(RewardCatalog.is_active.is_(True))
            .order_by(RewardCatalog.points_required.asc(), RewardCatalog.title.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_catalog_item(
        self,
        db: AsyncSession,
        catalog_id: UUID,
    ) -> Optional[RewardCatalog]:
        self._require_uuid(catalog_id, "catalog_id")
        result = await db.execute(
            select(RewardCatalog).where(RewardCatalog.id == catalog_id)
        )
        return result.scalar_one_or_none()

    async def get_catalog_item_by_title(
        self,
        db: AsyncSession,
        title: str,
    ) -> Optional[RewardCatalog]:
        self._require_text(title, "title")
        result = await db.execute(
            select(RewardCatalog).where(RewardCatalog.title == title.strip())
        )
        return result.scalar_one_or_none()

    async def upsert_catalog_item(
        self,
        db: AsyncSession,
        *,
        title: str,
        description: Optional[str] = None,
        points_required: int,
        reward_type: str = "voucher",
        reward_value: Decimal | int | float = 0,
        stock_quantity: int = 0,
        is_active: bool = True,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> RewardCatalog:
        existing = await self.get_catalog_item_by_title(db, title)
        if existing is None:
            item = RewardCatalog(
                id=uuid4(),
                title=title.strip(),
                description=description,
                points_required=int(points_required),
                reward_type=reward_type.strip(),
                reward_value=self._to_decimal(reward_value),
                stock_quantity=max(int(stock_quantity), 0),
                is_active=bool(is_active),
                metadata_json=self._normalize_json(metadata_json),
            )
            db.add(item)
            await db.flush()
            return item

        existing.description = description
        existing.points_required = int(points_required)
        existing.reward_type = reward_type.strip()
        existing.reward_value = self._to_decimal(reward_value)
        existing.stock_quantity = max(int(stock_quantity), 0)
        existing.is_active = bool(is_active)
        existing.metadata_json = self._normalize_json(metadata_json)
        await db.flush()
        return existing

    # =========================================================
    # SERIALIZATION HELPERS
    # =========================================================
    def transaction_to_dict(self, tx: RewardTransaction) -> Dict[str, Any]:
        self._ensure_transaction(tx)

        return {
            "id": str(tx.id),
            "user_id": str(tx.user_id),
            "wallet_id": str(tx.wallet_id),
            "reference": tx.reference,
            "payment_reference": tx.payment_reference,
            "reason": tx.reason,
            "base_amount": str(tx.base_amount),
            "reward_points": int(tx.reward_points),
            "wallet_credit": str(tx.wallet_credit),
            "status": tx.status,
            "message": tx.message,
            "reward_label": tx.reward_label,
            "surge_multiplier": float(tx.surge_multiplier),
            "risk_score": float(tx.risk_score),
            "fraud_flags": self._normalize_string_list(tx.fraud_flags),
            "is_fraud_blocked": bool(tx.is_fraud_blocked),
            "reward_context": tx.reward_context,
            "worker_meta": tx.worker_meta,
            "donor_rank": tx.donor_rank,
            "streak_count": int(tx.streak_count),
            "badges_awarded": self._normalize_string_list(tx.badges_awarded),
            "referral_code": tx.referral_code,
            "referral_bonus_points": int(tx.referral_bonus_points),
            "referred_user_id": str(tx.referred_user_id) if tx.referred_user_id else None,
            "created_at": tx.created_at,
            "updated_at": tx.updated_at,
            "processed_at": tx.processed_at,
        }

    def profile_to_dict(self, profile: DonorRewardProfile) -> Dict[str, Any]:
        return {
            "id": str(profile.id),
            "donor_id": str(profile.donor_id),
            "total_points": int(profile.total_points),
            "total_rewards": int(profile.total_rewards),
            "total_wallet_credit": str(profile.total_wallet_credit),
            "current_rank": profile.current_rank,
            "next_rank": profile.next_rank,
            "next_rank_points": int(profile.next_rank_points),
            "streak_count": int(profile.streak_count),
            "highest_streak": int(profile.highest_streak),
            "badges": self._normalize_string_list(profile.badges),
            "referral_code": profile.referral_code,
            "total_referrals": int(profile.total_referrals),
            "successful_referrals": int(profile.successful_referrals),
            "referral_bonus_points": int(profile.referral_bonus_points),
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        }

    # =========================================================
    # INTERNALS
    # =========================================================
    def _ensure_transaction(self, transaction: RewardTransaction) -> None:
        if transaction is None:
            raise ValueError("transaction is required")

    def _require_uuid(self, value: Any, field: str) -> None:
        if value is None:
            raise ValueError(f"{field} is required")
        if not isinstance(value, UUID):
            raise ValueError(f"{field} must be a UUID")

    def _require_text(self, value: Any, field: str) -> None:
        if value is None:
            raise ValueError(f"{field} is required")
        text = str(value).strip()
        if not text:
            raise ValueError(f"{field} cannot be empty")

    def _require_positive_int(self, value: Any, field: str) -> int:
        try:
            number = int(value)
        except Exception as exc:
            raise ValueError(f"{field} must be an integer") from exc

        if number <= 0:
            raise ValueError(f"{field} must be greater than zero")
        return number

    def _to_decimal(self, value: Any) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    def _normalize_string_list(self, value: Any) -> List[str]:
        if not value:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        return [str(value)]

    def _normalize_json(self, value: Any) -> Optional[Dict[str, Any]]:
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        if hasattr(value, "__dict__"):
            try:
                return dict(asdict(value))
            except Exception:
                return dict(value.__dict__)
        return None