from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.modules.payment.models import Payment

logger = logging.getLogger(__name__)


# =========================================================
# 🚨 FRAUD SIGNAL TYPES
# =========================================================
FRAUD_REPEAT_PAYMENT = "REPEAT_PAYMENT"
FRAUD_DOUBLE_SPEND = "DOUBLE_SPEND"
FRAUD_IDEMPOTENCY_BYPASS = "IDEMPOTENCY_BYPASS"
FRAUD_SUSPICIOUS_FREQUENCY = "SUSPICIOUS_FREQUENCY"
FRAUD_PHONE_MISMATCH = "PHONE_MISMATCH"
FRAUD_HIGH_VALUE_SPIKE = "HIGH_VALUE_SPIKE"


# =========================================================
# 📦 FRAUD RESULT
# =========================================================
@dataclass
class FraudResult:
    is_fraud: bool
    risk_score: float
    reasons: List[str]
    metadata: Dict[str, Any]


# =========================================================
# 🧠 FRAUD DETECTOR (PRODUCTION ENGINE)
# =========================================================
class FraudDetector:
    """
    Production-grade fraud detection system.

    Features:
    -------------------------------------------------
    ✔ DB-backed verification (no memory-only flaws)
    ✔ Idempotency abuse detection
    ✔ Double spend detection (provider_tx_id)
    ✔ Frequency spike detection
    ✔ High-value anomaly detection
    ✔ Structured scoring (0–100)
    ✔ Async-safe
    ✔ Analytics-ready metadata
    """

    def __init__(
        self,
        db: AsyncSession,
        max_transactions_per_minute: int = 5,
        duplicate_window_seconds: int = 60,
        high_value_threshold: Decimal = Decimal("50000"),
    ):
        self.db = db
        self.max_tpm = max_transactions_per_minute
        self.dup_window = duplicate_window_seconds
        self.high_value_threshold = high_value_threshold

    # =========================================================
    # 🚀 MAIN ENTRY (ASYNC)
    # =========================================================
    async def check(
        self,
        user_id: str,
        amount: Decimal,
        phone: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        provider_tx_id: Optional[str] = None,
    ) -> FraudResult:

        now = int(time.time())
        risk = 0
        reasons: List[str] = []

        # =====================================================
        # 1. HIGH VALUE SPIKE
        # =====================================================
        if amount >= self.high_value_threshold:
            risk += 30
            reasons.append(FRAUD_HIGH_VALUE_SPIKE)

        # =====================================================
        # 2. FREQUENCY CHECK (DB-based)
        # =====================================================
        stmt_freq = select(func.count(Payment.id)).where(
            Payment.user_id == user_id,
            Payment.created_at >= func.now() - func.interval("1 minute"),
        )

        tx_count = (await self.db.execute(stmt_freq)).scalar() or 0

        if tx_count >= self.max_tpm:
            risk += 40
            reasons.append(FRAUD_SUSPICIOUS_FREQUENCY)

        # =====================================================
        # 3. IDEMPOTENCY ABUSE
        # =====================================================
        if idempotency_key:
            stmt_idem = select(Payment.id).where(
                Payment.idempotency_key == idempotency_key
            )

            existing = (await self.db.execute(stmt_idem)).scalar_one_or_none()

            if existing:
                risk += 90
                reasons.append(FRAUD_IDEMPOTENCY_BYPASS)

        # =====================================================
        # 4. DOUBLE SPEND DETECTION
        # =====================================================
        if provider_tx_id:
            stmt_tx = select(Payment.id).where(
                Payment.provider_transaction_id == provider_tx_id
            )

            exists = (await self.db.execute(stmt_tx)).scalar_one_or_none()

            if exists:
                risk += 100
                reasons.append(FRAUD_DOUBLE_SPEND)

        # =====================================================
        # 5. REPEAT PAYMENT (same amount burst)
        # =====================================================
        stmt_repeat = select(func.count(Payment.id)).where(
            Payment.user_id == user_id,
            Payment.amount == amount,
            Payment.created_at >= func.now() - func.interval("2 minutes"),
        )

        repeat_count = (await self.db.execute(stmt_repeat)).scalar() or 0

        if repeat_count >= 3:
            risk += 25
            reasons.append(FRAUD_REPEAT_PAYMENT)

        # =====================================================
        # 6. PHONE SANITY CHECK
        # =====================================================
        if phone:
            if not phone.startswith(("2376", "23767", "23765", "23768")):
                risk += 10
                reasons.append(FRAUD_PHONE_MISMATCH)

        # =====================================================
        # FINAL DECISION
        # =====================================================
        risk_score = min(risk, 100)
        is_fraud = risk_score >= 70

        result = FraudResult(
            is_fraud=is_fraud,
            risk_score=risk_score,
            reasons=reasons,
            metadata={
                "user_id": user_id,
                "amount": str(amount),
                "phone": phone,
                "timestamp": now,
                "checks": {
                    "frequency": tx_count,
                    "repeat": repeat_count,
                }
            },
        )

        if is_fraud:
            logger.warning(f"🚨 FRAUD DETECTED: {result}")
        else:
            logger.info(f"✅ Fraud check passed | risk={risk_score}")

        return result