from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.modules.blood.domain.ai.reward_optimizer import RewardOptimizer
from app.modules.blood.security.fraud_detection import FraudDetector
from app.modules.blood.wallet.repository import WalletRepository
from app.modules.blood.wallet.models import WalletTransaction

logger = logging.getLogger(__name__)


# =========================================================
# 📦 PAYOUT JOB PAYLOAD
# =========================================================
@dataclass
class RewardJob:
    user_id: UUID
    wallet_id: UUID
    amount: Decimal
    reason: str
    reference: str   # 🔑 CRITICAL: idempotency key
    meta: Optional[Dict[str, Any]] = None


# =========================================================
# 💰 REWARD WORKER (ASYNC ENGINE)
# =========================================================
class RewardWorker:
    """
    Production-grade async payout engine

    Guarantees:
    -------------------------------------------------
    ✔ Idempotent payouts (no duplicates)
    ✔ Fraud protection layer
    ✔ AI reward optimization
    ✔ ACID-safe wallet updates
    ✔ Ledger-first accounting (no silent balance edits)
    ✔ Retry-safe execution
    ✔ Full audit traceability
    """

    def __init__(
        self,
        db: AsyncSession,
        wallet_repo: WalletRepository,
        fraud_detector: FraudDetector,
        reward_optimizer: RewardOptimizer,
    ):
        self.db = db
        self.wallet_repo = wallet_repo
        self.fraud_detector = fraud_detector
        self.reward_optimizer = reward_optimizer

    # =========================================================
    # 🔍 IDEMPOTENCY CHECK
    # =========================================================
    async def _already_processed(self, reference: str) -> Optional[WalletTransaction]:
        return await self.wallet_repo.get_transaction_by_reference(
            self.db,
            reference,
        )

    # =========================================================
    # 🚀 MAIN PROCESS
    # =========================================================
    async def process_reward(self, job: RewardJob) -> Dict[str, Any]:
        logger.info(f"💰 Reward job started: {job.reference}")

        try:
            # -------------------------------------------------
            # 1. IDEMPOTENCY (CRITICAL)
            # -------------------------------------------------
            existing_tx = await self._already_processed(job.reference)

            if existing_tx:
                logger.warning(f"⚠️ Duplicate payout blocked: {job.reference}")

                return {
                    "status": "duplicate",
                    "reference": job.reference,
                    "transaction_id": str(existing_tx.id),
                }

            # -------------------------------------------------
            # 2. FRAUD CHECK
            # -------------------------------------------------
            fraud_result = await self.fraud_detector.check(
                user_id=str(job.user_id),
                amount=job.amount,
                reference=job.reference,
            )

            if fraud_result:
                logger.warning(f"🚨 Fraud detected: {job.reference}")

                return {
                    "status": "blocked",
                    "reason": "fraud_detected",
                    "reference": job.reference,
                }

            # -------------------------------------------------
            # 3. AI REWARD ADJUSTMENT
            # -------------------------------------------------
            adjusted_amount = await self.reward_optimizer.adjust_reward(
                user_id=str(job.user_id),
                base_amount=job.amount,
                context=job.meta or {},
            )

            adjusted_amount = Decimal(adjusted_amount)

            # -------------------------------------------------
            # 4. LOCK WALLET (ROW LOCK)
            # -------------------------------------------------
            wallet = await self.wallet_repo.get_wallet_for_update(
                self.db,
                job.wallet_id,
            )

            if not wallet:
                return {
                    "status": "failed",
                    "reason": "wallet_not_found",
                    "reference": job.reference,
                }

            if not wallet.is_active or wallet.is_locked:
                return {
                    "status": "failed",
                    "reason": "wallet_locked",
                    "reference": job.reference,
                }

            # -------------------------------------------------
            # 5. BALANCE CHECK
            # -------------------------------------------------
            if wallet.balance < adjusted_amount:
                return {
                    "status": "failed",
                    "reason": "insufficient_funds",
                    "reference": job.reference,
                }

            # -------------------------------------------------
            # 6. LEDGER-FIRST TRANSACTION
            # -------------------------------------------------
            tx = WalletTransaction(
                wallet_id=wallet.id,
                amount=-adjusted_amount,  # 🔴 debit
                type="REWARD_PAYOUT",
                status="SUCCESS",
                reference=job.reference,
                metadata={
                    "user_id": str(job.user_id),
                    "reason": job.reason,
                    "original_amount": str(job.amount),
                    "adjusted_amount": str(adjusted_amount),
                    "meta": job.meta or {},
                },
            )

            self.db.add(tx)

            # -------------------------------------------------
            # 7. APPLY BALANCE UPDATE (SAFE)
            # -------------------------------------------------
            wallet.balance = wallet.balance - adjusted_amount

            await self.db.flush()
            await self.db.commit()

            logger.info(
                f"✅ Reward paid: {job.reference} | "
                f"{adjusted_amount} XAF → user {job.user_id}"
            )

            return {
                "status": "success",
                "reference": job.reference,
                "transaction_id": str(tx.id),
                "amount": str(adjusted_amount),
            }

        except SQLAlchemyError as db_error:
            await self.db.rollback()

            logger.exception(f"💥 DB failure on reward: {job.reference}")

            return {
                "status": "failed",
                "reason": "database_error",
                "reference": job.reference,
                "error": str(db_error),
            }

        except Exception as e:
            await self.db.rollback()

            logger.exception(f"💥 Unexpected reward failure: {job.reference}")

            return {
                "status": "failed",
                "reason": "internal_error",
                "reference": job.reference,
                "error": str(e),
            }

    # =========================================================
    # 🔁 RETRY WRAPPER (EXPONENTIAL BACKOFF)
    # =========================================================
    async def process_with_retry(
        self,
        job: RewardJob,
        retries: int = 3,
    ) -> Dict[str, Any]:

        last_error = None

        for attempt in range(1, retries + 1):
            try:
                result = await self.process_reward(job)

                # Stop retry if not retryable
                if result["status"] in ["success", "duplicate", "blocked"]:
                    return result

            except Exception as e:
                last_error = e
                logger.error(
                    f"⚠️ Retry {attempt} failed for {job.reference}: {e}"
                )

            await asyncio.sleep(2 ** attempt)

        return {
            "status": "failed",
            "reason": "max_retries_exceeded",
            "reference": job.reference,
            "error": str(last_error),
        }