from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.blood.domain.ai.reward_optimizer import RewardContext, RewardOptimizer
from app.modules.blood.security.fraud_detection import FraudDetector
from app.modules.blood.wallet.repository import WalletRepository
from app.modules.rewards.worker.reward_request import RewardRequest
from app.modules.rewards.worker.reward_worker import RewardJob, RewardWorker

logger = logging.getLogger(__name__)


# =========================================================
# SERVICE
# =========================================================
class RewardService:
    """
    Enterprise reward orchestration.

    Guarantees:
    - Fully async execution path
    - Strict idempotency enforcement
    - Fraud check before write
    - No side effects in preview mode
    - Safe JSON serialization
    - Clean separation between optimizer / fraud / worker
    """

    def __init__(
        self,
        db: AsyncSession,
        wallet_repo: WalletRepository,
        fraud_detector: FraudDetector,
        reward_optimizer: RewardOptimizer,
        reward_worker: RewardWorker,
        idempotency_store,
    ) -> None:
        self.db = db
        self.wallet_repo = wallet_repo
        self.fraud_detector = fraud_detector
        self.reward_optimizer = reward_optimizer
        self.reward_worker = reward_worker
        self.idempotency_store = idempotency_store

    # =========================================================
    # PUBLIC API
    # =========================================================
    async def process_reward(self, req: RewardRequest) -> Dict[str, Any]:
        reference = self._resolve_reference(req)

        # -------------------------
        # IDENTITY GUARD
        # -------------------------
        if await self.idempotency_store.exists(reference):
            return {
                "status": "duplicate",
                "reference": reference,
                "message": "Reward already processed",
            }

        wallet = await self.wallet_repo.get_wallet_by_id(self.db, req.wallet_id)
        if not wallet:
            raise ValueError("Wallet not found")

        if str(wallet.owner_id) != str(req.user_id):
            raise ValueError("Wallet ownership mismatch")

        base_amount = self._require_positive_decimal(req.base_amount, "base_amount")
        incentive = self._effective_incentive(req)

        # -------------------------
        # CONTEXT BUILD
        # -------------------------
        ctx = self._build_context(req, reference, True, incentive)
        payload = self.reward_optimizer.build_reward_payload(ctx)

        points = int(payload["reward_points"])
        credit = Decimal(str(payload["wallet_credit"]))

        # -------------------------
        # FRAUD CHECK (BEFORE WRITE)
        # -------------------------
        fraud = await self.fraud_detector.check(
            user_id=str(req.user_id),
            amount=credit,
            phone=req.phone or "system",
            idempotency_key=reference,
            provider_tx_id=req.payment_reference,
        )

        if fraud.is_fraud:
            return {
                "status": "blocked",
                "reason": "fraud_detected",
                "risk_score": fraud.risk_score,
                "fraud_flags": fraud.reasons,
                "reference": reference,
                "amount": str(base_amount),
            }

        # -------------------------
        # IDENTITY PERSIST
        # -------------------------
        await self.idempotency_store.save(reference)

        # -------------------------
        # WORKER JOB
        # -------------------------
        job = RewardJob(
            user_id=str(req.user_id),
            wallet_id=str(wallet.id),
            amount=credit,
            reason="BLOOD_DONATION_REWARD",
            reference=reference,
            meta={
                "points": points,
                "fraud_risk": fraud.risk_score,
                "fraud_flags": fraud.reasons,
                "label": payload["label"],
                "surge_multiplier": payload["surge_multiplier"],
                "base_amount": str(base_amount),
                "context": self._safe_json(req.context),
                "reward_context": self._safe_json(
                    {
                        **ctx.__dict__,
                        "base_amount": str(base_amount),
                        "incentive_amount": incentive,
                    }
                ),
            },
        )

        result = await self.reward_worker.process_with_retry(job)

        return {
            "status": result.get("status", "failed"),
            "reference": reference,
            "wallet_id": str(wallet.id),
            "amount": str(base_amount),
            "reward_points": points,
            "wallet_credit": str(credit),
            "fraud_risk": fraud.risk_score,
            "fraud_flags": fraud.reasons,
            "label": payload["label"],
            "surge_multiplier": payload["surge_multiplier"],
            "message": result.get("message"),
            "transaction_id": result.get("transaction_id"),
            "transaction": result if result.get("status") == "success" else None,
        }

    # =========================================================
    # PREVIEW (NO SIDE EFFECTS)
    # =========================================================
    async def preview_reward(self, req: RewardRequest) -> Dict[str, Any]:
        reference = self._resolve_reference(req)

        wallet = await self.wallet_repo.get_wallet_by_id(self.db, req.wallet_id)
        if not wallet:
            raise ValueError("Wallet not found")

        if str(wallet.owner_id) != str(req.user_id):
            raise ValueError("Wallet ownership mismatch")

        base_amount = self._require_positive_decimal(req.base_amount, "base_amount")
        incentive = self._effective_incentive(req)

        ctx = self._build_context(req, reference, False, incentive)
        payload = self.reward_optimizer.build_reward_payload(ctx)

        return {
            "status": "preview",
            "reference": reference,
            "wallet_id": str(wallet.id),
            "amount": str(base_amount),
            "reward_points": int(payload["reward_points"]),
            "wallet_credit": str(Decimal(str(payload["wallet_credit"]))),
            "label": payload["label"],
            "surge_multiplier": payload["surge_multiplier"],
        }

    # =========================================================
    # CONTEXT BUILDER
    # =========================================================
    def _build_context(
        self,
        req: RewardRequest,
        reference: str,
        is_completed: bool,
        incentive: int,
    ) -> RewardContext:
        return RewardContext(
            is_completed=is_completed,
            is_urgent=req.is_urgent,
            same_city=req.same_city,
            exact_blood_match=req.exact_blood_match,
            response_minutes=req.response_minutes,
            donor_points=req.donor_points,
            total_donations=req.total_donations,
            successful_responses=req.successful_responses,
            rejection_count=req.rejection_count,
            incentive_amount=max(int(incentive), 0),
            request_units=req.request_units,
            hospital_priority_level=req.hospital_priority_level,
            active_donors=req.active_donors,
            required_donors=req.required_donors,
            reference_code=reference,
            payment_reference=req.payment_reference,
        )

    # =========================================================
    # REFERENCE HANDLING
    # =========================================================
    def _resolve_reference(self, req: RewardRequest) -> str:
        ref = (req.reference or str(uuid4())).strip()
        return ref or str(uuid4())

    # =========================================================
    # INCENTIVE LOGIC
    # =========================================================
    def _effective_incentive(self, req: RewardRequest) -> int:
        if req.incentive_amount is not None:
            try:
                val = int(Decimal(str(req.incentive_amount)))
                if val > 0:
                    return val
            except Exception:
                pass

        return int(self._require_positive_decimal(req.base_amount, "base_amount"))

    # =========================================================
    # VALIDATION
    # =========================================================
    def _require_positive_decimal(self, value: Any, field: str) -> Decimal:
        try:
            amount = Decimal(str(value))
        except Exception as exc:
            raise ValueError(f"{field} must be decimal") from exc

        if amount <= 0:
            raise ValueError(f"{field} must be > 0")

        return amount

    # =========================================================
    # SAFE JSON
    # =========================================================
    def _safe_json(self, value: Any) -> Any:
        if value is None:
            return None

        if isinstance(value, dict):
            return {
                k: self._safe_json(v)
                for k, v in value.items()
            }

        if isinstance(value, list):
            return [self._safe_json(v) for v in value]

        if isinstance(value, Decimal):
            return str(value)

        if hasattr(value, "isoformat"):
            return value.isoformat()

        return value